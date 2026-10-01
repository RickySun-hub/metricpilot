from fastapi.testclient import TestClient
from api.index import app

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
