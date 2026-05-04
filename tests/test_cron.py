from unittest.mock import AsyncMock, patch

import pytest

from stonepanel.cron.service import CronService, _human_schedule


SAMPLE_CRONTAB = """# System backup
0 2 * * * /usr/bin/backup.sh
*/5 * * * * /usr/local/bin/check-health.sh
# Disabled log rotation
# 0 0 * * 0 /usr/bin/logrotate /etc/logrotate.conf
MAILTO=admin@example.com
"""


class TestParseCrontab:
    def test_parse_active_jobs(self):
        jobs = CronService.parse_crontab(SAMPLE_CRONTAB)
        active = [j for j in jobs if j["enabled"]]
        assert len(active) == 2

    def test_parse_job_fields(self):
        jobs = CronService.parse_crontab(SAMPLE_CRONTAB)
        backup = jobs[0]
        assert backup["schedule"] == "0 2 * * *"
        assert backup["command"] == "/usr/bin/backup.sh"
        assert backup["description"] == "System backup"
        assert backup["enabled"] is True
        assert backup["id"]

    def test_parse_disabled_job(self):
        jobs = CronService.parse_crontab(SAMPLE_CRONTAB)
        disabled = [j for j in jobs if not j["enabled"]]
        assert len(disabled) == 1
        assert disabled[0]["command"] == "/usr/bin/logrotate /etc/logrotate.conf"
        assert disabled[0]["schedule"] == "0 0 * * 0"
        assert disabled[0]["description"] == "Disabled log rotation"

    def test_parse_skips_env_vars(self):
        jobs = CronService.parse_crontab(SAMPLE_CRONTAB)
        commands = [j["command"] for j in jobs]
        assert not any("MAILTO" in c for c in commands)

    def test_parse_empty(self):
        assert CronService.parse_crontab("") == []
        assert CronService.parse_crontab("no crontab for user") == []

    def test_deterministic_id(self):
        jobs1 = CronService.parse_crontab(SAMPLE_CRONTAB)
        jobs2 = CronService.parse_crontab(SAMPLE_CRONTAB)
        assert jobs1[0]["id"] == jobs2[0]["id"]

    def test_different_lines_different_ids(self):
        jobs = CronService.parse_crontab(SAMPLE_CRONTAB)
        ids = [j["id"] for j in jobs]
        assert len(ids) == len(set(ids))


class TestValidateSchedule:
    def test_valid_expressions(self):
        valid_cases = [
            "* * * * *",
            "0 2 * * *",
            "*/5 * * * *",
            "0 0 1 * *",
            "30 4 1-15 * 1-5",
            "0 0 * * 0,6",
        ]
        for expr in valid_cases:
            ok, msg = CronService.validate_schedule(expr)
            assert ok, f"Expected valid: {expr}, got: {msg}"

    def test_invalid_expressions(self):
        invalid_cases = [
            ("", "Must have exactly 5 fields"),
            ("* * *", "Must have exactly 5 fields"),
            ("60 * * * *", "minute value 60 out of range"),
            ("* 25 * * *", "hour value 25 out of range"),
            ("* * 32 * *", "day value 32 out of range"),
            ("* * * 13 *", "month value 13 out of range"),
            ("* * * * 8", "weekday value 8 out of range"),
            ("abc * * * *", "Invalid minute"),
        ]
        for expr, expected_fragment in invalid_cases:
            ok, msg = CronService.validate_schedule(expr)
            assert not ok, f"Expected invalid: {expr}"
            assert expected_fragment.lower() in msg.lower(), f"Expected '{expected_fragment}' in '{msg}'"


class TestHumanSchedule:
    def test_every_minute(self):
        assert _human_schedule("*", "*", "*", "*", "*") == "Every minute"

    def test_every_hour(self):
        assert _human_schedule("0", "*", "*", "*", "*") == "Every hour"

    def test_every_n_minutes(self):
        assert "5 minutes" in _human_schedule("*/5", "*", "*", "*", "*")

    def test_daily(self):
        result = _human_schedule("0", "2", "*", "*", "*")
        assert "2:00" in result

    def test_weekdays(self):
        result = _human_schedule("30", "9", "*", "*", "1-5")
        assert "Weekdays" in result

    def test_monthly(self):
        result = _human_schedule("0", "0", "1", "*", "*")
        assert "Monthly" in result


class TestCronAPI:
    def test_list_jobs(self, client, auth_headers):
        with patch.object(CronService, "_read_crontab", new_callable=AsyncMock, return_value=SAMPLE_CRONTAB):
            resp = client.get("/api/cron/jobs", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "jobs" in data
            assert len(data["jobs"]) == 3

    def test_create_job(self, client, auth_headers):
        with patch.object(CronService, "_read_crontab", new_callable=AsyncMock, return_value=""), \
             patch.object(CronService, "_write_crontab", new_callable=AsyncMock, return_value=True):
            resp = client.post("/api/cron/jobs", json={
                "minute": "0",
                "hour": "3",
                "day": "*",
                "month": "*",
                "weekday": "*",
                "command": "/usr/bin/test.sh",
                "description": "Test job",
            }, headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["schedule"] == "0 3 * * *"
            assert data["command"] == "/usr/bin/test.sh"
            assert data["enabled"] is True

    def test_create_job_invalid_schedule(self, client, auth_headers):
        resp = client.post("/api/cron/jobs", json={
            "minute": "60",
            "hour": "0",
            "day": "*",
            "month": "*",
            "weekday": "*",
            "command": "/usr/bin/test.sh",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_job_empty_command(self, client, auth_headers):
        resp = client.post("/api/cron/jobs", json={
            "minute": "*",
            "hour": "*",
            "day": "*",
            "month": "*",
            "weekday": "*",
            "command": "",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_delete_job(self, client, auth_headers):
        crontab = "0 2 * * * /usr/bin/backup.sh\n"
        jobs = CronService.parse_crontab(crontab)
        job_id = jobs[0]["id"]

        with patch.object(CronService, "_read_crontab", new_callable=AsyncMock, return_value=crontab), \
             patch.object(CronService, "_write_crontab", new_callable=AsyncMock, return_value=True):
            resp = client.delete(f"/api/cron/jobs/{job_id}", headers=auth_headers)
            assert resp.status_code == 200

    def test_delete_job_not_found(self, client, auth_headers):
        with patch.object(CronService, "_read_crontab", new_callable=AsyncMock, return_value=""):
            resp = client.delete("/api/cron/jobs/nonexistent", headers=auth_headers)
            assert resp.status_code == 404

    def test_toggle_job(self, client, auth_headers):
        crontab = "0 2 * * * /usr/bin/backup.sh\n"
        jobs = CronService.parse_crontab(crontab)
        job_id = jobs[0]["id"]

        with patch.object(CronService, "_read_crontab", new_callable=AsyncMock, return_value=crontab), \
             patch.object(CronService, "_write_crontab", new_callable=AsyncMock, return_value=True):
            resp = client.post(f"/api/cron/jobs/{job_id}/toggle", json={"enabled": False}, headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "disabled"

    def test_validate_endpoint(self, client, auth_headers):
        resp = client.post("/api/cron/validate", json={"expression": "0 2 * * *"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    def test_validate_invalid(self, client, auth_headers):
        resp = client.post("/api/cron/validate", json={"expression": "bad"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False

    def test_requires_auth(self, client):
        resp = client.get("/api/cron/jobs")
        assert resp.status_code == 401
