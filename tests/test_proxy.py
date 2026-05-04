import json
from unittest.mock import AsyncMock, patch

import pytest


RULE_DATA = {
    "name": "Test Web App",
    "protocol": "http",
    "listen_port": 8080,
    "domain": "app.example.com",
    "path_prefix": "/",
    "upstreams": [
        {"address": "192.168.1.10:3000", "weight": 1},
        {"address": "192.168.1.11:3000", "weight": 2},
    ],
    "load_balance": "round_robin",
    "waf_enabled": False,
}


class TestProxyRuleCRUD:
    def test_list_rules_empty(self, client, auth_headers):
        resp = client.get("/api/proxy/rules", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["rules"] == []

    def test_create_rule(self, client, auth_headers):
        resp = client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Web App"
        assert data["protocol"] == "http"
        assert data["listen_port"] == 8080
        assert data["domain"] == "app.example.com"
        assert len(data["upstreams"]) == 2
        assert data["id"]

    def test_list_rules_after_create(self, client, auth_headers):
        client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        resp = client.get("/api/proxy/rules", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["rules"]) == 1

    def test_get_rule(self, client, auth_headers):
        create_resp = client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        rule_id = create_resp.json()["id"]
        resp = client.get(f"/api/proxy/rules/{rule_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Web App"

    def test_get_rule_not_found(self, client, auth_headers):
        resp = client.get("/api/proxy/rules/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_rule(self, client, auth_headers):
        create_resp = client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        rule_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/proxy/rules/{rule_id}",
            json={"name": "Updated Name", "listen_port": 9090},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["listen_port"] == 9090

    def test_delete_rule(self, client, auth_headers):
        create_resp = client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        rule_id = create_resp.json()["id"]
        resp = client.delete(f"/api/proxy/rules/{rule_id}", headers=auth_headers)
        assert resp.status_code == 200
        # Verify deleted
        resp = client.get(f"/api/proxy/rules/{rule_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_rule_not_found(self, client, auth_headers):
        resp = client.delete("/api/proxy/rules/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_enable_disable_rule(self, client, auth_headers):
        create_resp = client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        rule_id = create_resp.json()["id"]

        # Disable
        resp = client.post(f"/api/proxy/rules/{rule_id}/disable", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        # Enable
        resp = client.post(f"/api/proxy/rules/{rule_id}/enable", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_requires_auth(self, client):
        resp = client.get("/api/proxy/rules")
        assert resp.status_code == 401


class TestProxyCaddyConfig:
    def test_build_http_config(self, client, auth_headers):
        client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        service = client.app.state.proxy_service
        config = service.build_caddy_config()
        assert "apps" in config
        assert "http" in config["apps"]
        servers = config["apps"]["http"]["servers"]
        assert "srv_8080" in servers
        server = servers["srv_8080"]
        assert server["listen"] == [":8080"]
        assert len(server["routes"]) == 1

    def test_build_config_disabled_rules_excluded(self, client, auth_headers):
        resp = client.post("/api/proxy/rules", json=RULE_DATA, headers=auth_headers)
        rule_id = resp.json()["id"]
        client.post(f"/api/proxy/rules/{rule_id}/disable", headers=auth_headers)
        service = client.app.state.proxy_service
        config = service.build_caddy_config()
        # No apps since the only rule is disabled
        assert "apps" not in config or "http" not in config.get("apps", {})

    def test_build_tcp_config(self, client, auth_headers):
        tcp_data = {
            "name": "DB Proxy",
            "protocol": "tcp",
            "listen_port": 5432,
            "upstreams": [{"address": "192.168.1.20:5432"}],
        }
        client.post("/api/proxy/rules", json=tcp_data, headers=auth_headers)
        service = client.app.state.proxy_service
        config = service.build_caddy_config()
        assert "layer4" in config["apps"]


class TestProxyCaddyStatus:
    @patch("stonepanel.proxy.caddy.CaddyClient.is_installed", new_callable=AsyncMock, return_value=True)
    @patch("stonepanel.proxy.caddy.CaddyClient.is_running", new_callable=AsyncMock, return_value=True)
    @patch("stonepanel.proxy.caddy.CaddyClient.get_version", new_callable=AsyncMock, return_value="v2.7.6")
    def test_caddy_status(self, mock_ver, mock_run, mock_inst, client, auth_headers):
        resp = client.get("/api/proxy/caddy/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["installed"] is True
        assert data["running"] is True
        assert data["version"] == "v2.7.6"

    @patch("stonepanel.proxy.caddy.CaddyClient.is_installed", new_callable=AsyncMock, return_value=False)
    @patch("stonepanel.proxy.caddy.CaddyClient.is_running", new_callable=AsyncMock, return_value=False)
    @patch("stonepanel.proxy.caddy.CaddyClient.get_version", new_callable=AsyncMock, return_value=None)
    def test_caddy_not_installed(self, mock_ver, mock_run, mock_inst, client, auth_headers):
        resp = client.get("/api/proxy/caddy/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["installed"] is False
        assert data["running"] is False


class TestProxyStatus:
    def test_proxy_status(self, client, auth_headers):
        with patch("stonepanel.proxy.caddy.CaddyClient.is_installed", new_callable=AsyncMock, return_value=False), \
             patch("stonepanel.proxy.caddy.CaddyClient.is_running", new_callable=AsyncMock, return_value=False), \
             patch("stonepanel.proxy.caddy.CaddyClient.get_version", new_callable=AsyncMock, return_value=None):
            resp = client.get("/api/proxy/status", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "caddy" in data
            assert data["rules_total"] == 0
            assert data["rules_enabled"] == 0
