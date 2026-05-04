from __future__ import annotations

import asyncio
import hashlib
import re


# Lock to prevent concurrent crontab read-modify-write races
_crontab_lock = asyncio.Lock()


def _job_id(raw_line: str) -> str:
    """Deterministic ID from the raw crontab line."""
    return hashlib.md5(raw_line.strip().encode()).hexdigest()[:12]


def _human_schedule(minute: str, hour: str, day: str, month: str, weekday: str) -> str:
    """Convert cron fields to a human-readable string for common patterns."""
    DAYS = {
        "0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed",
        "4": "Thu", "5": "Fri", "6": "Sat", "7": "Sun",
    }

    if minute == "*" and hour == "*" and day == "*" and month == "*" and weekday == "*":
        return "Every minute"

    if hour == "*" and day == "*" and month == "*" and weekday == "*":
        if minute == "0":
            return "Every hour"
        if minute.startswith("*/"):
            return f"Every {minute[2:]} minutes"

    if day == "*" and month == "*" and weekday == "*":
        if minute.startswith("*/") and hour == "*":
            return f"Every {minute[2:]} minutes"
        if hour.startswith("*/"):
            return f"Every {hour[2:]} hours"
        time_str = f"{hour}:{minute.zfill(2)}"
        return f"Every day at {time_str}"

    if day == "*" and month == "*" and weekday != "*":
        time_str = f"{hour}:{minute.zfill(2)}"
        if weekday == "1-5":
            return f"Weekdays at {time_str}"
        if weekday == "0,6" or weekday == "6,0":
            return f"Weekends at {time_str}"
        day_names = []
        for d in weekday.split(","):
            d = d.strip()
            if d in DAYS:
                day_names.append(DAYS[d])
            else:
                day_names.append(d)
        return f"{','.join(day_names)} at {time_str}"

    if weekday == "*" and month == "*":
        time_str = f"{hour}:{minute.zfill(2)}"
        if day == "1":
            return f"Monthly on the 1st at {time_str}"
        return f"Monthly on day {day} at {time_str}"

    return f"{minute} {hour} {day} {month} {weekday}"


class CronService:
    """Manage crontab entries."""

    @staticmethod
    def validate_schedule(expression: str) -> tuple[bool, str]:
        """Validate a 5-field cron expression. Returns (valid, error_or_human)."""
        parts = expression.strip().split()
        if len(parts) != 5:
            return False, "Must have exactly 5 fields: minute hour day month weekday"

        patterns = [
            (r"^(\*|(\*/\d+)|(\d+(-\d+)?(,\d+(-\d+)?)*))$", "minute", 0, 59),
            (r"^(\*|(\*/\d+)|(\d+(-\d+)?(,\d+(-\d+)?)*))$", "hour", 0, 23),
            (r"^(\*|(\*/\d+)|(\d+(-\d+)?(,\d+(-\d+)?)*))$", "day", 1, 31),
            (r"^(\*|(\*/\d+)|(\d+(-\d+)?(,\d+(-\d+)?)*))$", "month", 1, 12),
            (r"^(\*|(\*/\d+)|(\d+(-\d+)?(,\d+(-\d+)?)*))$", "weekday", 0, 7),
        ]

        for i, (pattern, name, lo, hi) in enumerate(patterns):
            field = parts[i]
            if not re.match(pattern, field):
                return False, f"Invalid {name} field: {field}"
            # Range check for literal numbers
            for num_str in re.findall(r"\d+", field):
                num = int(num_str)
                if field.startswith("*/"):
                    if num < 1:
                        return False, f"Step in {name} must be >= 1"
                else:
                    if num < lo or num > hi:
                        return False, f"{name} value {num} out of range ({lo}-{hi})"

        human = _human_schedule(*parts)
        return True, human

    @staticmethod
    def parse_crontab(output: str) -> list[dict]:
        """Parse crontab -l output into structured job dicts."""
        jobs: list[dict] = []
        lines = output.split("\n")
        description = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                description = ""
                continue

            # Lines starting with # could be: disabled jobs, description comments, or other comments
            if stripped.startswith("#"):
                raw_uncommented = stripped.lstrip("# ").strip()
                # Check if this is a disabled cron job
                parts = raw_uncommented.split(None, 5)
                if len(parts) >= 6:
                    sched = " ".join(parts[:5])
                    valid, _ = CronService.validate_schedule(sched)
                    if valid:
                        command = parts[5]
                        human = _human_schedule(*parts[:5])
                        jobs.append({
                            "id": _job_id(raw_uncommented),
                            "schedule": sched,
                            "command": command,
                            "description": description,
                            "enabled": False,
                            "raw": raw_uncommented,
                            "human_schedule": human,
                        })
                        description = ""
                        continue
                # Not a disabled job — treat as description comment if it looks like one
                if stripped.startswith("# ") and "=" not in stripped:
                    description = stripped[2:].strip()
                else:
                    description = ""
                continue

            # Active cron line
            parts = stripped.split(None, 5)
            if len(parts) < 6:
                description = ""
                continue

            sched = " ".join(parts[:5])
            valid, _ = CronService.validate_schedule(sched)
            if not valid:
                description = ""
                continue

            command = parts[5]
            human = _human_schedule(*parts[:5])
            jobs.append({
                "id": _job_id(stripped),
                "schedule": sched,
                "command": command,
                "description": description,
                "enabled": True,
                "raw": stripped,
                "human_schedule": human,
            })
            description = ""

        return jobs

    @staticmethod
    async def _read_crontab(user: str | None = None) -> str:
        """Read current crontab. Returns empty string if no crontab."""
        cmd: list[str] = ["crontab", "-l"]
        if user:
            cmd.extend(["-u", user])
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return ""
            return stdout.decode(errors="replace")
        except FileNotFoundError:
            return ""

    @staticmethod
    async def _write_crontab(content: str, user: str | None = None) -> bool:
        """Write content to crontab via stdin."""
        cmd: list[str] = ["crontab", "-"]
        if user:
            cmd.extend(["-u", user])
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(input=content.encode())
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    @staticmethod
    async def list_jobs(user: str | None = None) -> list[dict]:
        output = await CronService._read_crontab(user)
        return CronService.parse_crontab(output)

    @staticmethod
    async def create_job(
        minute: str, hour: str, day: str, month: str, weekday: str,
        command: str, description: str = "", user: str | None = None,
    ) -> dict | None:
        schedule = f"{minute} {hour} {day} {month} {weekday}"
        cron_line = f"{schedule} {command}"

        async with _crontab_lock:
            current = await CronService._read_crontab(user)
            lines = current.rstrip("\n").split("\n") if current.strip() else []

            if description:
                lines.append(f"# {description}")
            lines.append(cron_line)

            new_content = "\n".join(lines) + "\n"
            ok = await CronService._write_crontab(new_content, user)
            if not ok:
                return None

        human = _human_schedule(minute, hour, day, month, weekday)
        return {
            "id": _job_id(cron_line),
            "schedule": schedule,
            "command": command,
            "description": description,
            "enabled": True,
            "raw": cron_line,
            "human_schedule": human,
        }

    @staticmethod
    async def update_job(
        job_id: str, minute: str | None = None, hour: str | None = None,
        day: str | None = None, month: str | None = None,
        weekday: str | None = None, command: str | None = None,
        description: str | None = None, user: str | None = None,
    ) -> dict | None:
        async with _crontab_lock:
            current = await CronService._read_crontab(user)
            jobs = CronService.parse_crontab(current)

            target = None
            for j in jobs:
                if j["id"] == job_id:
                    target = j
                    break
            if not target:
                return None

            # Build updated fields
            old_parts = target["schedule"].split()
            new_minute = minute if minute is not None else old_parts[0]
            new_hour = hour if hour is not None else old_parts[1]
            new_day = day if day is not None else old_parts[2]
            new_month = month if month is not None else old_parts[3]
            new_weekday = weekday if weekday is not None else old_parts[4]
            new_command = command if command is not None else target["command"]

            new_schedule = f"{new_minute} {new_hour} {new_day} {new_month} {new_weekday}"
            new_line = f"{new_schedule} {new_command}"
            if not target["enabled"]:
                new_line = f"# {new_line}"

            # Replace in raw crontab
            lines = current.split("\n")
            old_raw = target["raw"]
            if not target["enabled"]:
                old_raw_commented = f"# {old_raw}"
            else:
                old_raw_commented = None

            new_lines = []
            replaced = False
            skip_next_description = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Check if this is the description comment for the target job
                if not replaced and description is not None:
                    if stripped.startswith("# ") and "=" not in stripped:
                        # Look ahead to see if next non-empty line is our target
                        for ahead in lines[i + 1:]:
                            a = ahead.strip()
                            if not a:
                                continue
                            if a == target["raw"] or (old_raw_commented and a == old_raw_commented):
                                skip_next_description = True
                            break

                if skip_next_description and stripped.startswith("# ") and "=" not in stripped:
                    skip_next_description = False
                    if description:
                        new_lines.append(f"# {description}")
                    continue

                if not replaced and (
                    stripped == target["raw"]
                    or (old_raw_commented and stripped == old_raw_commented)
                ):
                    if description is not None and description and not any(
                        l.strip().startswith("# ") and "=" not in l
                        for l in new_lines[-1:]
                        if l.strip()
                    ):
                        new_lines.append(f"# {description}")
                    new_lines.append(new_line)
                    replaced = True
                    continue

                new_lines.append(line)

            if not replaced:
                return None

            new_content = "\n".join(new_lines)
            if not new_content.endswith("\n"):
                new_content += "\n"
            ok = await CronService._write_crontab(new_content, user)
            if not ok:
                return None

        human = _human_schedule(new_minute, new_hour, new_day, new_month, new_weekday)
        actual_raw = new_line.lstrip("# ").strip()
        return {
            "id": _job_id(actual_raw),
            "schedule": new_schedule,
            "command": new_command,
            "description": description if description is not None else target["description"],
            "enabled": target["enabled"],
            "raw": actual_raw,
            "human_schedule": human,
        }

    @staticmethod
    async def delete_job(job_id: str, user: str | None = None) -> bool:
        async with _crontab_lock:
            current = await CronService._read_crontab(user)
            jobs = CronService.parse_crontab(current)

            target = None
            for j in jobs:
                if j["id"] == job_id:
                    target = j
                    break
            if not target:
                return False

            lines = current.split("\n")
            target_raw = target["raw"]
            if not target["enabled"]:
                target_commented = f"# {target_raw}"
            else:
                target_commented = None

            new_lines = []
            removed = False
            for i, line in enumerate(lines):
                stripped = line.strip()

                if not removed and (
                    stripped == target_raw
                    or (target_commented and stripped == target_commented)
                ):
                    # Remove preceding description comment
                    if new_lines and new_lines[-1].strip().startswith("# ") and "=" not in new_lines[-1]:
                        new_lines.pop()
                    removed = True
                    continue

                new_lines.append(line)

            if not removed:
                return False

            new_content = "\n".join(new_lines)
            if new_content.strip():
                if not new_content.endswith("\n"):
                    new_content += "\n"
            else:
                new_content = ""

            return await CronService._write_crontab(new_content, user)

    @staticmethod
    async def toggle_job(job_id: str, enabled: bool, user: str | None = None) -> bool:
        async with _crontab_lock:
            current = await CronService._read_crontab(user)
            jobs = CronService.parse_crontab(current)

            target = None
            for j in jobs:
                if j["id"] == job_id:
                    target = j
                    break
            if not target:
                return False

            if target["enabled"] == enabled:
                return True  # Already in desired state

            lines = current.split("\n")
            target_raw = target["raw"]

            new_lines = []
            toggled = False
            for line in lines:
                stripped = line.strip()
                if not toggled:
                    if enabled and (stripped == f"# {target_raw}" or stripped == f"#{target_raw}"):
                        new_lines.append(target_raw)
                        toggled = True
                        continue
                    elif not enabled and stripped == target_raw:
                        new_lines.append(f"# {target_raw}")
                        toggled = True
                        continue
                new_lines.append(line)

            if not toggled:
                return False

            new_content = "\n".join(new_lines)
            if not new_content.endswith("\n"):
                new_content += "\n"
            return await CronService._write_crontab(new_content, user)
