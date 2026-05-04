import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import AttackLogEntry


class AttackLogger:
    """Logs attack events to daily JSONL files with rotation."""

    def __init__(self, log_dir: Path, max_size_mb: int = 100, max_files: int = 30):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_files = max_files

    def _current_log_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"attacks-{date_str}.jsonl"

    def log(self, entry: AttackLogEntry) -> None:
        log_file = self._current_log_file()
        line = json.dumps(entry.model_dump()) + "\n"

        # Check size before writing
        if log_file.exists() and log_file.stat().st_size > self.max_size_bytes:
            self._rotate(log_file)

        with open(log_file, "a") as f:
            f.write(line)

        self._cleanup_old_files()

    def _rotate(self, log_file: Path) -> None:
        """Rotate a log file by renaming with a sequence number."""
        for i in range(99, 0, -1):
            src = log_file.with_suffix(f".{i}.jsonl") if i > 1 else log_file
            dst = log_file.with_suffix(f".{i + 1}.jsonl")
            if src.exists():
                src.rename(dst)

    def _cleanup_old_files(self) -> None:
        """Remove old log files beyond max_files limit."""
        log_files = sorted(self.log_dir.glob("attacks-*.jsonl"), reverse=True)
        for old_file in log_files[self.max_files:]:
            old_file.unlink(missing_ok=True)

    def query(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        source_ip: Optional[str] = None,
        category: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query attack logs with filters."""
        results = []
        log_files = sorted(self.log_dir.glob("attacks-*.jsonl"), reverse=True)

        skipped = 0
        for log_file in log_files:
            try:
                with open(log_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)

                        # Apply filters
                        if start_time and entry.get("timestamp", 0) < start_time:
                            continue
                        if end_time and entry.get("timestamp", 0) > end_time:
                            continue
                        if source_ip and entry.get("source_ip") != source_ip:
                            continue
                        if category and entry.get("category") != category:
                            continue
                        if action and entry.get("action") != action:
                            continue

                        if skipped < offset:
                            skipped += 1
                            continue

                        results.append(entry)
                        if len(results) >= limit:
                            return results
            except (json.JSONDecodeError, OSError):
                continue

        return results

    def get_stats(self, hours: int = 24) -> dict:
        """Get attack statistics for the last N hours."""
        cutoff = time.time() - (hours * 3600)
        entries = self.query(start_time=cutoff, limit=10000)

        categories: dict[str, int] = {}
        top_ips: dict[str, int] = {}
        actions: dict[str, int] = {}

        for entry in entries:
            cat = entry.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

            ip = entry.get("source_ip", "unknown")
            top_ips[ip] = top_ips.get(ip, 0) + 1

            act = entry.get("action", "unknown")
            actions[act] = actions.get(act, 0) + 1

        # Sort top IPs by count
        sorted_ips = sorted(top_ips.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total": len(entries),
            "period_hours": hours,
            "categories": categories,
            "actions": actions,
            "top_ips": [{"ip": ip, "count": count} for ip, count in sorted_ips],
        }
