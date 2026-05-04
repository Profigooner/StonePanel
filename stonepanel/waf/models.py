import time
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WAFAction(str, Enum):
    BLOCK = "block"
    ALLOW = "allow"
    LOG = "log"


class RuleTarget(str, Enum):
    URL = "url"
    QUERY = "query"
    BODY = "body"
    HEADERS = "headers"
    COOKIES = "cookies"
    USER_AGENT = "user_agent"
    IP = "ip"
    METHOD = "method"


class RuleOperator(str, Enum):
    CONTAINS = "contains"
    REGEX = "regex"
    EQUALS = "equals"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class RuleCondition(BaseModel):
    target: RuleTarget
    operator: RuleOperator
    value: str
    negate: bool = False


class WAFRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    priority: int = 100  # lower = evaluated first
    conditions: list[RuleCondition]
    action: WAFAction = WAFAction.BLOCK
    log: bool = True
    category: str = "custom"  # "owasp", "custom", "bot"
    description: str = ""


class WAFRuleCreate(BaseModel):
    name: str
    enabled: bool = True
    priority: int = 100
    conditions: list[RuleCondition]
    action: WAFAction = WAFAction.BLOCK
    log: bool = True
    category: str = "custom"
    description: str = ""


class WAFRuleUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    conditions: Optional[list[RuleCondition]] = None
    action: Optional[WAFAction] = None
    log: Optional[bool] = None
    description: Optional[str] = None


class IPListEntry(BaseModel):
    address: str  # IP or CIDR, e.g. "192.168.1.0/24"
    note: str = ""
    added_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None  # Unix timestamp, None = permanent


class IPList(BaseModel):
    whitelist: list[IPListEntry] = Field(default_factory=list)
    blacklist: list[IPListEntry] = Field(default_factory=list)


class RateLimitRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    scope: str = "ip"  # "ip", "route", "global"
    route_pattern: Optional[str] = None
    requests: int = 100  # max requests
    window: int = 60  # time window in seconds
    action: WAFAction = WAFAction.BLOCK
    block_duration: int = 300  # ban duration in seconds


class RateLimitCreate(BaseModel):
    name: str
    enabled: bool = True
    scope: str = "ip"
    route_pattern: Optional[str] = None
    requests: int = 100
    window: int = 60
    action: WAFAction = WAFAction.BLOCK
    block_duration: int = 300


class RateLimitUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    scope: Optional[str] = None
    route_pattern: Optional[str] = None
    requests: Optional[int] = None
    window: Optional[int] = None
    action: Optional[WAFAction] = None
    block_duration: Optional[int] = None


class GeoBlockRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    countries: list[str]  # ISO country codes
    action: WAFAction = WAFAction.BLOCK
    mode: str = "blacklist"  # "blacklist" or "whitelist"


class GeoBlockCreate(BaseModel):
    enabled: bool = True
    countries: list[str]
    action: WAFAction = WAFAction.BLOCK
    mode: str = "blacklist"


class WAFConfig(BaseModel):
    enabled: bool = True
    mode: str = "active"  # "active" (block) or "monitor" (log only)
    owasp_enabled: bool = True
    bot_detection: bool = True


class AttackLogEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    source_ip: str
    method: str
    url: str
    rule_id: str
    rule_name: str
    action: WAFAction
    category: str
    details: str = ""
    country: Optional[str] = None


class RequestData(BaseModel):
    """Normalized request data for WAF evaluation."""
    source_ip: str
    method: str
    url: str
    path: str
    query_string: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    user_agent: str = ""
    cookies: str = ""


class WAFDecision(BaseModel):
    allowed: bool
    action: Optional[WAFAction] = None
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    category: Optional[str] = None
    details: str = ""
