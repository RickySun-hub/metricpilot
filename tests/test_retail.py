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


def test_retail_deterministic_never_checks_or_calls_live_provider(snapshot, monkeypatch):
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question: [])
    for name in ('live_available', 'reserve', 'generate_report'):
        monkeypatch.setattr(retail, name, lambda *args, **kwargs: pytest.fail('Deterministic request used live path'), raising=False)
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot)
    assert report['status'] == 'completed'
    assert report['model'] is None
    assert len(report['findings']) == 3


def test_retail_live_is_gated_before_retrieval(snapshot, monkeypatch):
    monkeypatch.setattr(retail, 'live_available', lambda: False, raising=False)
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question: pytest.fail('Disabled live request retrieved contracts'))
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot, mode='live')
    assert report['status'] == 'budget_exceeded'
    assert report['metrics']['tool_calls'] == report['metrics']['model_calls'] == 0
    assert report['findings'] == []


def test_retail_live_reservation_failure_stops_work(snapshot, monkeypatch):
    from backend.budget import BudgetError
    monkeypatch.setattr(retail, 'live_available', lambda: True, raising=False)
    def refuse(**kwargs):
        raise BudgetError('Live request budget or rate limit exhausted')
    monkeypatch.setattr(retail, 'reserve', refuse, raising=False)
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question: pytest.fail('Unreserved request retrieved contracts'))
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot, mode='live', client='test-client')
    assert report['status'] == 'budget_exceeded'
    assert report['evidence'] == []


def test_retail_live_report_uses_executed_country_evidence(snapshot, monkeypatch):
    stages = []
    monkeypatch.setattr(retail, 'live_available', lambda: True, raising=False)
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs: stages.append(('reserve', kwargs['client'])), raising=False)
    def retrieve(question):
        stages.append(('retrieve', question))
        return [{**retail.CONTRACTS[0], 'version':'1.0'}]
    monkeypatch.setattr(retail, 'retrieve_contracts', retrieve)
    def generate(state, findings):
        stages.append(('generate', state['question']))
        assert state['metrics']['tool_calls'] == 2
        assert isinstance(state['started'], float)
        assert len(state['evidence']) == 2
        assert state['retrieval'][0]['id'] == 'retail_gross_sales'
        assert state['warnings'] and state['trace']
        country_findings = [finding for finding in findings if finding['field_path'].startswith('countries.')]
        assert len(country_findings) == 3
        for country in ('UK', 'France', 'Germany'):
            assert sum(country in finding['label'] for finding in country_findings) == 1
        for finding in country_findings:
            row = state['evidence'][1]['result']['countries'][int(finding['field_path'].split('.')[1])]
            assert row['country'] in finding['label']
            assert finding['value'] == row[finding['field_path'].split('.')[2]]
        return {'status':'completed', 'summary':'Grounded model narrative.', 'findings':findings,
                'warnings':state['warnings'], 'trace':state['trace'],
                'claims':[{'text':'Grounded model narrative.', 'fact_ids':['f0'], 'evidence_ids':[state['evidence'][0]['id']], 'contract_ids':['retail_gross_sales']}],
                'citations':[{'id':'retail_gross_sales','kind':'contract','title':'Gross positive sales in GBP'}],
                'generation':{'method':'llm_grounded','numeric_validation':'passed','citation_validation':'passed','semantic_validation':'not_automated'},
                'metrics':{**state['metrics'], 'model_calls':1, 'input_tokens':100, 'output_tokens':30, 'estimated_cost_usd':.000088}}
    monkeypatch.setattr(retail, 'generate_report', generate, raising=False)
    report = retail.run_retail_analysis('Which countries contributed to the sales change?', snapshot=snapshot, mode='live', client='test-client')
    assert report['status'] == 'completed'
    assert report['mode'] == 'live'
    assert report['model'] == retail.MODEL
    assert report['summary'] == 'Grounded model narrative.'
    assert report['metrics']['model_calls'] == 1
    assert report['claims'] and report['citations']
    assert [stage[0] for stage in stages] == ['reserve', 'retrieve', 'generate']
    assert stages[0][1] == 'test-client'


def test_retail_live_generation_failure_is_safe_and_preserves_evidence(snapshot, monkeypatch):
    monkeypatch.setattr(retail, 'live_available', lambda: True, raising=False)
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs: None, raising=False)
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question: [])
    def fail(*args):
        raise ValueError('private provider credential or payload')
    monkeypatch.setattr(retail, 'generate_report', fail, raising=False)
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot, mode='live')
    assert report['status'] == 'provider_error'
    assert report['findings'] == []
    assert report['claims'] == []
    assert len(report['evidence']) == report['metrics']['tool_calls'] == 2
    assert 'private' not in str(report)


def test_retail_unknown_mode_is_rejected_without_work(snapshot, monkeypatch):
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question: pytest.fail('Invalid mode retrieved contracts'))
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot, mode='shell')
    assert report['status'] == 'invalid_data'
    assert report['evidence'] == []


def test_retail_unsupported_live_request_does_not_reserve(snapshot, monkeypatch):
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs: pytest.fail('Unsupported request reserved budget'))
    report = retail.run_retail_analysis('What is sales conversion?', snapshot=snapshot, mode='live')
    assert report['status'] == 'unsupported'
    assert report['metrics']['model_calls'] == report['metrics']['tool_calls'] == 0


def test_retail_late_generation_withholds_claims_but_retains_usage(snapshot, monkeypatch):
    clock = {'now':0.0}
    monkeypatch.setattr(retail.time, 'perf_counter', lambda:clock['now'])
    monkeypatch.setattr(retail, 'live_available', lambda:True)
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs:None)
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question:[])
    def late(state, findings):
        clock['now'] = 46.0
        return {'status':'completed','summary':'Late model narrative.','findings':findings,
                'claims':[{'text':'Late model narrative.'}], 'citations':[{'id':'source'}],
                'generation':{'method':'llm_grounded','numeric_validation':'passed','citation_validation':'passed'},
                'metrics':{**state['metrics'],'model_calls':1,'input_tokens':100,'output_tokens':20,'estimated_cost_usd':.000072}}
    monkeypatch.setattr(retail, 'generate_report', late)
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot, mode='live')
    assert report['status'] == 'timed_out'
    assert report['findings'] == report['claims'] == report['citations'] == []
    assert report['metrics']['model_calls'] == 1
    assert report['metrics']['input_tokens'] == 100
    assert report['metrics']['tool_calls'] == 2
    assert 'Late' not in report['summary']


def test_retail_live_grounds_public_data_with_mocked_provider(monkeypatch):
    from backend import generation
    monkeypatch.setattr(retail, 'live_available', lambda:True)
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs:None)
    def generated(state, facts):
        total = next(fact for fact in facts if fact['label'] == 'Sales change')
        country = next(fact for fact in facts if fact['label'] == 'United Kingdom: Sales change contribution')
        assert state['reservation_usd'] == .02
        assert state['metrics']['reserved_request_usd'] == .02
        assert any(doc['id'] == 'retail_country' for doc in state['retrieval'])
        return {'status':'answered', 'abstention_reason':'', 'claims':[
            {'text':f"Gross positive sales changed by {{{{{total['id']}}}}}; the United Kingdom contribution was {{{{{country['id']}}}}}. This is an arithmetic decomposition, not a causal explanation.",
             'fact_ids':[total['id'],country['id']], 'evidence_ids':[total['evidence_id'],country['evidence_id']], 'contract_ids':['retail_country']}
        ]}, {'prompt_tokens':500,'completion_tokens':100}
    monkeypatch.setattr(generation, 'generate_answer', generated)
    report = retail.run_retail_analysis('Which countries contributed to the sales change?', mode='live')
    assert report['status'] == 'completed'
    assert report['generation']['method'] == 'llm_grounded'
    assert report['generation']['numeric_validation'] == report['generation']['citation_validation'] == 'passed'
    assert report['generation']['semantic_validation'] == 'not_automated'
    assert report['metrics']['model_calls'] == 1
    assert report['metrics']['tool_calls'] == 2
    assert len(report['findings']) == 9 + len(report['evidence'][1]['result']['countries'])
    assert 'United Kingdom' in report['summary']
    assert len(report['citations']) == 3


def test_retail_live_rejects_unverified_narrative_but_keeps_usage(snapshot, monkeypatch):
    from backend import generation
    monkeypatch.setattr(retail, 'live_available', lambda:True)
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs:None)
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question:[retail.CONTRACTS[0]])
    def generated(state, facts):
        return {'status':'answered','abstention_reason':'','claims':[
            {'text':'Gross sales changed by 999 GBP.', 'fact_ids':[],
             'evidence_ids':[state['evidence'][0]['id']], 'contract_ids':['retail_gross_sales']}
        ]}, {'prompt_tokens':100,'completion_tokens':30}
    monkeypatch.setattr(generation, 'generate_answer', generated)
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot, mode='live')
    assert report['status'] == 'verification_failed'
    assert report['findings'] == report['claims'] == report['citations'] == []
    assert report['metrics']['model_calls'] == 1
    assert report['metrics']['input_tokens'] == 100
    assert '999' not in report['summary']
    assert report['metrics']['tool_calls'] == len(report['evidence']) == 2


def test_retail_live_can_ground_invoice_and_volume_counts(monkeypatch):
    from backend import generation
    monkeypatch.setattr(retail, 'live_available', lambda:True)
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs:None)
    def generated(state, facts):
        counts = [fact for fact in facts if fact['field_path'] in
                  ('before.orders','after.orders','before.lines','after.lines','before.units','after.units')]
        assert len(counts) == 6
        assert {fact['unit'] for fact in counts} == {'invoices','lines','units'}
        claims = []
        for field, metric in [('orders','invoice count'),('lines','invoice line count'),('units','unit volume')]:
            before = next(fact for fact in counts if fact['field_path'] == 'before.' + field)
            after = next(fact for fact in counts if fact['field_path'] == 'after.' + field)
            claims.append({'text':f"The {metric} changed from {{{{{before['id']}}}}} in October to {{{{{after['id']}}}}} in November.",
                           'fact_ids':[before['id'],after['id']], 'evidence_ids':[before['evidence_id']],
                           'contract_ids':[state['retrieval'][0]['id']]})
        return {'status':'answered','abstention_reason':'','claims':claims}, {'prompt_tokens':500,'completion_tokens':120}
    monkeypatch.setattr(generation, 'generate_answer', generated)
    report = retail.run_retail_analysis('Compare invoice counts and transaction volume from October to November 2011', mode='live')
    assert report['status'] == 'completed'
    assert report['generation']['numeric_validation'] == report['generation']['citation_validation'] == 'passed'
    assert len(report['claims']) == 3
    assert all(label in report['summary'] for label in ('invoice count','invoice line count','unit volume'))
    assert report['metrics']['model_calls'] == 1
    comparison = report['evidence'][0]['result']
    for finding in report['findings']:
        if finding['unit'] != 'GBP':
            period, field = finding['field_path'].split('.')
            assert finding['value'] == comparison[period][field]


@pytest.mark.parametrize('mode', ['deterministic','live'])
@pytest.mark.parametrize('failure', [retail.ToolError('private data validation details'), OSError('private database path')])
def test_retail_second_tool_failure_preserves_completed_evidence(snapshot, monkeypatch, mode, failure):
    monkeypatch.setattr(retail, 'retrieve_contracts', lambda question:[])
    monkeypatch.setattr(retail, 'live_available', lambda:True)
    monkeypatch.setattr(retail, 'reserve', lambda **kwargs:None)
    def fail(self):
        raise failure
    monkeypatch.setattr(retail.RetailAnalytics, 'country_contributions', fail)
    monkeypatch.setattr(retail, 'generate_report', lambda *args:pytest.fail('Failed tool request attempted narrative generation'))
    report = retail.run_retail_analysis('Compare gross sales', snapshot=snapshot, mode=mode)
    expected = 'provider_error' if mode == 'live' and not isinstance(failure, retail.ToolError) else 'invalid_data'
    assert report['status'] == expected
    assert report['metrics']['tool_calls'] == len(report['evidence']) == 1
    assert report['evidence'][0]['tool'] == 'compare_retail_sales'
    assert report['evidence'][0]['result']['delta_gbp'] == pytest.approx(.2)
    assert report['metrics']['model_calls'] == 0
    assert report['findings'] == report['claims'] == report['citations'] == []
    assert report['trace'][-1]['step'] == 'execute'
    assert 'private' not in str(report)
