from unittest.mock import AsyncMock, patch

import pytest

from stonepanel.services.service import SystemdService, _validate_name


SAMPLE_LIST_UNITS = """  ssh.service                loaded active running OpenBSD Secure Shell server
  nginx.service              loaded active running A high performance web server
  cron.service               loaded active running Regular background program processing daemon
  mysql.service              loaded failed failed  MySQL Community Server
  docker.service             loaded active exited  Docker Application Container Engine
"""

SAMPLE_SHOW_OUTPUT = """Id=nginx.service
Description=A high performance web server
LoadState=loaded
ActiveState=active
SubState=running
MainPID=1234
MemoryCurrent=12345678
ExecMainStartTimestamp=Mon 2025-01-01 00:00:00 UTC
UnitFileState=enabled
FragmentPath=/lib/systemd/system/nginx.service
"""

SAMPLE_JOURNAL_JSON = """{"__REALTIME_TIMESTAMP":"1704067200000000","MESSAGE":"Starting nginx...","PRIORITY":"6","_PID":"1234","_SYSTEMD_UNIT":"nginx.service"}
{"__REALTIME_TIMESTAMP":"1704067201000000","MESSAGE":"Started nginx.","PRIORITY":"6","_PID":"1234","_SYSTEMD_UNIT":"nginx.service"}
{"__REALTIME_TIMESTAMP":"1704067202000000","MESSAGE":"Error: bind failed","PRIORITY":"3","_PID":"1234","_SYSTEMD_UNIT":"nginx.service"}
"""


class TestValidateName:
    def test_valid_names(self):
        valid = [
            "nginx.service",
            "sshd",
            "my-app.service",
            "user@1000.service",
            "php8.1-fpm.service",
        ]
        for name in valid:
            assert _validate_name(name), f"Expected valid: {name}"

    def test_invalid_names(self):
        invalid = [
            "",
            "nginx; rm -rf /",
            "$(whoami)",
            "nginx\nservice",
            "../../../etc/passwd",
            "name with spaces",
            "name|pipe",
        ]
        for name in invalid:
            assert not _validate_name(name), f"Expected invalid: {name}"


class TestParseUnits:
    def test_parse_units(self):
        units = SystemdService.parse_units(SAMPLE_LIST_UNITS)
        assert len(units) == 5

    def test_parse_unit_fields(self):
        units = SystemdService.parse_units(SAMPLE_LIST_UNITS)
        nginx = [u for u in units if "nginx" in u["name"]][0]
        assert nginx["load"] == "loaded"
        assert nginx["active"] == "active"
        assert nginx["sub"] == "running"
        assert "web server" in nginx["description"].lower()

    def test_parse_failed_unit(self):
        units = SystemdService.parse_units(SAMPLE_LIST_UNITS)
        mysql = [u for u in units if "mysql" in u["name"]][0]
        assert mysql["active"] == "failed"

    def test_parse_empty(self):
        assert SystemdService.parse_units("") == []


class TestParseShow:
    def test_parse_show(self):
        props = SystemdService.parse_show(SAMPLE_SHOW_OUTPUT)
        assert props["Id"] == "nginx.service"
        assert props["ActiveState"] == "active"
        assert props["MainPID"] == "1234"
        assert props["UnitFileState"] == "enabled"

    def test_parse_show_empty(self):
        assert SystemdService.parse_show("") == {}


class TestParseLogs:
    def test_parse_logs(self):
        logs = SystemdService.parse_logs(SAMPLE_JOURNAL_JSON)
        assert len(logs) == 3

    def test_log_fields(self):
        logs = SystemdService.parse_logs(SAMPLE_JOURNAL_JSON)
        assert logs[0]["message"] == "Starting nginx..."
        assert logs[0]["priority"] == 6

    def test_error_priority(self):
        logs = SystemdService.parse_logs(SAMPLE_JOURNAL_JSON)
        error = logs[2]
        assert error["priority"] == 3
        assert "Error" in error["message"]

    def test_parse_empty_logs(self):
        assert SystemdService.parse_logs("") == []

    def test_parse_invalid_json(self):
        assert SystemdService.parse_logs("not json\nalso not json") == []


class TestServicesAPI:
    def test_list_units(self, client, auth_headers):
        with patch.object(SystemdService, "list_services", new_callable=AsyncMock, return_value=SystemdService.parse_units(SAMPLE_LIST_UNITS)):
            resp = client.get("/api/services/units", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "units" in data
            assert len(data["units"]) == 5

    def test_list_units_with_state(self, client, auth_headers):
        running = [u for u in SystemdService.parse_units(SAMPLE_LIST_UNITS) if u["sub"] == "running"]
        with patch.object(SystemdService, "list_services", new_callable=AsyncMock, return_value=running):
            resp = client.get("/api/services/units?state=running", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["units"]) == 3

    def test_get_unit(self, client, auth_headers):
        status = {
            "name": "nginx.service",
            "description": "A high performance web server",
            "load_state": "loaded",
            "active_state": "active",
            "sub_state": "running",
            "main_pid": 1234,
            "memory": "12345678",
            "started_at": "Mon 2025-01-01 00:00:00 UTC",
            "enabled": True,
            "unit_file": "/lib/systemd/system/nginx.service",
        }
        with patch.object(SystemdService, "get_status", new_callable=AsyncMock, return_value=status):
            resp = client.get("/api/services/units/nginx.service", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["active_state"] == "active"
            assert data["main_pid"] == 1234

    def test_get_unit_not_found(self, client, auth_headers):
        with patch.object(SystemdService, "get_status", new_callable=AsyncMock, return_value=None):
            resp = client.get("/api/services/units/nonexistent.service", headers=auth_headers)
            assert resp.status_code == 404

    def test_get_unit_invalid_name(self, client, auth_headers):
        resp = client.get("/api/services/units/$(whoami)", headers=auth_headers)
        assert resp.status_code == 400

    def test_action(self, client, auth_headers):
        with patch.object(SystemdService, "action", new_callable=AsyncMock, return_value=(True, "Service restart successful")):
            resp = client.post("/api/services/units/nginx.service/restart", headers=auth_headers)
            assert resp.status_code == 200

    def test_action_invalid_name(self, client, auth_headers):
        resp = client.post("/api/services/units/$(whoami)/restart", headers=auth_headers)
        assert resp.status_code == 400

    def test_action_invalid_action(self, client, auth_headers):
        resp = client.post("/api/services/units/nginx.service/destroy", headers=auth_headers)
        assert resp.status_code == 400

    def test_action_failure(self, client, auth_headers):
        with patch.object(SystemdService, "action", new_callable=AsyncMock, return_value=(False, "Permission denied")):
            resp = client.post("/api/services/units/nginx.service/stop", headers=auth_headers)
            assert resp.status_code == 500

    def test_get_logs(self, client, auth_headers):
        logs = SystemdService.parse_logs(SAMPLE_JOURNAL_JSON)
        with patch.object(SystemdService, "get_logs", new_callable=AsyncMock, return_value=logs):
            resp = client.get("/api/services/units/nginx.service/logs?lines=50", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["logs"]) == 3

    def test_available(self, client, auth_headers):
        with patch.object(SystemdService, "is_available", new_callable=AsyncMock, return_value=True):
            resp = client.get("/api/services/available", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["available"] is True

    def test_requires_auth(self, client):
        resp = client.get("/api/services/units")
        assert resp.status_code == 401
