import ipaddress
import json
import re
import time
from pathlib import Path
from typing import Optional

from .models import (
    AttackLogEntry,
    GeoBlockRule,
    IPList,
    RateLimitRule,
    RequestData,
    RuleCondition,
    RuleOperator,
    RuleTarget,
    WAFAction,
    WAFConfig,
    WAFDecision,
    WAFRule,
)
from .ratelimit import SlidingWindowCounter

OWASP_RULES_FILE = Path(__file__).parent / "owasp_rules.json"


class WAFEngine:
    """Core WAF rule evaluation engine."""

    def __init__(self):
        self.config = WAFConfig()
        self.custom_rules: list[WAFRule] = []
        self.owasp_rules: list[WAFRule] = []
        self.ip_lists = IPList()
        self.rate_limits: list[RateLimitRule] = []
        self.geo_rules: list[GeoBlockRule] = []
        self.rate_limiter = SlidingWindowCounter()
        self._compiled_patterns: dict[str, re.Pattern] = {}

    def load_owasp_rules(self) -> None:
        """Load built-in OWASP rules from JSON file."""
        if OWASP_RULES_FILE.exists():
            data = json.loads(OWASP_RULES_FILE.read_text())
            self.owasp_rules = [WAFRule(**r) for r in data]
            self._precompile_rules(self.owasp_rules)

    def reload(
        self,
        config: WAFConfig,
        custom_rules: list[WAFRule],
        ip_lists: IPList,
        rate_limits: list[RateLimitRule],
        geo_rules: list[GeoBlockRule],
    ) -> None:
        """Reload all WAF configuration."""
        self.config = config
        self.custom_rules = custom_rules
        self.ip_lists = ip_lists
        self.rate_limits = rate_limits
        self.geo_rules = geo_rules
        self._compiled_patterns.clear()
        self._precompile_rules(self.owasp_rules)
        self._precompile_rules(self.custom_rules)

    def _precompile_rules(self, rules: list[WAFRule]) -> None:
        """Pre-compile regex patterns for performance."""
        for rule in rules:
            for cond in rule.conditions:
                if cond.operator == RuleOperator.REGEX:
                    cache_key = cond.value
                    if cache_key not in self._compiled_patterns:
                        try:
                            self._compiled_patterns[cache_key] = re.compile(cond.value)
                        except re.error:
                            pass  # invalid regex, will fail at match time

    def evaluate(self, request: RequestData) -> WAFDecision:
        """Evaluate a request against all WAF rules.

        Evaluation order:
        1. IP whitelist -> allow immediately
        2. IP blacklist -> block immediately
        3. Rate limiting -> block if exceeded
        4. Geo-blocking -> block if matched
        5. OWASP rules -> block if matched
        6. Custom rules -> block if matched
        """
        if not self.config.enabled:
            return WAFDecision(allowed=True)

        # 1. IP whitelist
        if self._check_ip_whitelist(request.source_ip):
            return WAFDecision(allowed=True, details="IP whitelisted")

        # 2. IP blacklist
        if self._check_ip_blacklist(request.source_ip):
            return WAFDecision(
                allowed=False,
                action=WAFAction.BLOCK,
                category="ip_blacklist",
                rule_name="IP Blacklist",
                rule_id="ip-blacklist",
                details=f"IP {request.source_ip} is blacklisted",
            )

        # 3. Rate limiting
        rate_decision = self._check_rate_limits(request)
        if rate_decision:
            return rate_decision

        # 4. Geo-blocking (skipped if no geo rules configured)
        # GeoIP lookup would go here — requires geoip2 library

        # 5. OWASP rules
        if self.config.owasp_enabled:
            owasp_decision = self._check_rules(request, self.owasp_rules)
            if owasp_decision:
                return owasp_decision

        # 6. Custom rules (sorted by priority)
        sorted_rules = sorted(self.custom_rules, key=lambda r: r.priority)
        custom_decision = self._check_rules(request, sorted_rules)
        if custom_decision:
            return custom_decision

        return WAFDecision(allowed=True)

    def _check_ip_whitelist(self, ip: str) -> bool:
        now = time.time()
        for entry in self.ip_lists.whitelist:
            if entry.expires_at and entry.expires_at < now:
                continue
            if self._ip_matches(ip, entry.address):
                return True
        return False

    def _check_ip_blacklist(self, ip: str) -> bool:
        now = time.time()
        for entry in self.ip_lists.blacklist:
            if entry.expires_at and entry.expires_at < now:
                continue
            if self._ip_matches(ip, entry.address):
                return True
        return False

    def _ip_matches(self, ip: str, pattern: str) -> bool:
        """Check if an IP matches an address or CIDR pattern."""
        try:
            if "/" in pattern:
                network = ipaddress.ip_network(pattern, strict=False)
                return ipaddress.ip_address(ip) in network
            return ip == pattern
        except ValueError:
            return False

    def _check_rate_limits(self, request: RequestData) -> Optional[WAFDecision]:
        for rule in self.rate_limits:
            if not rule.enabled:
                continue

            if rule.scope == "ip":
                key = f"rate:{rule.id}:{request.source_ip}"
            elif rule.scope == "route":
                if rule.route_pattern and not re.match(rule.route_pattern, request.path):
                    continue
                key = f"rate:{rule.id}:{request.source_ip}:{request.path}"
            else:  # global
                key = f"rate:{rule.id}:global"

            # Check if already blocked
            if self.rate_limiter.is_blocked(key):
                return WAFDecision(
                    allowed=False,
                    action=rule.action,
                    category="rate_limit",
                    rule_id=rule.id,
                    rule_name=rule.name,
                    details=f"Rate limit exceeded: {rule.requests}/{rule.window}s",
                )

            # Record and check
            if not self.rate_limiter.record(key, rule.requests, rule.window):
                self.rate_limiter.block(key, rule.block_duration)
                return WAFDecision(
                    allowed=False,
                    action=rule.action,
                    category="rate_limit",
                    rule_id=rule.id,
                    rule_name=rule.name,
                    details=f"Rate limit exceeded: {rule.requests}/{rule.window}s",
                )

        return None

    def _check_rules(self, request: RequestData, rules: list[WAFRule]) -> Optional[WAFDecision]:
        for rule in rules:
            if not rule.enabled:
                continue
            if self._rule_matches(request, rule):
                # In monitor mode, log but allow
                action = rule.action
                allowed = action == WAFAction.ALLOW
                if self.config.mode == "monitor" and action == WAFAction.BLOCK:
                    allowed = True
                    action = WAFAction.LOG

                return WAFDecision(
                    allowed=allowed,
                    action=action,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    category=rule.category,
                    details=f"Matched rule: {rule.name}",
                )
        return None

    def _rule_matches(self, request: RequestData, rule: WAFRule) -> bool:
        """Check if all conditions of a rule match (AND logic)."""
        return all(self._condition_matches(request, cond) for cond in rule.conditions)

    def _condition_matches(self, request: RequestData, cond: RuleCondition) -> bool:
        value = self._get_target_value(request, cond.target)
        result = self._operator_matches(value, cond.operator, cond.value)
        return not result if cond.negate else result

    def _get_target_value(self, request: RequestData, target: RuleTarget) -> str:
        if target == RuleTarget.URL:
            return request.url
        elif target == RuleTarget.QUERY:
            return request.query_string
        elif target == RuleTarget.BODY:
            return request.body
        elif target == RuleTarget.HEADERS:
            return " ".join(f"{k}: {v}" for k, v in request.headers.items())
        elif target == RuleTarget.COOKIES:
            return request.cookies
        elif target == RuleTarget.USER_AGENT:
            return request.user_agent
        elif target == RuleTarget.IP:
            return request.source_ip
        elif target == RuleTarget.METHOD:
            return request.method
        return ""

    def _operator_matches(self, value: str, operator: RuleOperator, pattern: str) -> bool:
        if operator == RuleOperator.CONTAINS:
            return pattern.lower() in value.lower()
        elif operator == RuleOperator.EQUALS:
            return value.lower() == pattern.lower()
        elif operator == RuleOperator.STARTS_WITH:
            return value.lower().startswith(pattern.lower())
        elif operator == RuleOperator.ENDS_WITH:
            return value.lower().endswith(pattern.lower())
        elif operator == RuleOperator.REGEX:
            compiled = self._compiled_patterns.get(pattern)
            if compiled:
                return bool(compiled.search(value))
            try:
                return bool(re.search(pattern, value))
            except re.error:
                return False
        return False
