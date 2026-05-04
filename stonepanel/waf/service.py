import json
import time
from pathlib import Path
from typing import Optional

from .engine import WAFEngine
from .log import AttackLogger
from .models import (
    AttackLogEntry,
    GeoBlockCreate,
    GeoBlockRule,
    IPList,
    IPListEntry,
    RateLimitCreate,
    RateLimitRule,
    RateLimitUpdate,
    RequestData,
    WAFAction,
    WAFConfig,
    WAFDecision,
    WAFRule,
    WAFRuleCreate,
    WAFRuleUpdate,
)


class WAFService:
    def __init__(self, data_dir: Path):
        self.config_dir = data_dir / "waf"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.rules_file = self.config_dir / "rules.json"
        self.ip_lists_file = self.config_dir / "ip_lists.json"
        self.rate_limits_file = self.config_dir / "rate_limits.json"
        self.geo_rules_file = self.config_dir / "geo_rules.json"

        self.engine = WAFEngine()
        self.logger = AttackLogger(self.config_dir / "logs")

        # Load everything
        self.engine.load_owasp_rules()
        self._reload_engine()

    def _reload_engine(self) -> None:
        self.engine.reload(
            config=self.load_config(),
            custom_rules=self.load_rules(),
            ip_lists=self.load_ip_lists(),
            rate_limits=self.load_rate_limits(),
            geo_rules=self.load_geo_rules(),
        )

    # --- Config ---

    def load_config(self) -> WAFConfig:
        if not self.config_file.exists():
            return WAFConfig()
        return WAFConfig(**json.loads(self.config_file.read_text()))

    def save_config(self, config: WAFConfig) -> WAFConfig:
        self.config_file.write_text(json.dumps(config.model_dump(), indent=2))
        self._reload_engine()
        return config

    # --- Custom rules ---

    def load_rules(self) -> list[WAFRule]:
        if not self.rules_file.exists():
            return []
        return [WAFRule(**r) for r in json.loads(self.rules_file.read_text())]

    def _save_rules(self, rules: list[WAFRule]) -> None:
        self.rules_file.write_text(
            json.dumps([r.model_dump() for r in rules], indent=2)
        )
        self._reload_engine()

    def create_rule(self, create: WAFRuleCreate) -> WAFRule:
        rules = self.load_rules()
        rule = WAFRule(**create.model_dump())
        rules.append(rule)
        self._save_rules(rules)
        return rule

    def update_rule(self, rule_id: str, update: WAFRuleUpdate) -> Optional[WAFRule]:
        rules = self.load_rules()
        for i, rule in enumerate(rules):
            if rule.id == rule_id:
                updated = rule.model_copy(update=update.model_dump(exclude_unset=True))
                rules[i] = updated
                self._save_rules(rules)
                return updated
        return None

    def delete_rule(self, rule_id: str) -> bool:
        rules = self.load_rules()
        new_rules = [r for r in rules if r.id != rule_id]
        if len(new_rules) == len(rules):
            return False
        self._save_rules(new_rules)
        return True

    # --- OWASP rules ---

    def get_owasp_rules(self) -> list[WAFRule]:
        return self.engine.owasp_rules

    def update_owasp_rule(self, rule_id: str, enabled: bool) -> Optional[WAFRule]:
        for rule in self.engine.owasp_rules:
            if rule.id == rule_id:
                rule.enabled = enabled
                return rule
        return None

    # --- IP lists ---

    def load_ip_lists(self) -> IPList:
        if not self.ip_lists_file.exists():
            return IPList()
        return IPList(**json.loads(self.ip_lists_file.read_text()))

    def _save_ip_lists(self, ip_lists: IPList) -> None:
        self.ip_lists_file.write_text(json.dumps(ip_lists.model_dump(), indent=2))
        self._reload_engine()

    def add_to_whitelist(self, entry: IPListEntry) -> IPList:
        ip_lists = self.load_ip_lists()
        ip_lists.whitelist.append(entry)
        self._save_ip_lists(ip_lists)
        return ip_lists

    def add_to_blacklist(self, entry: IPListEntry) -> IPList:
        ip_lists = self.load_ip_lists()
        ip_lists.blacklist.append(entry)
        self._save_ip_lists(ip_lists)
        return ip_lists

    def remove_from_list(self, list_type: str, address: str) -> bool:
        ip_lists = self.load_ip_lists()
        if list_type == "whitelist":
            original = len(ip_lists.whitelist)
            ip_lists.whitelist = [e for e in ip_lists.whitelist if e.address != address]
            if len(ip_lists.whitelist) == original:
                return False
        elif list_type == "blacklist":
            original = len(ip_lists.blacklist)
            ip_lists.blacklist = [e for e in ip_lists.blacklist if e.address != address]
            if len(ip_lists.blacklist) == original:
                return False
        else:
            return False
        self._save_ip_lists(ip_lists)
        return True

    # --- Rate limits ---

    def load_rate_limits(self) -> list[RateLimitRule]:
        if not self.rate_limits_file.exists():
            return []
        return [RateLimitRule(**r) for r in json.loads(self.rate_limits_file.read_text())]

    def _save_rate_limits(self, rules: list[RateLimitRule]) -> None:
        self.rate_limits_file.write_text(
            json.dumps([r.model_dump() for r in rules], indent=2)
        )
        self._reload_engine()

    def create_rate_limit(self, create: RateLimitCreate) -> RateLimitRule:
        rules = self.load_rate_limits()
        rule = RateLimitRule(**create.model_dump())
        rules.append(rule)
        self._save_rate_limits(rules)
        return rule

    def update_rate_limit(self, rule_id: str, update: RateLimitUpdate) -> Optional[RateLimitRule]:
        rules = self.load_rate_limits()
        for i, rule in enumerate(rules):
            if rule.id == rule_id:
                updated = rule.model_copy(update=update.model_dump(exclude_unset=True))
                rules[i] = updated
                self._save_rate_limits(rules)
                return updated
        return None

    def delete_rate_limit(self, rule_id: str) -> bool:
        rules = self.load_rate_limits()
        new_rules = [r for r in rules if r.id != rule_id]
        if len(new_rules) == len(rules):
            return False
        self._save_rate_limits(new_rules)
        return True

    # --- Geo rules ---

    def load_geo_rules(self) -> list[GeoBlockRule]:
        if not self.geo_rules_file.exists():
            return []
        return [GeoBlockRule(**r) for r in json.loads(self.geo_rules_file.read_text())]

    def _save_geo_rules(self, rules: list[GeoBlockRule]) -> None:
        self.geo_rules_file.write_text(
            json.dumps([r.model_dump() for r in rules], indent=2)
        )
        self._reload_engine()

    def create_geo_rule(self, create: GeoBlockCreate) -> GeoBlockRule:
        rules = self.load_geo_rules()
        rule = GeoBlockRule(**create.model_dump())
        rules.append(rule)
        self._save_geo_rules(rules)
        return rule

    def delete_geo_rule(self, rule_id: str) -> bool:
        rules = self.load_geo_rules()
        new_rules = [r for r in rules if r.id != rule_id]
        if len(new_rules) == len(rules):
            return False
        self._save_geo_rules(new_rules)
        return True

    # --- WAF evaluation ---

    def check_request(self, request: RequestData) -> WAFDecision:
        decision = self.engine.evaluate(request)

        # Log blocked/flagged requests
        if not decision.allowed or (decision.action and decision.action != WAFAction.ALLOW):
            self.logger.log(AttackLogEntry(
                source_ip=request.source_ip,
                method=request.method,
                url=request.url,
                rule_id=decision.rule_id or "unknown",
                rule_name=decision.rule_name or "Unknown",
                action=decision.action or WAFAction.LOG,
                category=decision.category or "unknown",
                details=decision.details,
            ))

        return decision

    # --- Log queries ---

    def query_logs(self, **kwargs) -> list[dict]:
        return self.logger.query(**kwargs)

    def get_log_stats(self, hours: int = 24) -> dict:
        return self.logger.get_stats(hours=hours)
