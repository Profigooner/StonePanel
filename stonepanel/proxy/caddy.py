import asyncio
import shutil
from typing import Any, Optional

import httpx


class CaddyClient:
    """Async client for managing Caddy via its admin API."""

    def __init__(self, admin_url: str = "http://localhost:2019", binary: str = "caddy"):
        self.admin_url = admin_url.rstrip("/")
        self.binary = binary

    async def is_installed(self) -> bool:
        return shutil.which(self.binary) is not None

    async def is_running(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.admin_url}/config/", timeout=3)
                return resp.status_code in (200, 404)
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def get_version(self) -> Optional[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary, "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return stdout.decode().strip().split()[0]
        except FileNotFoundError:
            pass
        return None

    async def get_config(self) -> Optional[dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.admin_url}/config/", timeout=5)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except (httpx.ConnectError, httpx.TimeoutException):
            return None

    async def load_config(self, config: dict) -> bool:
        """Replace the entire Caddy config."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.admin_url}/load",
                json=config,
                timeout=10,
            )
            return resp.status_code == 200

    async def patch_config(self, path: str, value: Any) -> bool:
        """PATCH a specific config path (e.g., /config/apps/http)."""
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.admin_url}{path}",
                json=value,
                timeout=10,
            )
            return resp.status_code == 200

    async def delete_config(self, path: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.admin_url}{path}",
                timeout=10,
            )
            return resp.status_code == 200

    async def start(self) -> bool:
        """Start Caddy in the background with an empty config."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary, "start",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def stop(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary, "stop",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
