"""Independent small-fixture checks for the public retail mode."""
import pytest

from backend import retail


@pytest.fixture
def snapshot():
    return {
        'source': {'name': 'Public test fixture', 'source_rows': 7, 'url': 'https://example.invalid',
                   'license': 'CC BY 4.0'},
        'audit': {'total_rows': 7, 'included_lines': 7, 'excluded_lines': 0},
        'monthly': [
            {'month':'2011-10','country':'UK','lines':2,'orders':2,'units':3,'gross_sales_gbp':'100.10'},
            {'month':'2011-10','country':'France','lines':1,'orders':1,'units':1,'gross_sales_gbp':'50.20'},
            {'month':'2011-11','country':'UK','lines':3,'orders':2,'units':4,'gross_sales_gbp':'140.40'},
            {'month':'2011-11','country':'Germany','lines':1,'orders':1,'units':1,'gross_sales_gbp':'10.10'},
        ],
        'hash': 'fixture',
    }


def test_retail_sales_and_country_contributions_reconcile(snapshot):
    with retail.RetailAnalytics(snapshot) as tools:
        comparison = tools.compare_sales()
        contributions = tools.country_contributions()
    assert comparison['result']['before']['gross_sales_gbp'] == pytest.approx(150.30)
    assert comparison['result']['after']['gross_sales_gbp'] == pytest.approx(150.50)
    assert comparison['result']['delta_gbp'] == pytest.approx(.20)
    assert comparison['result']['before']['orders'] == 3
    assert comparison['args'] == {'before_month':'2011-10','after_month':'2011-11'}
    by_country = {row['country']: row for row in contributions['result']['countries']}
    assert by_country['UK']['delta_gbp'] == pytest.approx(40.30)
    assert by_country['France']['delta_gbp'] == pytest.approx(-50.20)
    assert by_country['Germany']['delta_gbp'] == pytest.approx(10.10)
    assert contributions['result']['delta_gbp'] == pytest.approx(.20)
    assert comparison['sql'] and contributions['sql']


def test_retail_rejects_unsupported_period_and_empty_snapshot(snapshot):
    with retail.RetailAnalytics(snapshot) as tools:
        with pytest.raises(retail.ToolError):
            tools.compare_sales(before_month='2011-12')
    snapshot['monthly'] = []
    with retail.RetailAnalytics(snapshot) as tools:
        with pytest.raises(retail.ToolError):
            tools.compare_sales()


@pytest.mark.parametrize('question', ['Analyze activation', 'Show the funnel', 'Run an A/B experiment',
                                      'DROP TABLE retail;', 'What is customer retention?',
                                      'Compare sales in 2011-12', 'Compare sales in December 2011',
                                      'Compare sales in October and November 2026', 'Compare sales last month',
                                      'What is net sales?', 'What is sales conversion?',
                                      'Which products drove the sales change?', 'Compare customer counts by country',
                                      'Compare sales in France', 'Compare sales for product 12345',
                                      'What were sales in 2011?', 'Show October sales', 'Compare sales in 2011-10',
                                      'How did sales change from November to October 2011?',
                                      'Compare sales from 2011-11 to 2011-10'])
def test_retail_cannot_invent_behavioral_or_experiment_data(question, snapshot, monkeypatch):
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda *args: pytest.fail('Unsupported request retrieved contracts'))
    report = retail.run_retail_analysis(question, snapshot=snapshot)
    assert report['status'] == 'unsupported'
    assert report['evidence'] == []
    assert report['metrics']['tool_calls'] == 0


def test_retail_report_numbers_reference_executed_evidence(snapshot, monkeypatch):
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question: [])
    report = retail.run_retail_analysis('How did sales change between October and November?', snapshot=snapshot)
    assert report['status'] == 'completed'
    assert report['mode'] == 'deterministic'
    assert report['metrics']['tool_calls'] == 2
    assert report['metrics']['model_calls'] == 0
    assert report['dataset']['source_type'] == 'real_public_transactions'
    assert report['dataset']['source_rows'] == 7
    evidence = {e['id']: e['result'] for e in report['evidence']}
    for finding in report['findings']:
        value = evidence[finding['evidence_id']]
        for part in finding['field_path'].split('.'):
            value = value[part]
        assert finding['value'] == pytest.approx(value * finding['scale'])
    assert any('causal' in warning for warning in report['warnings'])


def test_retail_snapshot_checksum_failure_is_typed(tmp_path, monkeypatch):
    target = tmp_path / 'retail.json'
    target.write_text('{"hash":"invalid","monthly":[]}', encoding='utf-8')
    monkeypatch.setattr(retail, 'SNAPSHOT_PATH', target)
    with pytest.raises(retail.DatasetUnavailableError):
        retail.load_snapshot()


@pytest.mark.parametrize('mutation', ['missing_audit', 'nonfinite_money', 'duplicate_group', 'incorrect_line_total'])
def test_retail_malformed_checksummed_snapshot_is_typed(tmp_path, monkeypatch, mutation):
    import json
    from backend.import_retail import canonical_hash
    snapshot = retail.load_snapshot()
    if mutation == 'missing_audit':
        del snapshot['audit']
    elif mutation == 'nonfinite_money':
        snapshot['monthly'][0]['gross_sales_gbp'] = 'NaN'
    elif mutation == 'duplicate_group':
        snapshot['monthly'].append(snapshot['monthly'][0])
    else:
        snapshot['audit']['included_lines'] += 1
    snapshot['hash'] = canonical_hash(snapshot)
    target = tmp_path / 'retail.json'; target.write_text(json.dumps(snapshot), encoding='utf-8')
    monkeypatch.setattr(retail, 'SNAPSHOT_PATH', target)
    with pytest.raises(retail.DatasetUnavailableError):
        retail.load_snapshot()


@pytest.mark.parametrize('slow_stage, expected_tools', [('retrieve',0), ('compare',1)])
def test_retail_expired_stage_stops_next_tool(snapshot, monkeypatch, slow_stage, expected_tools):
    clock = {'now':0.0}
    monkeypatch.setattr(retail.time,'perf_counter',lambda:clock['now'])
    def retrieve(question):
        if slow_stage == 'retrieve': clock['now'] = 46.0
        return []
    monkeypatch.setattr(retail,'retrieve_contracts',retrieve)
    original = retail.RetailAnalytics.compare_sales
    def compare(self):
        result = original(self)
        if slow_stage == 'compare': clock['now'] = 46.0
        return result
    monkeypatch.setattr(retail.RetailAnalytics,'compare_sales',compare)
    report = retail.run_retail_analysis('Compare gross sales',snapshot=snapshot)
    assert report['status'] == 'timed_out'
    assert report['findings'] == []
    assert report['metrics']['tool_calls'] == expected_tools
    assert len(report['evidence']) == expected_tools


def test_pinned_public_data_sql_matches_source_row_references():
    from decimal import Decimal
    snapshot = retail.load_snapshot()
    assert snapshot['source']['source_rows'] == 541909
    assert snapshot['audit']['included_lines'] == 530104
    assert snapshot['audit']['excluded_lines'] == 11805
    assert snapshot['audit']['included_lines'] + snapshot['audit']['excluded_lines'] == snapshot['audit']['total_rows']
    with retail.RetailAnalytics(snapshot) as tools:
        comparison = tools.compare_sales()['result']
        countries = tools.country_contributions()['result']
    reference = snapshot['reference']
    for side in ('before','after'):
        for field in ('gross_sales_gbp','orders','lines','units'):
            assert Decimal(str(comparison[side][field])) == Decimal(str(reference[side][field]))
    assert Decimal(str(comparison['delta_gbp'])) == Decimal(reference['delta_gbp'])
    expected = {row['country']: row for row in reference['country_totals']}
    assert {row['country'] for row in countries['countries']} == set(expected)
    for row in countries['countries']:
        assert Decimal(str(row['delta_gbp'])) == Decimal(expected[row['country']]['delta_gbp'])
    assert Decimal(str(countries['delta_gbp'])) == Decimal(reference['delta_gbp'])


def test_retail_end_to_end_returns_real_source_and_semantic_contracts():
    from fastapi.testclient import TestClient
    from api.index import app
    response = TestClient(app).post('/api/retail/analyze', json={'question':'Which countries contributed to the sales change?'})
    assert response.status_code == 200
    report = response.json()
    assert report['status'] == 'completed'
    assert report['dataset']['source_rows'] == 541909
    assert report['dataset']['source_type'] == 'real_public_transactions'
    assert report['metrics']['model_calls'] == 0
    assert report['metrics']['tool_calls'] == 2
    assert any(doc['id'] == 'retail_country' for doc in report['retrieval'])
    assert all(doc['method'] == 'minilm_cosine_similarity' for doc in report['retrieval'])
