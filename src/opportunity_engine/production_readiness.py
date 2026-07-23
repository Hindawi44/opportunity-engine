"""Production readiness audit for Opportunity Engine v2.6.6.

The audit verifies configuration and dry-run artifacts without exposing secrets.
It never performs purchases, bids, or buyer outreach.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    name: str
    passed: bool
    required: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    ready: bool
    checks: tuple[ReadinessCheck, ...]

    def to_dict(self) -> dict:
        return {"ready": self.ready, "checks": [asdict(item) for item in self.checks]}


class ProductionReadinessAuditor:
    """Audit environment and files while keeping secret values private."""

    def audit(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        daily_script: str | Path = "scripts/run_daily_pipeline.py",
        investment_files_dir: str | Path = "data/investment_files",
        usage_log: str | Path = "data/brave_usage.jsonl",
        require_live_secret: bool = True,
    ) -> ReadinessReport:
        env = environment if environment is not None else os.environ
        checks: list[ReadinessCheck] = []

        brave_present = bool((env.get("BRAVE_API_KEY") or env.get("BRAVE_SEARCH_API_KEY") or "").strip())
        checks.append(ReadinessCheck(
            "brave_secret_present",
            brave_present,
            require_live_secret,
            "Brave secret is configured" if brave_present else "Brave secret is not available to this runtime",
        ))

        max_requests = self._positive_int(env.get("BRAVE_MAX_REQUESTS_PER_RUN", "8"))
        checks.append(ReadinessCheck(
            "request_budget_valid",
            max_requests is not None and max_requests <= 20,
            True,
            f"BRAVE_MAX_REQUESTS_PER_RUN={max_requests}" if max_requests is not None else "Request budget must be a positive integer",
        ))

        cache_hours = self._positive_int(env.get("BRAVE_CACHE_TTL_HOURS", "24"))
        checks.append(ReadinessCheck(
            "cache_ttl_valid",
            cache_hours is not None,
            True,
            f"BRAVE_CACHE_TTL_HOURS={cache_hours}" if cache_hours is not None else "Cache TTL must be a positive integer",
        ))

        script_path = Path(daily_script)
        script_ok = script_path.is_file()
        checks.append(ReadinessCheck(
            "daily_pipeline_script_present",
            script_ok,
            True,
            str(script_path),
        ))

        investment_path = Path(investment_files_dir)
        checks.append(ReadinessCheck(
            "investment_directory_writable",
            self._directory_writable(investment_path),
            True,
            str(investment_path),
        ))

        usage_path = Path(usage_log)
        checks.append(ReadinessCheck(
            "usage_log_parent_writable",
            self._directory_writable(usage_path.parent),
            True,
            str(usage_path.parent),
        ))

        ready = all(item.passed for item in checks if item.required)
        return ReadinessReport(ready=ready, checks=tuple(checks))

    @staticmethod
    def inspect_dry_run(first_run: str | Path, second_run: str | Path) -> dict:
        """Compare two JSON run summaries and report cache/repeat protection signals."""
        first = json.loads(Path(first_run).read_text(encoding="utf-8"))
        second = json.loads(Path(second_run).read_text(encoding="utf-8"))
        first_searches = int(first.get("external_searches_executed", first.get("searches_executed", 0)) or 0)
        second_searches = int(second.get("external_searches_executed", second.get("searches_executed", 0)) or 0)
        second_cache = int(second.get("external_cache_hits", second.get("cache_hits", 0)) or 0)
        return {
            "first_searches": first_searches,
            "second_searches": second_searches,
            "second_cache_hits": second_cache,
            "repeat_protection_observed": second_searches <= first_searches and (second_cache > 0 or second_searches == 0),
        }

    @staticmethod
    def _positive_int(value: str) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _directory_writable(path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".readiness_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False
