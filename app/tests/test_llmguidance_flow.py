import json
from app_ui.app import app


def test_verify_endpoint_requires_secret():
    client = app.test_client()
    resp = client.post('/internal/llmguidance/verify-auth0-token', json={"token": "x"})
    assert resp.status_code == 403 or resp.status_code == 400
    data = resp.get_json()
    assert data is not None
    assert data.get("valid") is False
