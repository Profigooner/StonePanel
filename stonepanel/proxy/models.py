import time
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProxyProtocol(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    UDP = "udp"


class LoadBalancePolicy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    IP_HASH = "ip_hash"
    RANDOM = "random"
    FIRST = "first"


class Upstream(BaseModel):
    address: str  # e.g. "192.168.1.10:8080"
    weight: int = 1
    max_fails: int = 3
    fail_timeout: int = 30  # seconds


class HealthCheck(BaseModel):
    enabled: bool = False
    path: str = "/"
    interval: int = 30  # seconds
    timeout: int = 10
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3


class SSLConfig(BaseModel):
    enabled: bool = False
    auto_cert: bool = True  # Let's Encrypt via Caddy
    cert_path: Optional[str] = None
    key_path: Optional[str] = None


class ProxyRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    listen_host: str = ""  # empty = all interfaces
    listen_port: int = 80
    domain: Optional[str] = None  # for HTTP virtual host matching
    path_prefix: str = "/"
    upstreams: list[Upstream]
    load_balance: LoadBalancePolicy = LoadBalancePolicy.ROUND_ROBIN
    health_check: HealthCheck = Field(default_factory=HealthCheck)
    ssl: SSLConfig = Field(default_factory=SSLConfig)
    waf_enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ProxyRuleCreate(BaseModel):
    name: str
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    listen_host: str = ""
    listen_port: int = 80
    domain: Optional[str] = None
    path_prefix: str = "/"
    upstreams: list[Upstream]
    load_balance: LoadBalancePolicy = LoadBalancePolicy.ROUND_ROBIN
    health_check: HealthCheck = Field(default_factory=HealthCheck)
    ssl: SSLConfig = Field(default_factory=SSLConfig)
    waf_enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)


class ProxyRuleUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    protocol: Optional[ProxyProtocol] = None
    listen_host: Optional[str] = None
    listen_port: Optional[int] = None
    domain: Optional[str] = None
    path_prefix: Optional[str] = None
    upstreams: Optional[list[Upstream]] = None
    load_balance: Optional[LoadBalancePolicy] = None
    health_check: Optional[HealthCheck] = None
    ssl: Optional[SSLConfig] = None
    waf_enabled: Optional[bool] = None
    headers: Optional[dict[str, str]] = None


class UpstreamStatus(BaseModel):
    address: str
    healthy: bool
    last_check: float
    response_time_ms: Optional[float] = None


class ProxyRuleStatus(BaseModel):
    id: str
    name: str
    enabled: bool
    upstreams: list[UpstreamStatus]
    requests_total: int = 0
    bytes_in: int = 0
    bytes_out: int = 0


class CaddyStatus(BaseModel):
    installed: bool
    running: bool
    version: Optional[str] = None
    admin_url: str = ""
