"""SQL answers checked against independent list arithmetic and trusted intervals."""
import copy
from datetime import timedelta
import pytest
from backend.data import generate_dataset
from backend.tools import Analytics
from evals import reference

@pytest.fixture(scope='module')
def dataset():
    return generate_dataset(seed=654321, users=400)

@pytest.mark.parametrize('seed', [1, 42, 9001])
def test_metric_matches_independent_reference(seed):
    data = generate_dataset(seed=seed, users=300)
    tool = Analytics(data)
    reference.assert_fields(tool.compare_metric()['result'], reference.metric(data))

def test_funnel_requires_order_and_matching_session(dataset):
    data = copy.deepcopy(dataset)
    user = reference.cohort(data, 'before')[0]
    data['events'] = [e for e in data['events'] if e['user_id'] != user['user_id']]
    data['events'].extend([
        {'event_id': 'bad-start', 'user_id': user['user_id'], 'event_at': (reference.dt(user['signup_at'])+timedelta(hours=1)).isoformat(), 'event_type': 'practice_start', 'practice_session_id': 'session-a'},
        {'event_id': 'bad-complete', 'user_id': user['user_id'], 'event_at': (reference.dt(user['signup_at'])+timedelta(hours=2)).isoformat(), 'event_type': 'practice_complete', 'practice_session_id': 'session-b'},
    ])
    reference.assert_fields(Analytics(data).analyze_funnel()['result'], reference.funnel(data))

@pytest.mark.parametrize('segment', ['acquisition_channel', 'signup_device'])
def test_exact_decomposition(dataset, segment):
    result = Analytics(dataset).decompose_change(segment=segment)['result']
    reference.assert_fields(result, reference.decomposition(dataset, segment))
    assert result['mix_pp']+result['within_pp'] == pytest.approx(result['delta_pp'], abs=1e-9)

@pytest.mark.parametrize('experiment_id', ['onboarding_valid', 'onboarding_srm'])
def test_experiment_numeric_fields(dataset, experiment_id):
    result = Analytics(dataset).check_experiment(experiment_id=experiment_id)['result']
    reference.assert_fields(result, reference.experiment(dataset, experiment_id))

def test_interval_matches_statsmodels(dataset):
    from statsmodels.stats.proportion import confint_proportions_2indep
    result = Analytics(dataset).check_experiment(experiment_id='onboarding_valid')['result']
    c, t = result['control'], result['treatment']
    low, high = confint_proportions_2indep(t['successes'], t['n'], c['successes'], c['n'], method='newcomb', compare='diff')
    assert result['ci_low_pp'] == pytest.approx(low*100, abs=1e-8)
    assert result['ci_high_pp'] == pytest.approx(high*100, abs=1e-8)

def test_invalid_segment_rejected(dataset):
    with pytest.raises(ValueError):
        Analytics(dataset).decompose_change(segment='postal_code; DROP TABLE users')

def test_unknown_experiment_rejected(dataset):
    with pytest.raises(ValueError):
        Analytics(dataset).check_experiment(experiment_id='unknown')

def test_empty_dataset_does_not_report_success(dataset):
    data = dict(dataset, users=[], events=[], experiment_assignments=[])
    with pytest.raises(ValueError):
        Analytics(data).compare_metric()

def test_generator_reproducible_and_isolated_seeds():
    assert generate_dataset(seed=1, users=100) == generate_dataset(seed=1, users=100)
    assert generate_dataset(seed=1, users=100) != generate_dataset(seed=2, users=100)
