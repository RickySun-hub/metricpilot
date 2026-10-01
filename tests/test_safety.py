"""Mock provider failures; none of these tests issue paid model requests."""
import pytest
import backend.agent as agent
from backend.data import generate_dataset
from backend.tools import ToolError

@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setattr(agent, 'live_available', lambda: True)
    monkeypatch.setattr(agent, 'reserve', lambda **kwargs: None)
    return generate_dataset(users=100)

def action(name='finish', **kwargs):
    return {'action': name, 'segment': kwargs.get('segment', 'acquisition_channel'),
            'experiment_id': 'onboarding_valid', 'reason': 'Mock provider output'}, {}

def test_live_mock_cannot_finish_without_evidence(sandbox, monkeypatch):
    monkeypatch.setattr(agent, 'choose_action', lambda state: action())
    report = agent.run_analysis('Investigate activation', mode='live', dataset=sandbox)
    assert report['status'] == 'verification_failed'
    assert report['evidence'] == []

def test_live_mock_repeated_tool_is_rejected(sandbox, monkeypatch):
    monkeypatch.setattr(agent, 'choose_action', lambda state: action('compare_metric'))
    report = agent.run_analysis('Investigate activation', mode='live', dataset=sandbox)
    assert report['status'] == 'invalid_data'
    assert 'Repeated identical' in report['summary']

def test_live_mock_tool_dimension_cannot_inject_sql(sandbox, monkeypatch):
    monkeypatch.setattr(agent, 'choose_action', lambda state: action('decompose_change', segment='postal_code; DROP TABLE users'))
    report = agent.run_analysis('Investigate activation', mode='live', dataset=sandbox)
    assert report['status'] == 'invalid_data'
    assert report['findings'] == []

def test_live_mock_cost_limit_stops_before_tool(sandbox, monkeypatch):
    monkeypatch.setattr(agent, 'choose_action', lambda state: (action('compare_metric')[0], {'prompt_tokens': 1000000, 'completion_tokens': 1}))
    report = agent.run_analysis('Investigate activation', mode='live', dataset=sandbox)
    assert report['status'] == 'budget_exceeded'
    assert report['evidence'] == []

def test_live_mock_tool_budget_stops_sixth_distinct_call(sandbox, monkeypatch):
    steps = [action('compare_metric')[0], action('analyze_funnel')[0],
             action('decompose_change')[0], action('decompose_change', segment='signup_device')[0],
             action('check_experiment')[0], {**action('check_experiment')[0], 'experiment_id': 'onboarding_srm'}]
    def choose(state):
        return steps[state['metrics']['model_calls']], {}
    monkeypatch.setattr(agent, 'choose_action', choose)
    report = agent.run_analysis('Investigate activation', mode='live', dataset=sandbox)
    assert report['status'] == 'budget_exceeded'
    assert report['metrics']['tool_calls'] <= 5
    assert report['metrics']['model_calls'] <= 6

def test_tool_failure_cannot_produce_success(sandbox, monkeypatch):
    def fail(self):
        raise ToolError('Injected database failure')
    monkeypatch.setattr(agent.Analytics, 'compare_metric', fail)
    report = agent.run_analysis('Investigate activation', mode='deterministic', dataset=sandbox)
    assert report['status'] == 'invalid_data'
    assert report['findings'] == []

@pytest.mark.parametrize('finding', [
    {'evidence_id': 'invented', 'field_path': 'rate', 'value': .5, 'scale': 1},
    {'evidence_id': 'real', 'field_path': 'rate', 'value': .9, 'scale': 1},
])
def test_unverifiable_numeric_findings_rejected(finding):
    with pytest.raises(ToolError):
        agent.validate_findings([finding], [{'id': 'real', 'result': {'rate': .5}}])
