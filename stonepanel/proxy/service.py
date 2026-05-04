import json
import time
from pathlib import Path
from typing import Optional

from .caddy import CaddyClient
from .models import (
    CaddyStatus,
    LoadBalancePolicy,
    ProxyProtocol,
    ProxyRule,
    ProxyRuleCreate,
    ProxyRuleUpdate,
)


# Caddy load balance policy name mapping
_LB_POLICY_MAP = {
    LoadBalancePolicy.ROUND_ROBIN: "round_robin",
    LoadBalancePolicy.LEAST_CONN: "least_conn",
    LoadBalancePolicy.IP_HASH: "ip_hash",
    LoadBalancePolicy.RANDOM: "random",
    LoadBalancePolicy.FIRST: "first",
}


class ProxyService:
    def __init__(self, data_dir: Path, caddy: CaddyClient, waf_check_url: str = ""):
        self.config_dir = data_dir / "proxy"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.rules_file = self.config_dir / "rules.json"
        self.caddy = caddy
        self.waf_check_url = waf_check_url  # e.g. "http://localhost:6767/internal/waf/check"

    # --- Rule persistence ---

    def load_rules(self) -> list[ProxyRule]:
        if not self.rules_file.exists():
            return []
        data = json.loads(self.rules_file.read_text())
        return [ProxyRule(**r) for r in data]

    def save_rules(self, rules: list[ProxyRule]) -> None:
        self.rules_file.write_text(
            json.dumps([r.model_dump() for r in rules], indent=2)
        )

    def get_rule(self, rule_id: str) -> Optional[ProxyRule]:
        for rule in self.load_rules():
            if rule.id == rule_id:
                return rule
        return None

    def create_rule(self, create: ProxyRuleCreate) -> ProxyRule:
        rules = self.load_rules()
        rule = ProxyRule(
            **create.model_dump(),
            created_at=time.time(),
            updated_at=time.time(),
        )
        rules.append(rule)
        self.save_rules(rules)
        return rule

    def update_rule(self, rule_id: str, update: ProxyRuleUpdate) -> Optional[ProxyRule]:
        rules = self.load_rules()
        for i, rule in enumerate(rules):
            if rule.id == rule_id:
                update_data = update.model_dump(exclude_unset=True)
                update_data["updated_at"] = time.time()
                updated = rule.model_copy(update=update_data)
                rules[i] = updated
                self.save_rules(rules)
                return updated
        return None

    def delete_rule(self, rule_id: str) -> bool:
        rules = self.load_rules()
        new_rules = [r for r in rules if r.id != rule_id]
        if len(new_rules) == len(rules):
            return False
        self.save_rules(new_rules)
        return True

    def enable_rule(self, rule_id: str) -> Optional[ProxyRule]:
        return self.update_rule(rule_id, ProxyRuleUpdate(enabled=True))

    def disable_rule(self, rule_id: str) -> Optional[ProxyRule]:
        return self.update_rule(rule_id, ProxyRuleUpdate(enabled=False))

    # --- Caddy config generation ---

    def build_caddy_config(self, rules: Optional[list[ProxyRule]] = None) -> dict:
        """Build a complete Caddy JSON config from all enabled proxy rules."""
        if rules is None:
            rules = self.load_rules()

        enabled_rules = [r for r in rules if r.enabled]
        http_rules = [r for r in enabled_rules if r.protocol in (ProxyProtocol.HTTP, ProxyProtocol.HTTPS)]
        l4_rules = [r for r in enabled_rules if r.protocol in (ProxyProtocol.TCP, ProxyProtocol.UDP)]

        config: dict = {"admin": {"listen": "localhost:2019"}}

        # Build HTTP app config
        if http_rules:
            config["apps"] = {"http": self._build_http_app(http_rules)}

        # Build Layer4 app config (TCP/UDP)
        if l4_rules:
            config.setdefault("apps", {})
            config["apps"]["layer4"] = self._build_l4_app(l4_rules)

        # Logging
        config.setdefault("logging", {
            "logs": {
                "default": {
                    "writer": {"output": "stdout"},
                    "level": "INFO",
                }
            }
        })

        return config

    def _build_http_app(self, rules: list[ProxyRule]) -> dict:
        """Build Caddy HTTP app config."""
        # Group rules by listen port
        port_groups: dict[int, list[ProxyRule]] = {}
        for rule in rules:
            port = rule.listen_port
            port_groups.setdefault(port, []).append(rule)

        servers: dict[str, dict] = {}
        for port, group in port_groups.items():
            listen = [f":{port}"]
            routes = []
            auto_https_domains = []

            for rule in group:
                route = self._build_http_route(rule)
                routes.append(route)

                # Collect domains for auto HTTPS
                if rule.ssl.enabled and rule.ssl.auto_cert and rule.domain:
                    auto_https_domains.append(rule.domain)

            server: dict = {"listen": listen, "routes": routes}

            # If any rule on this port uses auto HTTPS, don't disable it
            if not any(r.ssl.enabled and r.ssl.auto_cert for r in group):
                server["automatic_https"] = {"disable": True}

            servers[f"srv_{port}"] = server

        return {"servers": servers}

    def _build_http_route(self, rule: ProxyRule) -> dict:
        """Build a single Caddy HTTP route from a ProxyRule."""
        matchers = []

        # Domain matching
        if rule.domain:
            matchers.append({"host": [rule.domain]})

        # Path matching
        if rule.path_prefix and rule.path_prefix != "/":
            matchers.append({"path": [f"{rule.path_prefix}*"]})

        # Upstream addresses
        upstreams = [{"dial": u.address} for u in rule.upstreams]

        # Reverse proxy handler
        proxy_handler: dict = {
            "handler": "reverse_proxy",
            "upstreams": upstreams,
        }

        # Load balancing
        lb_policy = _LB_POLICY_MAP.get(rule.load_balance, "round_robin")
        proxy_handler["load_balancing"] = {"selection_policy": {"policy": lb_policy}}

        # Health checks
        if rule.health_check.enabled:
            proxy_handler["health_checks"] = {
                "active": {
                    "path": rule.health_check.path,
                    "interval": f"{rule.health_check.interval}s",
                    "timeout": f"{rule.health_check.timeout}s",
                }
            }

        # Custom headers
        if rule.headers:
            proxy_handler["headers"] = {
                "request": {
                    "set": {k: [v] for k, v in rule.headers.items()}
                }
            }

        # Build handlers list
        handlers = []

        # WAF forward_auth (if enabled and waf_check_url is set)
        if rule.waf_enabled and self.waf_check_url:
            handlers.append({
                "handler": "forward_auth",
                "uri": "/internal/waf/check",
                "upstream": self.waf_check_url,
                "copy_headers": ["X-Forwarded-For", "X-Real-IP"],
            })

        handlers.append(proxy_handler)

        route: dict = {"handle": handlers}
        if matchers:
            route["match"] = matchers

        # TLS with manual certs
        if rule.ssl.enabled and not rule.ssl.auto_cert:
            if rule.ssl.cert_path and rule.ssl.key_path:
                route["terminal"] = True  # handled by tls app separately

        return route

    def _build_l4_app(self, rules: list[ProxyRule]) -> dict:
        """Build Caddy Layer4 app config for TCP/UDP proxying."""
        servers: dict[str, dict] = {}

        for rule in rules:
            listen_addr = f":{rule.listen_port}"
            if rule.protocol == ProxyProtocol.UDP:
                listen_addr = f"udp/{listen_addr}"

            upstreams = [{"dial": [u.address]} for u in rule.upstreams]

            servers[f"l4_{rule.id[:8]}"] = {
                "listen": [listen_addr],
                "routes": [
                    {
                        "handle": [
                            {
                                "handler": "proxy",
                                "upstreams": upstreams,
                            }
                        ]
                    }
                ],
            }

        return {"servers": servers}

    # --- Caddy operations ---

    async def apply_config(self) -> bool:
        """Build config from rules and load it into Caddy."""
        config = self.build_caddy_config()
        return await self.caddy.load_config(config)

    async def get_caddy_status(self) -> CaddyStatus:
        installed = await self.caddy.is_installed()
        running = await self.caddy.is_running()
        version = await self.caddy.get_version() if installed else None
        return CaddyStatus(
            installed=installed,
            running=running,
            version=version,
            admin_url=self.caddy.admin_url,
        )
