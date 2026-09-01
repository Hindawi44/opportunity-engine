from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"{label} anchor not found")
    return text.replace(old, new, 1)


verifier_path = Path("src/opportunity_engine/discovery/exa_shadow_page_verification.py")
verifier = verifier_path.read_text(encoding="utf-8")

old = '''from opportunity_engine.discovery.keyword_shadow_verification import (\n    PageFetchResult,\n    fetch_public_page,\n)\n'''
new = old + '''from opportunity_engine.discovery.source_native_commercial_terms_capture import (\n    capture_source_native_commercial_terms,\n)\n'''
verifier = replace_once(verifier, old, new, "commercial terms import")

old = '''    project_domain = classify_project_domain(text=combined_raw)\n    domain_evidence = project_domain == CLOTHING_INVENTORY\n\n    evidence: dict[str, Any] = {\n'''
new = '''    project_domain = classify_project_domain(text=combined_raw)\n    domain_evidence = project_domain == CLOTHING_INVENTORY\n    commercial_terms_capture = capture_source_native_commercial_terms(combined_raw)\n\n    evidence: dict[str, Any] = {\n'''
verifier = replace_once(verifier, old, new, "commercial terms capture call")

old = '''        "source_native_quantity_candidates": _bounded_source_native_matches(\n            combined_raw, (_QUANTITY_RE, _LABELED_QUANTITY_RE)\n        ),\n        "item_specific_url_evidence": item_specific_url,\n'''
new = '''        "source_native_quantity_candidates": _bounded_source_native_matches(\n            combined_raw, (_QUANTITY_RE, _LABELED_QUANTITY_RE)\n        ),\n        "source_native_commercial_terms_capture_version": commercial_terms_capture["version"],\n        "source_native_condition_candidates": commercial_terms_capture["condition_candidates"],\n        "source_native_seller_identity_candidates": commercial_terms_capture["seller_identity_candidates"],\n        "source_native_fulfilment_candidates": commercial_terms_capture["fulfilment_candidates"],\n        "source_native_commercial_terms_capture_is_qualification_evidence": False,\n        "item_specific_url_evidence": item_specific_url,\n'''
verifier = replace_once(verifier, old, new, "commercial terms evidence fields")
verifier_path.write_text(verifier, encoding="utf-8")

runner_path = Path("scripts/run_exa_exact_lot_checkpoint.py")
runner = runner_path.read_text(encoding="utf-8")

old = '''    value_capture_version = _compact(evidence.get("source_native_value_capture_version"))\n    normalization = normalize_source_native_values(\n'''
new = '''    value_capture_version = _compact(evidence.get("source_native_value_capture_version"))\n    commercial_terms_capture_version = _compact(\n        evidence.get("source_native_commercial_terms_capture_version")\n    )\n    raw_condition_candidates = evidence.get("source_native_condition_candidates") or []\n    raw_seller_identity_candidates = evidence.get("source_native_seller_identity_candidates") or []\n    raw_fulfilment_candidates = evidence.get("source_native_fulfilment_candidates") or []\n    condition_candidates = (\n        [_compact(value) for value in raw_condition_candidates if _compact(value)][:8]\n        if isinstance(raw_condition_candidates, (list, tuple))\n        else []\n    )\n    seller_identity_candidates = (\n        [_compact(value) for value in raw_seller_identity_candidates if _compact(value)][:8]\n        if isinstance(raw_seller_identity_candidates, (list, tuple))\n        else []\n    )\n    fulfilment_candidates = (\n        [_compact(value) for value in raw_fulfilment_candidates if _compact(value)][:8]\n        if isinstance(raw_fulfilment_candidates, (list, tuple))\n        else []\n    )\n    normalization = normalize_source_native_values(\n'''
runner = replace_once(runner, old, new, "runner commercial terms parsing")

old = '''        "source_native_price_candidates": price_candidates,\n        "source_native_quantity_candidates": quantity_candidates,\n        "source_value_normalization_required": not values_normalized,\n'''
new = '''        "source_native_price_candidates": price_candidates,\n        "source_native_quantity_candidates": quantity_candidates,\n        "source_native_commercial_terms_capture_version": commercial_terms_capture_version or None,\n        "source_native_condition_candidates": condition_candidates,\n        "source_native_seller_identity_candidates": seller_identity_candidates,\n        "source_native_fulfilment_candidates": fulfilment_candidates,\n        "source_native_commercial_terms_capture_is_qualification_evidence": False,\n        "source_value_normalization_required": not values_normalized,\n'''
runner = replace_once(runner, old, new, "runner candidate commercial terms fields")

old = '''                "source_value_normalization_required": not values_normalized,\n                "source_value_normalization": normalization,\n                "verification_content_match": True,\n'''
new = '''                "source_value_normalization_required": not values_normalized,\n                "source_value_normalization": normalization,\n                "source_native_commercial_terms_capture_version": commercial_terms_capture_version or None,\n                "source_native_condition_candidates": condition_candidates,\n                "source_native_seller_identity_candidates": seller_identity_candidates,\n                "source_native_fulfilment_candidates": fulfilment_candidates,\n                "source_native_commercial_terms_capture_is_qualification_evidence": False,\n                "verification_content_match": True,\n'''
runner = replace_once(runner, old, new, "runner verification commercial terms fields")

runner_path.write_text(runner, encoding="utf-8")
