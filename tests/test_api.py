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


def test_public_retail_endpoint_rejects_live_and_arbitrary_data():
    for extra in [{'mode':'live'}, {'source_path':'/etc/passwd'}, {'sql':'SELECT 1'}]:
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
