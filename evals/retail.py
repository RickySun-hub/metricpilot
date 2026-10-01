"""Reproduce public-retail SQL versus source-row references; no paid calls."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from backend.retail import load_snapshot, run_retail_analysis

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = load_snapshot()
    answer = run_retail_analysis('Which countries contributed to gross sales change from October to November 2011?')
    assert answer['status'] == 'completed', answer['summary']
    comparison = answer['evidence'][0]['result']
    contribution = answer['evidence'][1]['result']
    reference = source['reference']
    checks = []
    for side in ('before', 'after'):
        for field in ('gross_sales_gbp', 'orders', 'lines', 'units'):
            actual, expected = Decimal(str(comparison[side][field])), Decimal(str(reference[side][field]))
            checks.append({'field':f'{side}.{field}','actual':str(actual),'expected':str(expected),'passed':actual == expected})
    by_country = {row['country']:row for row in reference['country_totals']}
    assert {row['country'] for row in contribution['countries']} == set(by_country)
    for row in contribution['countries']:
        actual, expected = Decimal(str(row['delta_gbp'])), Decimal(by_country[row['country']]['delta_gbp'])
        checks.append({'field':f"country_delta.{row['country']}",'actual':str(actual),'expected':str(expected),'passed':actual == expected})
    for label, value in [('comparison_delta', comparison['delta_gbp']), ('country_total_delta', contribution['delta_gbp'])]:
        checks.append({'field':label,'actual':str(value),'expected':reference['delta_gbp'],
                       'passed':Decimal(str(value)) == Decimal(reference['delta_gbp'])})
    report = {'scope':'Fixed public-data numerical cross-check, not a held-out model benchmark or causal estimate.',
              'run_at_utc':datetime.now(timezone.utc).isoformat(), 'source':source['source'], 'audit':source['audit'],
              'snapshot_hash':source['hash'], 'reference_method':'Separate Python Decimal accumulators over accepted workbook rows; shares the documented filter, which is also hand-fixture tested.',
              'checks':checks,'passed':all(item['passed'] for item in checks),'check_count':len(checks),
              'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                               ('backend/retail.py','backend/import_retail.py','evals/retail.py')},
              'execution':answer,
              'omitted_checks':['Live model action selection and model baseline','Public deployment validation','Causal attribution','Browser interaction verification for the new retail page']}
    output=ROOT/'evals/results/retail.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'checks':len(checks),'source_rows':source['source']['source_rows'],
                      'model_calls':answer['metrics']['model_calls'],'api_cost_usd':0,'output':str(output)},indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
