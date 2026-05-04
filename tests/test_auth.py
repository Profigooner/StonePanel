def test_initial_status_not_setup(client):
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json()["setup_complete"] is False


def test_setup_password(client):
    resp = client.post("/api/auth/setup", json={"password": "testpass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_setup_password_too_short(client):
    resp = client.post("/api/auth/setup", json={"password": "abc"})
    assert resp.status_code == 400


def test_setup_twice_rejected(client):
    client.post("/api/auth/setup", json={"password": "testpass123"})
    resp = client.post("/api/auth/setup", json={"password": "another123"})
    assert resp.status_code == 400


def test_status_after_setup(client):
    client.post("/api/auth/setup", json={"password": "testpass123"})
    resp = client.get("/api/auth/status")
    assert resp.json()["setup_complete"] is True


def test_login_success(client):
    client.post("/api/auth/setup", json={"password": "testpass123"})
    resp = client.post("/api/auth/login", json={"password": "testpass123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    client.post("/api/auth/setup", json={"password": "testpass123"})
    resp = client.post("/api/auth/login", json={"password": "wrongpassword"})
    assert resp.status_code == 401


def test_login_before_setup(client):
    resp = client.post("/api/auth/login", json={"password": "testpass123"})
    assert resp.status_code == 400


def test_protected_endpoint_no_token(client):
    resp = client.get("/api/files/list")
    assert resp.status_code == 401


def test_protected_endpoint_invalid_token(client):
    headers = {"Authorization": "Bearer invalid-token"}
    resp = client.get("/api/files/list", headers=headers)
    assert resp.status_code == 401


def test_protected_endpoint_valid_token(client, auth_headers):
    resp = client.get("/api/files/list?path=/", headers=auth_headers)
    assert resp.status_code == 200
