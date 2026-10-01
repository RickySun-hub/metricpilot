"""Contract violations must fail before query execution."""
import copy
import pytest
from backend.data import generate_dataset
from backend.tools import Analytics

@pytest.fixture(scope='module')
def original():
    return generate_dataset(seed=321, users=100)

@pytest.mark.parametrize('violation', ['user_duplicate', 'event_duplicate', 'foreign_user', 'assignment_duplicate', 'allocation'])
def test_contract_violations_rejected(original, violation):
    data = copy.deepcopy(original)
    if violation == 'user_duplicate':
        data['users'].append(copy.deepcopy(data['users'][0]))
    elif violation == 'event_duplicate':
        data['events'].append(copy.deepcopy(data['events'][0]))
    elif violation == 'foreign_user':
        data['events'][0]['user_id'] = 'does-not-exist'
    elif violation == 'assignment_duplicate':
        data['experiment_assignments'].append(copy.deepcopy(data['experiment_assignments'][0]))
    else:
        data['experiment_assignments'][0]['expected_allocation'] = .7
    with pytest.raises(ValueError):
        Analytics(data)

def test_immature_cohort_excluded(original):
    data = copy.deepcopy(original)
    data['cutoff'] = '2026-09-08T00:00:00'
    with pytest.raises(ValueError):
        Analytics(data).compare_metric()

def test_missing_segment_denominator_blocks_decomposition(original):
    data = copy.deepcopy(original)
    for u in data['users']:
        if u['signup_at'] >= '2026-09-08':
            u['acquisition_channel'] = 'organic'
    with pytest.raises(ValueError):
        Analytics(data).decompose_change()
