from __future__ import annotations

import asyncio
import json
import re

VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9@._-]+$")
ALLOWED_ACTIONS = {"start", "stop", "restart", "reload", "enable", "disable"}


def _validate_name(name: str) -> bool:
    """Validate service name to prevent command injection."""
    return bool(VALID_NAME_RE.match(name))


class SystemdService:
    """Manage systemd services."""

    @staticmethod
    async def is_available() -> bool:
        """Check if systemctl is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    @staticmethod
    def parse_units(output: str) -> list[dict]:
        """Parse systemctl list-units output (plain text format)."""
        units: list[dict] = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Format: UNIT LOAD ACTIVE SUB DESCRIPTION...
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            unit_name = parts[0]
            # Skip non-service entries that might slip through
            if not unit_name.endswith(".service") and "." in unit_name:
                continue
            units.append({
                "name": unit_name,
                "load": parts[1],
                "active": parts[2],
                "sub": parts[3],
                "description": parts[4] if len(parts) > 4 else "",
            })
        return units

    @staticmethod
    async def list_services(
        unit_type: str = "service",
        state: str | None = None,
    ) -> list[dict]:
        """List systemd units."""
        cmd = [
            "systemctl", "list-units",
            f"--type={unit_type}",
            "--no-pager", "--plain", "--no-legend",
            "--all",
        ]
        if state:
            cmd.append(f"--state={state}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return []
            return SystemdService.parse_units(stdout.decode(errors="replace"))
        except FileNotFoundError:
            return []

    @staticmethod
    def parse_show(output: str) -> dict:
        """Parse systemctl show key=value output into a dict."""
        props: dict = {}
        for line in output.split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            props[key] = value
        return props

    @staticmethod
    async def get_status(name: str) -> dict | None:
        """Get detailed status of a service."""
        if not _validate_name(name):
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "show", name, "--no-pager",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return None
            props = SystemdService.parse_show(stdout.decode(errors="replace"))
            if not props.get("Id"):
                return None

            # Extract useful fields
            return {
                "name": props.get("Id", name),
                "description": props.get("Description", ""),
                "load_state": props.get("LoadState", ""),
                "active_state": props.get("ActiveState", ""),
                "sub_state": props.get("SubState", ""),
                "main_pid": int(props["MainPID"]) if props.get("MainPID", "0") != "0" else None,
                "memory": props.get("MemoryCurrent", ""),
                "started_at": props.get("ExecMainStartTimestamp", ""),
                "enabled": props.get("UnitFileState", "") in ("enabled", "enabled-runtime"),
                "unit_file": props.get("FragmentPath", ""),
            }
        except FileNotFoundError:
            return None

    @staticmethod
    async def action(name: str, act: str) -> tuple[bool, str]:
        """Run a systemctl action. Returns (success, message)."""
        if not _validate_name(name):
            return False, "Invalid service name"
        if act not in ALLOWED_ACTIONS:
            return False, f"Action '{act}' not allowed"

        try:
            proc = await asyncio.create_subprocess_exec(
                "sudo", "-n", "systemctl", act, name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                if "a password is required" in err.lower():
                    return False, "sudo requires a password — configure NOPASSWD for systemctl"
                return False, err or f"systemctl {act} failed"
            return True, f"Service {act} successful"
        except FileNotFoundError:
            return False, "systemctl or sudo not found"

    @staticmethod
    def parse_logs(output: str) -> list[dict]:
        """Parse journalctl JSON output into log entries."""
        entries: list[dict] = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append({
                    "timestamp": entry.get("__REALTIME_TIMESTAMP", ""),
                    "message": entry.get("MESSAGE", ""),
                    "priority": int(entry.get("PRIORITY", 6)),
                    "pid": entry.get("_PID", ""),
                    "unit": entry.get("_SYSTEMD_UNIT", ""),
                })
            except (json.JSONDecodeError, ValueError):
                continue
        return entries

    @staticmethod
    async def get_logs(
        name: str,
        lines: int = 100,
        since: str | None = None,
    ) -> list[dict]:
        """Get journal logs for a service."""
        if not _validate_name(name):
            return []

        cmd = [
            "journalctl", "-u", name,
            "-n", str(lines),
            "--no-pager", "-o", "json",
        ]
        if since:
            cmd.extend(["--since", since])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return []
            return SystemdService.parse_logs(stdout.decode(errors="replace"))
        except FileNotFoundError:
            return []
