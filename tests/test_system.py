def test_system_info(client, auth_headers):
    resp = client.get("/api/system/info", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "hostname" in data
    assert "os" in data
    assert "cpu_count" in data
    assert data["cpu_count"] >= 1
    assert data["total_memory"] > 0
    assert data["uptime"] > 0


def test_system_stats(client, auth_headers):
    resp = client.get("/api/system/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu_percent" in data
    assert "memory" in data
    assert "disk" in data
    assert "network" in data
    assert 0 <= data["memory"]["percent"] <= 100
    assert 0 <= data["disk"]["percent"] <= 100


def test_system_processes(client, auth_headers):
    resp = client.get("/api/system/processes", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "processes" in data
    assert len(data["processes"]) > 0
    proc = data["processes"][0]
    assert "pid" in proc
    assert "name" in proc


def test_system_processes_sort_memory(client, auth_headers):
    resp = client.get(
        "/api/system/processes?sort_by=memory&limit=5", headers=auth_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["processes"]) <= 5


def test_system_no_auth(client):
    resp = client.get("/api/system/info")
    assert resp.status_code == 401


def test_frontend_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"StonePanel" in resp.content
