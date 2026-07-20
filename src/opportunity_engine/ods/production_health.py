"""Production readiness checks for the opportunity engine.

The checker validates local runtime prerequisites without contacting external services
or exposing secret values. Optional connectors are reported as configured only when
all required environment variables for that connector are present.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Mapping


@dataclass(frozen=True)
class HealthCheckItem:
    name: str
    status: str
    message: str
    required: bool = True


@dataclass(frozen=True)
class ProductionHealthReport:
    status: str
    ready: bool
    checks: tuple[HealthCheckItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "ready": self.ready,
            "checks": [asdict(item) for item in self.checks],
        }


class ProductionHealthChecker:
    """Run deterministic local checks required before a production execution."""

    REQUIRED_MODULES = (
        "opportunity_engine.ods.daily_pipeline",
        "opportunity_engine.ods.opportunity_discovery",
        "opportunity_engine.ods.smart_alerts",
        "opportunity_engine.ods.capital_allocation",
        "opportunity_engine.ods.portfolio_manager",
    )

    CONNECTOR_ENV_GROUPS = {
        "FINN.no": ("FINN_API_KEY", "FINN_ORG_ID"),
        "Konkurskupp": ("KONKURSKUPP_FEED_URL",),
        "Bjarøy": ("BJAROY_FEED_URL",),
        "Konkurs.app": ("KONKURS_APP_FEED_URL",),
    }

    def run(
        self,
        *,
        data_directory: str | Path = "data",
        environment: Mapping[str, str] | None = None,
    ) -> ProductionHealthReport:
        env = environment if environment is not None else os.environ
        checks: list[HealthCheckItem] = []

        for module_name in self.REQUIRED_MODULES:
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # pragma: no cover - exact import failure varies
                checks.append(HealthCheckItem(module_name, "fail", f"Import failed: {exc}"))
            else:
                checks.append(HealthCheckItem(module_name, "pass", "Module import succeeded."))

        data_path = Path(data_directory)
        try:
            data_path.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", dir=data_path, prefix=".health-", delete=True) as handle:
                handle.write("ok")
                handle.flush()
        except OSError as exc:
            checks.append(HealthCheckItem("data_directory", "fail", f"Directory is not writable: {exc}"))
        else:
            checks.append(HealthCheckItem("data_directory", "pass", f"Writable: {data_path}"))

        for connector, variables in self.CONNECTOR_ENV_GROUPS.items():
            present = [bool(str(env.get(name, "")).strip()) for name in variables]
            if any(present) and not all(present):
                missing = [name for name, exists in zip(variables, present) if not exists]
                checks.append(
                    HealthCheckItem(
                        f"connector:{connector}",
                        "fail",
                        "Incomplete configuration; missing " + ", ".join(missing),
                    )
                )
            elif all(present):
                checks.append(
                    HealthCheckItem(
                        f"connector:{connector}",
                        "pass",
                        "Authorized connector configuration is complete.",
                        required=False,
                    )
                )
            else:
                checks.append(
                    HealthCheckItem(
                        f"connector:{connector}",
                        "warn",
                        "Optional connector is not configured.",
                        required=False,
                    )
                )

        required_failures = [item for item in checks if item.required and item.status == "fail"]
        ready = not required_failures
        status = "healthy" if ready else "unhealthy"
        return ProductionHealthReport(status=status, ready=ready, checks=tuple(checks))

    def write_report(
        self,
        path: str | Path,
        *,
        data_directory: str | Path = "data",
        environment: Mapping[str, str] | None = None,
    ) -> ProductionHealthReport:
        report = self.run(data_directory=data_directory, environment=environment)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output)
        return report
