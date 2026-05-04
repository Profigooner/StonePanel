import time

import pytest

from stonepanel.waf.engine import WAFEngine
from stonepanel.waf.models import (
    GeoBlockRule,
    IPList,
    IPListEntry,
    RateLimitRule,
    RequestData,
    RuleCondition,
    RuleOperator,
    RuleTarget,
    WAFAction,
    WAFConfig,
    WAFRule,
)
from stonepanel.waf.ratelimit import SlidingWindowCounter


# --- Rate Limiter Tests ---


class TestSlidingWindowCounter:
    def test_within_limit(self):
        limiter = SlidingWindowCounter()
        for _ in range(5):
            assert limiter.record("key1", max_requests=10, window=60)

    def test_exceeds_limit(self):
        limiter = SlidingWindowCounter()
        for _ in range(10):
            limiter.record("key1", max_requests=10, window=60)
        assert not limiter.record("key1", max_requests=10, window=60)

    def test_block_and_unblock(self):
        limiter = SlidingWindowCounter()
        limiter.block("key1", duration=1)
        assert limiter.is_blocked("key1")
        time.sleep(1.1)
        assert not limiter.is_blocked("key1")

    def test_separate_keys(self):
        limiter = SlidingWindowCounter()
        for _ in range(10):
            limiter.record("key1", max_requests=10, window=60)
        assert not limiter.record("key1", max_requests=10, window=60)
        assert limiter.record("key2", max_requests=10, window=60)


# --- WAF Engine Tests ---


class TestWAFEngine:
    def _make_engine(self, **kwargs) -> WAFEngine:
        engine = WAFEngine()
        engine.load_owasp_rules()
        engine.reload(
            config=kwargs.get("config", WAFConfig()),
            custom_rules=kwargs.get("custom_rules", []),
            ip_lists=kwargs.get("ip_lists", IPList()),
            rate_limits=kwargs.get("rate_limits", []),
            geo_rules=kwargs.get("geo_rules", []),
        )
        return engine

    def _make_request(self, **kwargs) -> RequestData:
        defaults = {
            "source_ip": "10.0.0.1",
            "method": "GET",
            "url": "http://example.com/test",
            "path": "/test",
            "query_string": "",
            "headers": {},
            "user_agent": "Mozilla/5.0",
        }
        defaults.update(kwargs)
        return RequestData(**defaults)

    def test_disabled_allows_all(self):
        engine = self._make_engine(config=WAFConfig(enabled=False))
        req = self._make_request(query_string="id=1 UNION SELECT * FROM users")
        decision = engine.evaluate(req)
        assert decision.allowed

    def test_sql_injection_blocked(self):
        engine = self._make_engine()
        req = self._make_request(query_string="id=1 UNION SELECT * FROM users")
        decision = engine.evaluate(req)
        assert not decision.allowed
        assert decision.category == "owasp"

    def test_xss_blocked(self):
        engine = self._make_engine()
        req = self._make_request(query_string='name=<script>alert(1)</script>')
        decision = engine.evaluate(req)
        assert not decision.allowed

    def test_path_traversal_blocked(self):
        engine = self._make_engine()
        req = self._make_request(url="http://example.com/../../../etc/passwd")
        decision = engine.evaluate(req)
        assert not decision.allowed

    def test_command_injection_blocked(self):
        engine = self._make_engine()
        req = self._make_request(query_string="cmd=test; cat /etc/passwd")
        decision = engine.evaluate(req)
        assert not decision.allowed

    def test_scanner_blocked(self):
        engine = self._make_engine()
        req = self._make_request(user_agent="sqlmap/1.5")
        decision = engine.evaluate(req)
        assert not decision.allowed
        assert decision.category == "bot"

    def test_clean_request_allowed(self):
        engine = self._make_engine()
        req = self._make_request(
            url="http://example.com/api/users",
            query_string="page=1&limit=20",
        )
        decision = engine.evaluate(req)
        assert decision.allowed

    def test_ip_whitelist_bypasses_rules(self):
        ip_lists = IPList(whitelist=[IPListEntry(address="10.0.0.1")])
        engine = self._make_engine(ip_lists=ip_lists)
        req = self._make_request(
            source_ip="10.0.0.1",
            query_string="id=1 UNION SELECT * FROM users",
        )
        decision = engine.evaluate(req)
        assert decision.allowed

    def test_ip_blacklist_blocks(self):
        ip_lists = IPList(blacklist=[IPListEntry(address="10.0.0.1")])
        engine = self._make_engine(ip_lists=ip_lists)
        req = self._make_request(source_ip="10.0.0.1")
        decision = engine.evaluate(req)
        assert not decision.allowed
        assert decision.category == "ip_blacklist"

    def test_cidr_blacklist(self):
        ip_lists = IPList(blacklist=[IPListEntry(address="10.0.0.0/24")])
        engine = self._make_engine(ip_lists=ip_lists)
        req = self._make_request(source_ip="10.0.0.55")
        decision = engine.evaluate(req)
        assert not decision.allowed

    def test_rate_limiting(self):
        rate_limits = [
            RateLimitRule(name="Test Limit", requests=3, window=60, block_duration=10)
        ]
        engine = self._make_engine(rate_limits=rate_limits)
        req = self._make_request()
        for _ in range(3):
            decision = engine.evaluate(req)
            assert decision.allowed
        decision = engine.evaluate(req)
        assert not decision.allowed
        assert decision.category == "rate_limit"

    def test_custom_rule(self):
        custom = [
            WAFRule(
                name="Block admin access",
                conditions=[
                    RuleCondition(target=RuleTarget.URL, operator=RuleOperator.CONTAINS, value="/admin")
                ],
                action=WAFAction.BLOCK,
            )
        ]
        engine = self._make_engine(custom_rules=custom)
        req = self._make_request(url="http://example.com/admin/dashboard")
        decision = engine.evaluate(req)
        assert not decision.allowed

    def test_monitor_mode_logs_but_allows(self):
        engine = self._make_engine(config=WAFConfig(mode="monitor"))
        req = self._make_request(query_string="id=1 UNION SELECT * FROM users")
        decision = engine.evaluate(req)
        assert decision.allowed
        assert decision.action == WAFAction.LOG

    def test_negated_condition(self):
        custom = [
            WAFRule(
                name="Block non-JSON",
                conditions=[
                    RuleCondition(
                        target=RuleTarget.HEADERS,
                        operator=RuleOperator.CONTAINS,
                        value="application/json",
                        negate=True,
                    )
                ],
                action=WAFAction.BLOCK,
            )
        ]
        engine = self._make_engine(custom_rules=custom)

        # Without JSON header -> blocked
        req = self._make_request(headers={"content-type": "text/html"})
        decision = engine.evaluate(req)
        assert not decision.allowed

        # With JSON header -> allowed
        req = self._make_request(headers={"content-type": "application/json"})
        decision = engine.evaluate(req)
        assert decision.allowed


# --- WAF API Tests ---


class TestWAFAPI:
    def test_get_config(self, client, auth_headers):
        resp = client.get("/api/waf/config", headers=auth_headers)
        assert resp.status_code == 200
        assert "enabled" in resp.json()

    def test_update_config(self, client, auth_headers):
        resp = client.put(
            "/api/waf/config",
            json={"enabled": True, "mode": "monitor", "owasp_enabled": True, "bot_detection": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "monitor"

    def test_list_owasp_rules(self, client, auth_headers):
        resp = client.get("/api/waf/owasp/rules", headers=auth_headers)
        assert resp.status_code == 200
        rules = resp.json()["rules"]
        assert len(rules) > 0
        assert any(r["category"] == "owasp" for r in rules)

    def test_custom_rule_crud(self, client, auth_headers):
        # Create
        rule_data = {
            "name": "Block /secret",
            "conditions": [
                {"target": "url", "operator": "contains", "value": "/secret"}
            ],
            "action": "block",
        }
        resp = client.post("/api/waf/rules", json=rule_data, headers=auth_headers)
        assert resp.status_code == 201
        rule_id = resp.json()["id"]

        # List
        resp = client.get("/api/waf/rules", headers=auth_headers)
        assert len(resp.json()["rules"]) == 1

        # Update
        resp = client.put(
            f"/api/waf/rules/{rule_id}",
            json={"name": "Block /secret-v2"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Block /secret-v2"

        # Delete
        resp = client.delete(f"/api/waf/rules/{rule_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_ip_lists(self, client, auth_headers):
        # Add to blacklist
        resp = client.post(
            "/api/waf/ip-lists/blacklist",
            json={"address": "192.168.1.100", "note": "attacker"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Get lists
        resp = client.get("/api/waf/ip-lists", headers=auth_headers)
        assert len(resp.json()["blacklist"]) == 1

        # Remove
        resp = client.delete(
            "/api/waf/ip-lists/blacklist/192.168.1.100",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_rate_limit_crud(self, client, auth_headers):
        resp = client.post(
            "/api/waf/rate-limits",
            json={"name": "API Limit", "requests": 100, "window": 60},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        rule_id = resp.json()["id"]

        resp = client.get("/api/waf/rate-limits", headers=auth_headers)
        assert len(resp.json()["rules"]) == 1

        resp = client.delete(f"/api/waf/rate-limits/{rule_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_geo_rule_crud(self, client, auth_headers):
        resp = client.post(
            "/api/waf/geo-rules",
            json={"countries": ["CN", "RU"], "mode": "blacklist"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        rule_id = resp.json()["id"]

        resp = client.get("/api/waf/geo-rules", headers=auth_headers)
        assert len(resp.json()["rules"]) == 1

        resp = client.delete(f"/api/waf/geo-rules/{rule_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_dashboard(self, client, auth_headers):
        resp = client.get("/api/waf/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "stats" in data
        assert "owasp_rules_total" in data

    def test_logs(self, client, auth_headers):
        resp = client.get("/api/waf/logs", headers=auth_headers)
        assert resp.status_code == 200
        assert "logs" in resp.json()

    def test_log_stats(self, client, auth_headers):
        resp = client.get("/api/waf/logs/stats", headers=auth_headers)
        assert resp.status_code == 200
        assert "total" in resp.json()

    def test_requires_auth(self, client):
        resp = client.get("/api/waf/config")
        assert resp.status_code == 401


class TestWAFCheck:
    def test_internal_waf_check_allows_clean(self, client, auth_headers):
        # First enable WAF
        client.put(
            "/api/waf/config",
            json={"enabled": True, "mode": "active", "owasp_enabled": True, "bot_detection": True},
            headers=auth_headers,
        )
        resp = client.post(
            "/internal/waf/check",
            headers={
                "x-forwarded-for": "10.0.0.1",
                "x-forwarded-method": "GET",
                "x-forwarded-uri": "/api/data?page=1",
                "x-forwarded-host": "example.com",
                "user-agent": "Mozilla/5.0",
            },
        )
        assert resp.status_code == 200

    def test_internal_waf_check_blocks_sqli(self, client, auth_headers):
        client.put(
            "/api/waf/config",
            json={"enabled": True, "mode": "active", "owasp_enabled": True, "bot_detection": True},
            headers=auth_headers,
        )
        resp = client.post(
            "/internal/waf/check",
            headers={
                "x-forwarded-for": "10.0.0.1",
                "x-forwarded-method": "GET",
                "x-forwarded-uri": "/api/data?id=1 UNION SELECT * FROM users",
                "x-forwarded-host": "example.com",
                "user-agent": "Mozilla/5.0",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["status"] == "blocked"

    def test_rule_test_endpoint(self, client, auth_headers):
        resp = client.post(
            "/api/waf/rules/test",
            json={
                "source_ip": "10.0.0.1",
                "method": "GET",
                "url": "http://example.com/test?id=1 UNION SELECT 1",
                "path": "/test",
                "query_string": "id=1 UNION SELECT 1",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert not resp.json()["allowed"]
