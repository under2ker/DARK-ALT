from fastapi.testclient import TestClient
from dark_alt.main import app

def test_readiness_and_metrics_expose_operational_signals():
    with TestClient(app) as client:
        ready=client.get('/api/ready')
        assert ready.status_code==200 and ready.json()['database']=='ok'
        health=client.get('/api/health')
        assert health.headers['x-content-type-options']=='nosniff'
        assert health.headers['x-frame-options']=='DENY'
        assert health.headers['x-request-id']
        metrics=client.get('/metrics')
        assert metrics.status_code==200 and 'dark_alt_wallpapers' in metrics.text
