from fastapi.testclient import TestClient
from api.index import app
import pytest
import backend.agent as agent

client = TestClient(app)

def test_health_declares_data_and_controller():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['data'] == 'synthetic'
    assert response.json()['deterministic_enabled'] is True

def test_api_rejects_unknown_execution_mode_and_executable_payload():
    assert client.post('/api/analyze', json={'question': 'activation', 'mode': 'shell'}).status_code == 422
    assert client.post('/api/analyze', json={'question': 'activation', 'sql': 'DROP TABLE users'}).status_code == 422
    assert client.post('/api/analyze', json={'question': 'x'*1001}).status_code == 422

def test_deterministic_public_request_has_verifiable_evidence():
    response = client.post('/api/analyze', json={'question': 'Why did activation fall last week?'})
    assert response.status_code == 200
    answer = response.json()
    assert answer['status'] == 'completed'
    assert answer['mode'] == 'deterministic'
    assert answer['metrics']['model_calls'] == 0
    assert answer['metrics']['estimated_cost_usd'] == 0
    assert len(answer['evidence']) == 2


@pytest.mark.parametrize('failure', [ValueError('private checksum details'), OSError('private filesystem path')])
def test_unavailable_dataset_returns_safe_json_and_recovers(monkeypatch, failure):
    with monkeypatch.context() as scoped:
        def fail():
            raise failure
        scoped.setattr(agent, 'default_dataset', fail)
        with TestClient(app, raise_server_exceptions=False) as isolated:
            response = isolated.post('/api/analyze', json={'question': 'Investigate activation'})
        assert response.status_code == 503
        assert response.json() == {'detail': 'The synthetic dataset is unavailable. Please try again later.'}
        assert 'private' not in response.text
    response = client.post('/api/analyze', json={'question': 'Investigate activation'})
    assert response.status_code == 200
    assert response.json()['status'] == 'completed'


def test_public_retail_endpoint_rejects_unknown_modes_and_arbitrary_data():
    for extra in [{'mode':'shell'}, {'source_path':'/etc/passwd'}, {'sql':'SELECT 1'}]:
        response=client.post('/api/retail/analyze',json={'question':'Compare sales',**extra})
        assert response.status_code == 422


def test_public_retail_unavailable_snapshot_returns_safe_json(monkeypatch):
    import backend.retail as retail
    def fail():
        raise agent.DatasetUnavailableError('The public retail dataset is unavailable. Please try again later.')
    monkeypatch.setattr(retail,'load_snapshot',fail)
    response=client.post('/api/retail/analyze',json={'question':'Compare sales'})
    assert response.status_code == 503
    assert response.json()['detail'].startswith('The public retail dataset is unavailable.')


def test_public_retail_endpoint_passes_live_mode_and_hashed_client(monkeypatch):
    import hashlib
    import backend.retail as retail
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('METRICPILOT_CLIENT_SALT', 'offline-test-salt')
    def capture(question, snapshot=None, mode='deterministic', client='local'):
        return {'question':question, 'mode':mode, 'client':client}
    monkeypatch.setattr(retail, 'run_retail_analysis', capture)
    response=client.post('/api/retail/analyze',json={'question':'Compare sales','mode':'live'})
    assert response.status_code == 200
    assert response.json() == {'question':'Compare sales','mode':'live',
                               'client':hashlib.sha256(b'offline-test-salttestclient').hexdigest()[:20]}


def test_public_retail_defaults_to_deterministic_mode(monkeypatch):
    import backend.retail as retail
    def capture(question, snapshot=None, mode='deterministic', client='local'):
        return {'mode':mode}
    monkeypatch.setattr(retail, 'run_retail_analysis', capture)
    assert client.post('/api/retail/analyze',json={'question':'Compare sales'}).json() == {'mode':'deterministic'}


def test_public_retail_uses_same_forwarded_client_quota_scope_as_synthetic(monkeypatch):
    import backend.retail as retail
    import api.index as api
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('METRICPILOT_CLIENT_SALT', 'offline-test-salt')
    def capture(question, mode='deterministic', **kwargs):
        return {'client':kwargs['client']}
    monkeypatch.setattr(retail, 'run_retail_analysis', capture)
    monkeypatch.setattr(api, 'run_analysis', capture)
    headers = {'x-forwarded-for':'198.51.100.20, 192.0.2.10'}
    retail_response = client.post('/api/retail/analyze',json={'question':'Compare sales'},headers=headers)
    synthetic_response = client.post('/api/analyze',json={'question':'Compare activation'},headers=headers)
    assert retail_response.status_code == synthetic_response.status_code == 200
    assert retail_response.json()['client'] == synthetic_response.json()['client']
    assert '198.51.100.20' not in retail_response.text
