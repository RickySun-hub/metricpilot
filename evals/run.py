"""Run synthetic regressions: python -m evals.run --mode deterministic --split test."""
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
    parser.add_argument('--allow-paid', action='store_true')
    args = parser.parse_args()
    if args.mode == 'live':
        parser.error('Live benchmark is not implemented; --allow-paid does not fabricate model evidence.')
    if not 1 <= args.repeats <= 5:
        parser.error('--repeats must be 1..5')
    from backend.data import generate_dataset
    from backend.agent import run_analysis
    manifest_path = ROOT / 'evals/cases.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    assert manifest_hash == manifest_path.with_suffix('.sha256').read_text().strip(), 'Manifest changed: document exposure and refreeze deliberately.'
    cases = [c for c in json.loads(manifest_bytes)['cases'] if args.split == 'all' or c['split'] == args.split]
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
              'manifest_sha256': manifest_hash, 'code_sha': revision, 'working_tree_dirty': dirty,
              'source_sha256': source_hashes, 'model': None, 'model_calls': 0, 'model_tokens': 0,
              'model_api_cost_usd': 0, 'runs': runs,
              'omitted_checks': ['Live-model correctness and nondeterminism', 'Single-pass model baseline', 'Manual narrative review', 'Public deployment validation'],
              'gate_scope': 'Numerical/controller regression only; not the full release gate',
              'protocol_notes': ['Before the first agent benchmark execution, SRM terminal status aligned with invalid_data; unnamed nonexistent experiment aligned with needs_clarification. Manifest questions, seeds and split unchanged.'],
              'passed': all(r['passed'] == r['total'] for r in runs)}
    output = ROOT / 'evals/results/deterministic.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'runs': [{'passed': r['passed'], 'total': r['total']} for r in runs], 'output': str(output)}, indent=2))
    if not report['passed']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
