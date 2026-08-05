#!/usr/bin/env python3
"""Persist bounded source signals and write the daily domain bulletin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.blinto_generic_seller_guard import (
    sanitize_blinto_seller_identity_report,
)
from opportunity_engine.discovery.blinto_seller_identity_extraction import (
    write_blinto_seller_identity_evidence,
)
from opportunity_engine.discovery.brave_market_signal_continuity import (
    collect_manifest_brave_market_signals,
)
from opportunity_engine.discovery.domain_market_intelligence_feed import (
    build_domain_market_intelligence_brief,
    persist_manifest_market_signals,
)
from opportunity_engine.discovery.signal_role_freshness_correction import (
    write_corrected_market_bulletin_artifacts,
)
from opportunity_engine.discovery.sweden_organisation_discovery_bridge import (
    resolve_sweden_artifact_company_identities,
)
from opportunity_engine.discovery.sweden_valuable_datasets_status_feed import (
    collect_manifest_official_signals_with_sweden_status,
)


def _load_object(path: Path, name: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return payload


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rewrite_source_artifact(
    report: dict[str, Any],
    *,
    root: str | Path,
) -> None:
    raw_path = report.get("artifact_path")
    if not raw_path:
        return
    artifact_path = Path(str(raw_path))
    if not artifact_path.is_absolute():
        artifact_path = Path(root) / artifact_path
    _write_report(artifact_path, report)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--config-path", default="alembic.ini")
    args = parser.parse_args()

    checkpoint = _load_object(Path(args.checkpoint), "checkpoint")
    manifest = _load_object(Path(args.manifest), "manifest")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        blinto_seller_identity = write_blinto_seller_identity_evidence(
            manifest,
            root=args.root,
        )
        blinto_seller_identity = sanitize_blinto_seller_identity_report(
            blinto_seller_identity
        )
        _rewrite_source_artifact(blinto_seller_identity, root=args.root)
    except Exception as exc:
        blinto_seller_identity = {
            "schema_version": "blinto-seller-identity-extraction-1.0",
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "seller_evidence": [],
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    _write_report(
        output_dir / "blinto-seller-identity-extraction.json",
        blinto_seller_identity,
    )
    print(
        "blinto_seller_identity_extraction_status:",
        blinto_seller_identity.get("status"),
    )

    try:
        sweden_identity_bridge = resolve_sweden_artifact_company_identities(
            manifest,
            root=args.root,
            config_path=args.config_path,
        )
    except Exception as exc:
        sweden_identity_bridge = {
            "schema_version": "sweden-organisation-discovery-bridge-1.0",
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "resolved_organisations": [],
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    _write_report(
        output_dir / "sweden-organisation-discovery-bridge.json",
        sweden_identity_bridge,
    )
    print(
        "sweden_organisation_discovery_bridge_status:",
        sweden_identity_bridge.get("status"),
    )

    try:
        brave_radar = collect_manifest_brave_market_signals(
            manifest,
            root=args.root,
        )
    except Exception as exc:
        brave_radar = {
            "schema_version": "brave-market-signal-radar-1.0",
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "market_coverage": ["NO", "SE", "DE"],
            "signal_count": 0,
            "sources": [],
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    _write_report(
        output_dir / "brave-market-signal-radar.json",
        brave_radar,
    )
    print(
        "brave_market_signal_radar_status_counts:",
        json.dumps(brave_radar.get("status_counts") or {}, sort_keys=True),
    )

    official_coverage = collect_manifest_official_signals_with_sweden_status(
        manifest,
        root=args.root,
    )
    _write_report(
        output_dir / "official-early-signal-source-coverage.json",
        official_coverage,
    )
    print(
        "official_early_signal_status_counts:",
        json.dumps(official_coverage.get("status_counts") or {}, sort_keys=True),
    )

    persistence = persist_manifest_market_signals(
        manifest,
        root=args.root,
        config_path=args.config_path,
    )
    _write_report(
        output_dir / "domain-market-signal-persistence.json",
        persistence,
    )
    brief = build_domain_market_intelligence_brief(checkpoint, persistence)
    write_corrected_market_bulletin_artifacts(
        brief,
        persistence,
        json_path=output_dir / "domain-market-intelligence-brief.json",
        text_path=output_dir / "domain-market-intelligence-brief.txt",
    )
    print((output_dir / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
