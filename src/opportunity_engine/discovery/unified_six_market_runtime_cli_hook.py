"""Emit the six-market runtime authority after daily enrichment is complete.

The existing daily checkpoint still owns source execution while migration is in
progress. The workflow then enriches lifecycle state, reconciles human review,
and builds the domain-intelligence bulletin. This hook runs only at the end of
that final bulletin CLI, when the NO/SE/DE checkpoint and FR/IT/NL market-cycle
artifacts are all present and the core checkpoint already contains its final
lifecycle/review state for the run.
"""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from opportunity_engine.discovery.unified_six_market_pipeline import (
    build_unified_six_market_pipeline,
)


UNIFIED_PIPELINE_FILENAME = "unified-six-market-pipeline-v1.json"
UNIFIED_PHONE_SUMMARY_FILENAME = "unified-six-market-phone-summary-v1.txt"
LEGACY_CORE_FILENAME = "multi-market-daily-checkpoint.json"
FRANCE_CYCLE_FILENAME = "france-case-memory-v1.json"
ITALY_CYCLE_FILENAME = "italy-case-memory-v1.json"
NETHERLANDS_CYCLE_FILENAME = "netherlands-case-memory-v1.json"
_TARGET_CLI = "build_domain_market_intelligence_feed.py"
_INSTALLED = False


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _stage_status(market: Mapping[str, Any], stage_name: str) -> str:
    for stage in market.get("stages") or []:
        if isinstance(stage, Mapping) and stage.get("stage") == stage_name:
            return str(stage.get("status") or "UNKNOWN")
    return "UNKNOWN"


def render_unified_phone_summary(ledger: Mapping[str, Any]) -> str:
    """Render the operator-facing six-market path without legacy side labels."""
    rows = ledger.get("markets") or []
    lines = [
        "ملخص المسار الموحد — 6 أسواق",
        f"الوقت: {ledger.get('generated_at')}",
        "التغطية: NO | SE | DE | FR | IT | NL",
        "المسار: Discovery → Validation → Entity → Memory → Follow-up → Exact Lot → Commercial Qualification → Evidence → Decision → Report",
    ]
    for market in rows:
        if not isinstance(market, Mapping):
            continue
        code = str(market.get("market_code") or "?")
        lines.append(
            f"{code}: اكتشاف {_stage_status(market, 'DISCOVERY')} | "
            f"Exact Lot {_stage_status(market, 'EXACT_LOT_VERIFICATION')} | "
            f"تجاري {_stage_status(market, 'COMMERCIAL_QUALIFICATION')} | "
            f"قرار {_stage_status(market, 'OPPORTUNITY_DECISION')}"
        )
    lines.extend(
        [
            "أي قدرة غير مبنية تظهر صراحة ولا يتم تجاوزها.",
            "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_unified_runtime_artifacts(output_dir: str | Path) -> dict[str, Path]:
    """Build the authoritative six-market daily view from final current truth."""
    root = Path(output_dir)
    core = _load_json(root / LEGACY_CORE_FILENAME)
    france_cycle = _load_json(root / FRANCE_CYCLE_FILENAME)
    italy_cycle = _load_json(root / ITALY_CYCLE_FILENAME)
    netherlands_cycle = _load_json(root / NETHERLANDS_CYCLE_FILENAME)

    ledger = build_unified_six_market_pipeline(
        core,
        france_sidecar=france_cycle,
        italy_sidecar=italy_cycle,
        netherlands_sidecar=netherlands_cycle,
    )
    ledger["runtime_authority"] = "PRIMARY_DAILY_OPERATOR_VIEW"
    ledger["runtime_emission_stage"] = "AFTER_LIFECYCLE_REVIEW_AND_DOMAIN_INTELLIGENCE"
    ledger["legacy_three_market_checkpoint_retained"] = True
    ledger["legacy_compatibility_input"] = LEGACY_CORE_FILENAME
    ledger["runtime_input_files"] = [
        LEGACY_CORE_FILENAME,
        FRANCE_CYCLE_FILENAME,
        ITALY_CYCLE_FILENAME,
        NETHERLANDS_CYCLE_FILENAME,
    ]

    pipeline_path = root / UNIFIED_PIPELINE_FILENAME
    summary_path = root / UNIFIED_PHONE_SUMMARY_FILENAME
    pipeline_path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(render_unified_phone_summary(ledger), encoding="utf-8")
    return {"pipeline": pipeline_path, "phone_summary": summary_path}


def _output_dir_from_argv(argv: list[str]) -> Path:
    for index, value in enumerate(argv):
        if value == "--output-dir" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if value.startswith("--output-dir="):
            return Path(value.split("=", 1)[1])
    return Path("artifacts/multi-market-daily-operator-checkpoint")


def _emit_after_daily_cli() -> None:
    if Path(sys.argv[0]).name != _TARGET_CLI:
        return
    output_dir = _output_dir_from_argv(sys.argv)
    core_path = output_dir / LEGACY_CORE_FILENAME
    if not core_path.exists():
        # Upstream failed before a checkpoint existed; preserve that original
        # failure instead of replacing it with a secondary runtime error.
        return

    required = [
        output_dir / FRANCE_CYCLE_FILENAME,
        output_dir / ITALY_CYCLE_FILENAME,
        output_dir / NETHERLANDS_CYCLE_FILENAME,
    ]
    missing = [path.name for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Unified six-market runtime cannot be emitted; missing market cycle artifacts: "
            + ", ".join(missing)
        )

    paths = build_unified_runtime_artifacts(output_dir)
    print(f"unified_pipeline: {paths['pipeline']}")
    print(f"unified_phone_summary: {paths['phone_summary']}")


def install_unified_six_market_runtime_cli_hook() -> bool:
    """Register the final daily six-market emitter for the bulletin CLI only."""
    global _INSTALLED
    if _INSTALLED:
        return False
    if Path(sys.argv[0]).name != _TARGET_CLI:
        return False
    atexit.register(_emit_after_daily_cli)
    _INSTALLED = True
    return True
