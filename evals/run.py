"""Deterministic regression or explicitly authorized paired live evaluation."""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from evals import reference

ROOT = Path(__file__).resolve().parents[1]

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def score(case, dataset, response):
    family = case['family']
    if family == 'boundary':
        expected = 'needs_clarification' if case['boundary_index'] in (0, 4) else 'unsupported'
        assert response['status'] == expected, f"status {response['status']} != {expected}"
        assert not response['evidence'], 'boundary request executed analytical tools'
        return
    expected_status = 'invalid_data' if family == 'experiment_srm' else 'completed'
    assert response['status'] == expected_status, f"terminal status {response['status']} != {expected_status}"
    evidence = response['evidence']
    assert evidence, 'missing numerical evidence'
    assert len({e['id'] for e in evidence}) == len(evidence), 'duplicate evidence IDs'
    assert all(e['sql'] and e['args'] is not None for e in evidence), 'missing execution audit'
    if family == 'metric':
        target, expected = 'compare_metric', reference.metric(dataset)
    elif family == 'funnel':
        target, expected = 'analyze_funnel', reference.funnel(dataset)
    elif family == 'decomposition':
        target, expected = 'decompose_change', reference.decomposition(dataset)
    else:
        target = 'check_experiment'
        experiment_id = 'onboarding_srm' if family == 'experiment_srm' else 'onboarding_valid'
        expected = reference.experiment(dataset, experiment_id)
    selected = next((e for e in evidence if e['tool'] == target), None)
    assert selected, f'missing tool {target}'
    reference.assert_fields(selected['result'], expected)
    by_id = {item['id']: item for item in evidence}
    for finding in response['findings']:
        item = by_id[finding['evidence_id']]['result']
        for part in finding['field_path'].split('.'):
            item = item[part]
        assert abs(finding['value']-item*finding['scale']) <= 1e-9, 'unsupported report value'
    assert len(evidence) <= 5, 'tool budget bypass'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['deterministic', 'live'], default='deterministic')
    parser.add_argument('--split', choices=['dev', 'test', 'all'], default='test')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--allow-paid', action='store_true', help='Explicit paid-run opt-in; does not enable/configure live mode or change quotas')
    parser.add_argument('--track', choices=['synthetic', 'retail', 'adversarial'], default='synthetic')
    parser.add_argument('--family', action='append', choices=['metric', 'funnel', 'decomposition', 'experiment_valid', 'experiment_srm', 'boundary'], help='Filter synthetic families (repeatable); partial runs are smoke checks')
    parser.add_argument('--limit', type=int, help='Limit selected cases; partial runs cannot pass the full benchmark gate')
    parser.add_argument('--output', type=Path, help='JSON result destination; existing live result files are never overwritten')
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5:
        parser.error('--repeats must be 1..5')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    if args.track != 'synthetic' and args.family:
        parser.error('--family is only supported for the synthetic track')
    if args.mode == 'live':
        return run_live(args, parser)
    if args.track != 'synthetic':
        parser.error('Supplemental tracks require --mode live; use python -m evals.retail for zero-call retail numerical checks')
    from backend.data import generate_dataset
    from backend.agent import run_analysis
    manifest_path = ROOT / 'evals/cases.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    assert manifest_hash == manifest_path.with_suffix('.sha256').read_text().strip(), 'Manifest changed: document exposure and refreeze deliberately.'
    cases = [c for c in json.loads(manifest_bytes)['cases'] if args.split == 'all' or c['split'] == args.split]
    if args.family:
        cases = [c for c in cases if c['family'] in args.family]
    if args.limit is not None:
        cases = cases[:args.limit]
    if not cases:
        parser.error('No cases match the requested split/families')
    runs = []
    for repeat in range(args.repeats):
        records = []
        for case in cases:
            started = time.perf_counter()
            dataset = generate_dataset(seed=case['seed'], users=case['users'])
            record = {'id': case['id'], 'family': case['family'], 'seed': case['seed'], 'dataset_sha256': digest(dataset)}
            try:
                response = run_analysis(case['question'], mode='deterministic', dataset=dataset)
                score(case, dataset, response)
                record.update(passed=True, status=response['status'], tool_calls=len(response['evidence']))
            except Exception as exc:
                record.update(passed=False, error=f'{type(exc).__name__}: {exc}')
            record['elapsed_ms'] = round((time.perf_counter()-started)*1000, 2)
            records.append(record)
        runs.append({'repeat': repeat+1, 'passed': sum(r['passed'] for r in records), 'total': len(records), 'cases': records})
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    except Exception:
        revision, dirty = 'unavailable', True
    source_hashes = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                     for folder in ['backend', 'evals'] for p in sorted((ROOT/folder).rglob('*.py'))}
    report = {'scope': 'Deterministic controller and numerical synthetic regression. No LLM calls, no live model benchmark, no single-pass baseline comparison.',
              'run_at_utc': datetime.now(timezone.utc).isoformat(), 'mode': args.mode, 'split': args.split,
              'benchmark_scope': 'partial_smoke' if args.family or args.limit else 'deterministic_regression',
              'manifest_sha256': manifest_hash, 'code_sha': revision, 'working_tree_dirty': dirty,
              'source_sha256': source_hashes, 'model': None, 'model_calls': 0, 'model_tokens': 0,
              'model_api_cost_usd': 0, 'runs': runs,
              'omitted_checks': ['Live-model correctness and nondeterminism', 'Single-pass model baseline', 'Manual narrative review', 'Public deployment validation'],
              'gate_scope': 'Numerical/controller regression only; not the full release gate',
              'protocol_notes': ['Before the first agent benchmark execution, SRM terminal status aligned with invalid_data; unnamed nonexistent experiment aligned with needs_clarification. Manifest questions, seeds and split unchanged.'],
              'passed': all(r['passed'] == r['total'] for r in runs)}
    output = args.output or ROOT / ('evals/results/deterministic-smoke-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json' if args.family or args.limit else 'evals/results/deterministic.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'runs': [{'passed': r['passed'], 'total': r['total']} for r in runs], 'output': str(output)}, indent=2))
    if not report['passed']:
        raise SystemExit(1)

def load_live_environment(allow_paid: bool):
    """Load existing local settings only after explicit paid-run opt-in.

    Existing process values win. This never writes configuration, creates a key,
    changes a cap, or supplies a default enabling live mode.
    """
    if not allow_paid:
        return False
    from dotenv import load_dotenv
    return load_dotenv(ROOT / '.env.local', override=False)


def run_live(args, parser):
    from backend import budget
    from evals import live
    try:
        if not args.allow_paid:
            live.require_live_authorization(False)
        load_live_environment(args.allow_paid)
        live.require_live_authorization(args.allow_paid)
        _, manifest_hash, cases = live.select_cases(args.split, args.family, args.limit)
        if args.track == 'retail':
            cases = live.retail_cases()
        elif args.track == 'adversarial':
            cases = live.adversarial_cases()
        if args.track != 'synthetic' and args.limit is not None:
            cases = cases[:args.limit]
        output = args.output or ROOT / ('evals/results/live-'+args.track+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        if output.exists() or output.with_suffix('.review.json').exists():
            parser.error('Live output/review file already exists; choose a new path to preserve prior evidence.')
        before = budget.budget_snapshot()
    except (ValueError, budget.BudgetError) as exc:
        parser.error(str(exc))
    report = live.run_suite(cases, repeats=args.repeats, split=args.split, manifest_hash=manifest_hash,
                            track=args.track, checkpoint=lambda value: live.write_report(output, {**value, 'budget_before': before}))
    report['budget_before'] = before
    try:
        report['budget_after'] = budget.budget_snapshot()
    except budget.BudgetError:
        report['budget_after'] = {'status': 'unavailable', 'note': 'Read-only quota snapshot failed; no reset or replacement was attempted.'}
    live.write_report(output, report)
    review_output = output.with_suffix('.review.json')
    live.write_report(review_output, live.review_template(report))
    print(json.dumps({'automatic_pass': report['automatic_pass'], 'whole_task_pass': report['whole_task_pass'],
                      'benchmark_scope': report['benchmark_scope'], 'summary_by_system': report['summary_by_system'],
                      'model_calls': report['model_calls'], 'estimated_model_cost_usd': report['model_api_cost_usd'],
                      'budget_stop': report['budget_stop'], 'provider_stop': report['provider_stop'],
                      'stop_reason': report['stop_reason'], 'manual_semantic_review': 'required',
                      'output': str(output), 'review_template': str(review_output)}, indent=2))
    if not report['automatic_pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
