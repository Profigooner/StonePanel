import asyncio
import time
from typing import Optional

import httpx

from .models import ProxyProtocol, ProxyRule, UpstreamStatus


class HealthChecker:
    """Background task that periodically checks upstream health."""

    def __init__(self):
        self._status: dict[str, list[UpstreamStatus]] = {}  # rule_id -> statuses
        self._task: Optional[asyncio.Task] = None

    @property
    def status(self) -> dict[str, list[UpstreamStatus]]:
        return self._status

    def get_rule_status(self, rule_id: str) -> list[UpstreamStatus]:
        return self._status.get(rule_id, [])

    def start(self, rules_loader) -> None:
        """Start background health checking. rules_loader is a callable returning list[ProxyRule]."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(rules_loader))

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self, rules_loader) -> None:
        while True:
            try:
                rules = rules_loader()
                await self._check_all(rules)
            except asyncio.CancelledError:
                break
            except Exception:
                pass  # don't crash the loop on transient errors
            await asyncio.sleep(30)

    async def _check_all(self, rules: list[ProxyRule]) -> None:
        for rule in rules:
            if not rule.enabled or not rule.health_check.enabled:
                continue
            statuses = []
            for upstream in rule.upstreams:
                status = await self._check_upstream(rule, upstream.address)
                statuses.append(status)
            self._status[rule.id] = statuses

    async def _check_upstream(self, rule: ProxyRule, address: str) -> UpstreamStatus:
        if rule.protocol in (ProxyProtocol.TCP, ProxyProtocol.UDP):
            return await self._check_tcp(address)
        return await self._check_http(address, rule.health_check.path, rule.health_check.timeout)

    async def _check_http(self, address: str, path: str, timeout: int) -> UpstreamStatus:
        url = f"http://{address}{path}"
        start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=timeout, follow_redirects=True)
                elapsed = (time.time() - start) * 1000
                return UpstreamStatus(
                    address=address,
                    healthy=resp.status_code < 500,
                    last_check=time.time(),
                    response_time_ms=round(elapsed, 2),
                )
        except (httpx.ConnectError, httpx.TimeoutException, Exception):
            return UpstreamStatus(
                address=address,
                healthy=False,
                last_check=time.time(),
                response_time_ms=None,
            )

    async def _check_tcp(self, address: str) -> UpstreamStatus:
        host, _, port_str = address.rpartition(":")
        port = int(port_str) if port_str else 80
        start = time.time()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5
            )
            elapsed = (time.time() - start) * 1000
            writer.close()
            await writer.wait_closed()
            return UpstreamStatus(
                address=address,
                healthy=True,
                last_check=time.time(),
                response_time_ms=round(elapsed, 2),
            )
        except (asyncio.TimeoutError, OSError):
            return UpstreamStatus(
                address=address,
                healthy=False,
                last_check=time.time(),
                response_time_ms=None,
            )
