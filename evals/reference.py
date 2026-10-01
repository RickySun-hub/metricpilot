"""Independent list-based references: no imports from application tools or SQL."""
from datetime import datetime, timedelta
from math import sqrt, erfc

_last_dataset = None
_event_index = {}

def events_for(dataset, user_id):
    global _last_dataset, _event_index
    if dataset is not _last_dataset:
        _event_index = {}
        for event in dataset['events']:
            _event_index.setdefault(event['user_id'], []).append(event)
        _last_dataset = dataset
    return _event_index.get(user_id, [])

def dt(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)

def cohort(dataset, period):
    start, end = (('2026-09-01', '2026-09-08') if period == 'before' else ('2026-09-08', '2026-09-15'))
    cutoff = dt(dataset['cutoff'])
    return [u for u in dataset['users'] if dt(start) <= dt(u['signup_at']) < dt(end)
            and dt(u['signup_at']) + timedelta(days=7) <= cutoff]

def outcome(dataset, user, anchor=None):
    begin = dt(anchor or user['signup_at'])
    end = begin + timedelta(days=7)
    return any(e['user_id'] == user['user_id'] and e['event_type'] == 'practice_complete'
               and begin <= dt(e['event_at']) < end and dt(e['event_at']) < dt(dataset['cutoff'])
               for e in events_for(dataset, user['user_id']))

def activation(dataset, user):
    begin = dt(user['signup_at'])
    end = begin + timedelta(days=7)
    events = [e for e in events_for(dataset, user['user_id']) if begin <= dt(e['event_at']) < end]
    starts = [e for e in events if e['event_type'] == 'practice_start']
    return any(e['event_type'] == 'practice_complete' and any(
        s['practice_session_id'] == e['practice_session_id'] and dt(s['event_at']) <= dt(e['event_at'])
        for s in starts) for e in events)

def metric(dataset):
    result = {}
    for period in ['before', 'after']:
        users = cohort(dataset, period)
        n = len(users)
        s = sum(activation(dataset, u) for u in users)
        result[period] = {'numerator': s, 'denominator': n, 'rate': s/n if n else None}
    result['delta_pp'] = 100 * (result['after']['rate'] - result['before']['rate'])
    return result

def funnel(dataset):
    result = {}
    for period in ['before', 'after']:
        users = cohort(dataset, period)
        started = completed = 0
        for u in users:
            begin = dt(u['signup_at'])
            end = begin + timedelta(days=7)
            events = [e for e in events_for(dataset, u['user_id']) if begin <= dt(e['event_at']) < end]
            starts = [e for e in events if e['event_type'] == 'practice_start']
            started += bool(starts)
            completed += any(e['event_type'] == 'practice_complete' and any(
                s['practice_session_id'] == e['practice_session_id'] and dt(s['event_at']) <= dt(e['event_at'])
                for s in starts) for e in events)
        n = len(users)
        result[period] = {'users': n, 'started': started, 'completed': completed,
                          'start_rate': started/n, 'completion_rate': completed/n}
    return result

def decomposition(dataset, segment='acquisition_channel'):
    groups = sorted({u[segment] for u in dataset['users']})
    cohorts = {p: cohort(dataset, p) for p in ['before', 'after']}
    rows = []
    for group in groups:
        rates, weights = {}, {}
        for p in cohorts:
            subset = [u for u in cohorts[p] if u[segment] == group]
            weights[p] = len(subset)/len(cohorts[p])
            rates[p] = sum(activation(dataset, u) for u in subset)/len(subset)
        rows.append({'segment': group, 'before_rate': rates['before'], 'after_rate': rates['after'],
                     'before_weight': weights['before'], 'after_weight': weights['after'],
                     'mix_pp': 100*(weights['after']-weights['before'])*(rates['after']+rates['before'])/2,
                     'within_pp': 100*(rates['after']-rates['before'])*(weights['after']+weights['before'])/2})
    return {'segments': rows, 'mix_pp': sum(r['mix_pp'] for r in rows),
            'within_pp': sum(r['within_pp'] for r in rows), 'delta_pp': metric(dataset)['delta_pp']}

def wilson(successes, n):
    z = 1.959963984540054
    p = successes/n
    center = (p+z*z/(2*n))/(1+z*z/n)
    width = z*sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return center-width, center+width

def experiment(dataset, experiment_id):
    users = {u['user_id']: u for u in dataset['users']}
    assignments = [a for a in dataset['experiment_assignments'] if a['experiment_id'] == experiment_id
                   and dt(a['assigned_at']) + timedelta(days=7) <= dt(dataset['cutoff'])]
    out = {}
    for variant in ['control', 'treatment']:
        group = [a for a in assignments if a['variant'] == variant]
        s = sum(outcome(dataset, users[a['user_id']], a['assigned_at']) for a in group)
        out[variant] = {'n': len(group), 'successes': s, 'rate': s/len(group)}
    nc, nt = out['control']['n'], out['treatment']['n']
    chi2 = ((nc-(nc+nt)/2)**2+(nt-(nc+nt)/2)**2)/((nc+nt)/2)
    out['srm_pvalue'] = erfc(sqrt(chi2/2))
    pc, pt = out['control']['rate'], out['treatment']['rate']
    lc, uc = wilson(out['control']['successes'], nc)
    lt, ut = wilson(out['treatment']['successes'], nt)
    diff = pt-pc
    out.update(effect_pp=100*diff,
               ci_low_pp=None if out['srm_pvalue'] < .001 else 100*(diff-sqrt((pt-lt)**2+(uc-pc)**2)),
               ci_high_pp=None if out['srm_pvalue'] < .001 else 100*(diff+sqrt((ut-pt)**2+(pc-lc)**2)),
               status='invalid' if out['srm_pvalue'] < .001 else 'valid')
    return out

def assert_fields(actual, expected, path='result'):
    """Compare required reference fields only; allow additional UI fields."""
    if isinstance(expected, dict):
        for key, value in expected.items():
            assert key in actual, f'{path}.{key} missing'
            assert_fields(actual[key], value, f'{path}.{key}')
    elif isinstance(expected, list):
        assert len(actual) == len(expected), f'{path} length'
        if expected and isinstance(expected[0], dict) and 'segment' in expected[0]:
            actual = sorted(actual, key=lambda x: x['segment'])
        for i, value in enumerate(expected):
            assert_fields(actual[i], value, f'{path}[{i}]')
    elif isinstance(expected, (int, float)):
        assert abs(actual-expected) <= 1e-8, f'{path}: {actual} != {expected}'
    else:
        assert actual == expected, f'{path}: {actual} != {expected}'
