from __future__ import annotations

import asyncio
import re


class ScreenService:
    """Manage screen and tmux sessions."""

    # ---- screen ----

    @staticmethod
    async def list_screen() -> list[dict]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "screen", "-ls",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            # screen -ls returns 1 when sessions exist, 0 when none
            return ScreenService.parse_screen(stdout.decode(errors="replace"))
        except FileNotFoundError:
            return []

    @staticmethod
    def parse_screen(output: str) -> list[dict]:
        sessions: list[dict] = []
        for line in output.split("\n"):
            line = line.strip()
            if not line or not line[0].isdigit():
                continue
            # Format: <PID>.<name> \t (optional date) \t (Status)
            m = re.match(r"(\d+)\.(\S+)", line)
            if not m:
                continue
            status = "Unknown"
            sm = re.search(r"\((\w+)[^)]*\)\s*$", line)
            if sm:
                status = sm.group(1)
            sessions.append({
                "type": "screen",
                "id": m.group(1) + "." + m.group(2),
                "name": m.group(2),
                "status": status,
                "windows": None,
                "created": None,
            })
        return sessions

    @staticmethod
    async def create_screen(name: str, command: str = "") -> bool:
        cmd: list[str] = ["screen", "-dmS", name]
        if command:
            cmd += ["bash", "-c", command]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        return proc.returncode == 0

    @staticmethod
    async def kill_screen(session_id: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "screen", "-X", "-S", session_id, "quit",
        )
        await proc.communicate()
        return proc.returncode == 0

    # ---- tmux ----

    @staticmethod
    async def list_tmux() -> list[dict]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "list-sessions", "-F",
                "#{session_name}\t#{session_windows}\t#{session_created}\t#{session_attached}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return []
            return ScreenService.parse_tmux(stdout.decode(errors="replace"))
        except FileNotFoundError:
            return []

    @staticmethod
    def parse_tmux(output: str) -> list[dict]:
        sessions: list[dict] = []
        for line in output.split("\n"):
            parts = line.strip().split("\t")
            if len(parts) < 4 or not parts[0]:
                continue
            sessions.append({
                "type": "tmux",
                "id": parts[0],
                "name": parts[0],
                "windows": int(parts[1]) if parts[1].isdigit() else None,
                "created": parts[2] if parts[2] else None,
                "status": "Attached" if parts[3] != "0" else "Detached",
            })
        return sessions

    @staticmethod
    async def create_tmux(name: str, command: str = "") -> bool:
        cmd: list[str] = ["tmux", "new-session", "-d", "-s", name]
        if command:
            cmd += [command]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        return proc.returncode == 0

    @staticmethod
    async def kill_tmux(name: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "tmux", "kill-session", "-t", name,
        )
        await proc.communicate()
        return proc.returncode == 0

    # ---- availability ----

    @staticmethod
    async def check_available() -> dict:
        result = {"screen": False, "tmux": False}
        for tool, flag in [("screen", "--version"), ("tmux", "-V")]:
            try:
                p = await asyncio.create_subprocess_exec(
                    tool, flag,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await p.communicate()
                result[tool] = True
            except FileNotFoundError:
                pass
        return result

    # ---- combined ----

    @staticmethod
    async def list_all() -> list[dict]:
        screen_sessions, tmux_sessions = await asyncio.gather(
            ScreenService.list_screen(),
            ScreenService.list_tmux(),
        )
        return screen_sessions + tmux_sessions
