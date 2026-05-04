import time


def test_create_session(client, auth_headers):
    resp = client.post("/api/terminal/sessions", headers=auth_headers)
    assert resp.status_code == 200
    assert "session_id" in resp.json()


def test_create_session_no_auth(client):
    resp = client.post("/api/terminal/sessions")
    assert resp.status_code == 401


def test_list_sessions(client, auth_headers):
    client.post("/api/terminal/sessions", headers=auth_headers)
    resp = client.get("/api/terminal/sessions", headers=auth_headers)
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) >= 1
    assert sessions[0]["alive"] is True


def test_kill_session(client, auth_headers):
    resp = client.post("/api/terminal/sessions", headers=auth_headers)
    sid = resp.json()["session_id"]
    resp = client.delete(f"/api/terminal/sessions/{sid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "killed"


def test_kill_nonexistent_session(client, auth_headers):
    resp = client.delete(
        "/api/terminal/sessions/nonexistent", headers=auth_headers
    )
    assert resp.json()["status"] == "not_found"


def test_websocket_no_token(client, auth_headers):
    # Create a real session first
    resp = client.post("/api/terminal/sessions", headers=auth_headers)
    sid = resp.json()["session_id"]
    with client.websocket_connect(f"/api/terminal/ws/{sid}") as ws:
        msg = ws.receive_json()
        assert msg["error"] == "Unauthorized"


def test_websocket_invalid_session(client, auth_token):
    with client.websocket_connect(
        f"/api/terminal/ws/nonexistent?token={auth_token}"
    ) as ws:
        msg = ws.receive_json()
        assert msg["error"] == "Session not found"


def test_websocket_connect_and_receive(client, auth_token, auth_headers):
    resp = client.post("/api/terminal/sessions", headers=auth_headers)
    sid = resp.json()["session_id"]
    with client.websocket_connect(
        f"/api/terminal/ws/{sid}?token={auth_token}"
    ) as ws:
        # Shell should produce output (prompt) on startup
        data = ws.receive_bytes()
        assert len(data) > 0


def test_websocket_send_command(client, auth_token, auth_headers):
    resp = client.post("/api/terminal/sessions", headers=auth_headers)
    sid = resp.json()["session_id"]
    with client.websocket_connect(
        f"/api/terminal/ws/{sid}?token={auth_token}"
    ) as ws:
        # Consume initial shell output
        time.sleep(0.3)
        ws.receive_bytes()

        # Send command
        ws.send_json({"type": "input", "data": "echo STONEPANEL_TEST_42\n"})
        time.sleep(0.5)

        # Collect output
        output = b""
        for _ in range(10):
            try:
                chunk = ws.receive_bytes()
                output += chunk
                if b"STONEPANEL_TEST_42" in output:
                    break
            except Exception:
                break

        assert b"STONEPANEL_TEST_42" in output


def test_websocket_resize(client, auth_token, auth_headers):
    resp = client.post("/api/terminal/sessions", headers=auth_headers)
    sid = resp.json()["session_id"]
    with client.websocket_connect(
        f"/api/terminal/ws/{sid}?token={auth_token}"
    ) as ws:
        ws.receive_bytes()  # consume initial output
        # Resize should not crash
        ws.send_json({"type": "resize", "rows": 40, "cols": 120})
        time.sleep(0.2)
        # Session should still be alive — send a command after resize
        ws.send_json({"type": "input", "data": "echo RESIZED\n"})
        time.sleep(0.3)
        output = b""
        for _ in range(5):
            try:
                chunk = ws.receive_bytes()
                output += chunk
                if b"RESIZED" in output:
                    break
            except Exception:
                break
        assert b"RESIZED" in output
