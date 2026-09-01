from __future__ import annotations

from pathlib import Path

verifier = Path("src/opportunity_engine/discovery/exa_shadow_page_verification.py")
text = verifier.read_text(encoding="utf-8")

constant_anchor = 'MAX_ALLOWED_PAGE_FETCHES = 30\n\n'
constant_replacement = '''MAX_ALLOWED_PAGE_FETCHES = 30\nSOURCE_NATIVE_VALUE_CAPTURE_VERSION = "SOURCE_NATIVE_VALUE_CAPTURE_V1"\nMAX_SOURCE_NATIVE_VALUE_CANDIDATES = 12\n\n'''
if "SOURCE_NATIVE_VALUE_CAPTURE_VERSION" not in text:
    if constant_anchor not in text:
        raise SystemExit("expected verifier constant anchor")
    text = text.replace(constant_anchor, constant_replacement, 1)

helper_anchor = '''def _compact(value: object) -> str:\n    return " ".join(str(value or "").split()).strip()\n\n\n'''
helper_replacement = '''def _compact(value: object) -> str:\n    return " ".join(str(value or "").split()).strip()\n\n\ndef _bounded_source_native_matches(\n    text: str, patterns: tuple[re.Pattern[str], ...]\n) -> list[str]:\n    """Capture bounded source-native numeric tokens without interpreting them."""\n    ordered: list[tuple[int, str]] = []\n    for pattern in patterns:\n        for match in pattern.finditer(text):\n            value = _compact(match.group(0))\n            if value:\n                ordered.append((match.start(), value))\n    ordered.sort(key=lambda item: item[0])\n\n    values: list[str] = []\n    seen: set[str] = set()\n    for _, value in ordered:\n        key = value.casefold()\n        if key in seen:\n            continue\n        seen.add(key)\n        values.append(value)\n        if len(values) >= MAX_SOURCE_NATIVE_VALUE_CANDIDATES:\n            break\n    return values\n\n\n'''
if "def _bounded_source_native_matches(" not in text:
    if helper_anchor not in text:
        raise SystemExit("expected verifier compact helper anchor")
    text = text.replace(helper_anchor, helper_replacement, 1)

old_evidence = '''        "price_evidence": has_price,\n        "quantity_evidence": has_quantity,\n        "item_specific_url_evidence": item_specific_url,\n'''
new_evidence = '''        "price_evidence": has_price,\n        "quantity_evidence": has_quantity,\n        "source_native_value_capture_version": SOURCE_NATIVE_VALUE_CAPTURE_VERSION,\n        "source_native_price_candidates": _bounded_source_native_matches(\n            combined_raw, (_PRICE_RE, _SCANDINAVIAN_DASH_PRICE_RE)\n        ),\n        "source_native_quantity_candidates": _bounded_source_native_matches(\n            combined_raw, (_QUANTITY_RE, _LABELED_QUANTITY_RE)\n        ),\n        "item_specific_url_evidence": item_specific_url,\n'''
if "source_native_price_candidates" not in text:
    if old_evidence not in text:
        raise SystemExit("expected verifier evidence anchor")
    text = text.replace(old_evidence, new_evidence, 1)
verifier.write_text(text, encoding="utf-8")

runner = Path("scripts/run_exa_exact_lot_checkpoint.py")
text = runner.read_text(encoding="utf-8")

candidate_anchor = '''    price_detected = evidence.get("price_evidence") is True\n    quantity_detected = evidence.get("quantity_evidence") is True\n    bounded_context = (\n'''
candidate_replacement = '''    price_detected = evidence.get("price_evidence") is True\n    quantity_detected = evidence.get("quantity_evidence") is True\n    raw_price_candidates = evidence.get("source_native_price_candidates") or []\n    raw_quantity_candidates = evidence.get("source_native_quantity_candidates") or []\n    price_candidates = (\n        [_compact(value) for value in raw_price_candidates if _compact(value)][:12]\n        if isinstance(raw_price_candidates, (list, tuple))\n        else []\n    )\n    quantity_candidates = (\n        [_compact(value) for value in raw_quantity_candidates if _compact(value)][:12]\n        if isinstance(raw_quantity_candidates, (list, tuple))\n        else []\n    )\n    value_capture_version = _compact(evidence.get("source_native_value_capture_version"))\n    bounded_context = (\n'''
if "raw_price_candidates = evidence.get(" not in text:
    if candidate_anchor not in text:
        raise SystemExit("expected candidate value-evidence anchor")
    text = text.replace(candidate_anchor, candidate_replacement, 1)

old_candidate_fields = '''        "source_native_price_evidence_detected": price_detected,\n        "source_native_quantity_evidence_detected": quantity_detected,\n        "source_value_normalization_required": True,\n        "verification": [\n'''
new_candidate_fields = '''        "source_native_price_evidence_detected": price_detected,\n        "source_native_quantity_evidence_detected": quantity_detected,\n        "source_native_value_capture_version": value_capture_version or None,\n        "source_native_price_candidates": price_candidates,\n        "source_native_quantity_candidates": quantity_candidates,\n        "source_value_normalization_required": True,\n        "verification": [\n'''
if '"source_native_value_capture_version": value_capture_version or None' not in text:
    if old_candidate_fields not in text:
        raise SystemExit("expected candidate output anchor")
    text = text.replace(old_candidate_fields, new_candidate_fields, 1)
runner.write_text(text, encoding="utf-8")


test = Path("tests/test_source_native_value_capture_v1.py")
test.write_text('''from __future__ import annotations\n\nimport importlib.util\nfrom pathlib import Path\n\nfrom opportunity_engine.discovery import exa_shadow_page_verification as verifier\n\n\nROOT = Path(__file__).resolve().parents[1]\nRUNNER = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"\n\n\ndef _load_runner():\n    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_value_capture", RUNNER)\n    assert spec is not None and spec.loader is not None\n    module = importlib.util.module_from_spec(spec)\n    spec.loader.exec_module(module)\n    return module\n\n\ndef test_classification_captures_bounded_source_native_price_and_quantity_tokens() -> None:\n    classification, evidence = verifier._classify_page(\n        title="Parti grossist restparti blandade kläder",\n        text=(\n            "Till salu. Vald Bodyconklänningar Nude (19 st). "\n            "Pris 929 kr. Alternativ 20 st. Pris 1 228 kr. "\n            "Varulager för grossist."\n        ),\n        url="https://cdon.se/produkt/parti-grossist-restparti-blandade-klader-123456",\n    )\n\n    assert classification == verifier.EXACT_LOT_CANDIDATE\n    assert evidence["price_evidence"] is True\n    assert evidence["quantity_evidence"] is True\n    assert evidence["source_native_value_capture_version"] == "SOURCE_NATIVE_VALUE_CAPTURE_V1"\n    assert evidence["source_native_price_candidates"] == ["929 kr", "1 228 kr"]\n    assert evidence["source_native_quantity_candidates"] == ["19 st", "20 st"]\n\n\ndef test_value_capture_is_bounded_and_deduplicated() -> None:\n    text = " ".join(["100 kr 20 st"] * 20)\n    _, evidence = verifier._classify_page(\n        title="Parti kläder till salu",\n        text=text,\n        url="https://example.se/product/wholesale-clothing-lot-42",\n    )\n\n    assert evidence["source_native_price_candidates"] == ["100 kr"]\n    assert evidence["source_native_quantity_candidates"] == ["20 st"]\n\n\ndef test_candidate_propagates_captured_values_without_enabling_financial_analysis() -> None:\n    runner = _load_runner()\n    row = {\n        "url": "https://example.se/product/wholesale-clothing-lot-42",\n        "final_url": "https://example.se/product/wholesale-clothing-lot-42",\n        "title": "Wholesale clothing lot",\n        "query": "Sverige restparti kläder grossist lager",\n        "exact_lot_origin": "DIRECT_SEARCH_RESULT",\n        "evidence": {\n            "project_domain": "CLOTHING_INVENTORY",\n            "item_specific_url_evidence": True,\n            "inventory_evidence": True,\n            "direct_sale_evidence": True,\n            "price_evidence": True,\n            "quantity_evidence": True,\n            "source_native_value_capture_version": "SOURCE_NATIVE_VALUE_CAPTURE_V1",\n            "source_native_price_candidates": ["929 kr"],\n            "source_native_quantity_candidates": ["19 st"],\n        },\n    }\n\n    candidate = runner._candidate_from_exact_lot(row, market="SE")\n\n    assert candidate["source_native_value_capture_version"] == "SOURCE_NATIVE_VALUE_CAPTURE_V1"\n    assert candidate["source_native_price_candidates"] == ["929 kr"]\n    assert candidate["source_native_quantity_candidates"] == ["19 st"]\n    assert candidate["source_value_normalization_required"] is True\n    assert candidate["analysis_eligible"] is False\n''', encoding="utf-8")
