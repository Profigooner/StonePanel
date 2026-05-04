from stonepanel.screen.service import ScreenService


# ---- Parsing unit tests (no subprocess needed) ----

def test_parse_screen_with_sessions():
    output = (
        "There are screens on:\n"
        "\t12345.my_app\t(05/04/2026 10:30:00 PM)\t(Detached)\n"
        "\t12346.web_server\t(Attached)\n"
        "2 Sockets in /run/screen/S-user.\n"
    )
    sessions = ScreenService.parse_screen(output)
    assert len(sessions) == 2
    assert sessions[0]["type"] == "screen"
    assert sessions[0]["name"] == "my_app"
    assert sessions[0]["id"] == "12345.my_app"
    assert sessions[0]["status"] == "Detached"
    assert sessions[1]["name"] == "web_server"
    assert sessions[1]["status"] == "Attached"


def test_parse_screen_empty():
    output = "No Sockets found in /run/screen/S-user.\n"
    sessions = ScreenService.parse_screen(output)
    assert sessions == []


def test_parse_screen_dead():
    output = (
        "There are screens on:\n"
        "\t99999.dead_session\t(Dead ???)\n"
        "Remove dead screens with 'screen -wipe'.\n"
    )
    sessions = ScreenService.parse_screen(output)
    assert len(sessions) == 1
    assert sessions[0]["status"] == "Dead"


def test_parse_tmux_with_sessions():
    output = "dev\t2\t1714880000\t0\nweb\t3\t1714880100\t1\n"
    sessions = ScreenService.parse_tmux(output)
    assert len(sessions) == 2
    assert sessions[0]["type"] == "tmux"
    assert sessions[0]["name"] == "dev"
    assert sessions[0]["windows"] == 2
    assert sessions[0]["status"] == "Detached"
    assert sessions[1]["name"] == "web"
    assert sessions[1]["windows"] == 3
    assert sessions[1]["status"] == "Attached"


def test_parse_tmux_empty():
    sessions = ScreenService.parse_tmux("")
    assert sessions == []


def test_parse_tmux_single():
    output = "main\t1\t1714880000\t0\n"
    sessions = ScreenService.parse_tmux(output)
    assert len(sessions) == 1
    assert sessions[0]["name"] == "main"
    assert sessions[0]["status"] == "Detached"


# ---- API endpoint tests (screen/tmux may not be installed) ----

def test_list_sessions_api(client, auth_headers):
    resp = client.get("/api/screen/sessions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


def test_check_available_api(client, auth_headers):
    resp = client.get("/api/screen/available", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "screen" in data
    assert "tmux" in data
    assert isinstance(data["screen"], bool)
    assert isinstance(data["tmux"], bool)


def test_create_session_invalid_type(client, auth_headers):
    resp = client.post(
        "/api/screen/sessions",
        json={"type": "invalid", "name": "test"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_session_empty_name(client, auth_headers):
    resp = client.post(
        "/api/screen/sessions",
        json={"type": "screen", "name": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_no_auth_rejected(client):
    resp = client.get("/api/screen/sessions")
    assert resp.status_code == 401
