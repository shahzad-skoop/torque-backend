def test_mock_login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@torque.local", "password": "ABC123ab#c"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "Bearer"
    assert "token" in payload
