from pathlib import Path


path = Path("scripts/run_exa_exact_lot_checkpoint.py")
text = path.read_text(encoding="utf-8")

old = "from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain\n"
new = old + "from opportunity_engine.discovery.source_native_value_normalization import normalize_source_native_values\n"
if new not in text:
    if old not in text:
        raise SystemExit("import anchor not found")
    text = text.replace(old, new, 1)

old = '''    value_capture_version = _compact(evidence.get("source_native_value_capture_version"))
    bounded_context = (
        "Strict Exact-Lot evidence: CLOTHING_INVENTORY subject, item-specific URL, inventory, "
        "direct sale, and source-native numeric price and quantity patterns were verified on the "
        "exact public page. Source values still require normalization before financial analysis."
    )
    missing_information = [
        "normalized source-native price value for financial analysis",
        "normalized source-native quantity value for financial analysis",
        "condition",
        "seller or company identity",
        "pickup or shipping terms",
    ]
    confirmed_information = [
        "clothing domain",
        "item-specific page",
        "inventory evidence",
        "direct-sale evidence",
        "source-native numeric price evidence" if price_detected else "price evidence",
        "source-native numeric quantity evidence" if quantity_detected else "quantity evidence",
    ]
'''
new = '''    value_capture_version = _compact(evidence.get("source_native_value_capture_version"))
    normalization = normalize_source_native_values(
        market=market,
        url=url,
        price_candidates=price_candidates,
        quantity_candidates=quantity_candidates,
    )
    values_normalized = normalization.get("status") == "NORMALIZED"
    bounded_context = (
        "Strict Exact-Lot evidence: CLOTHING_INVENTORY subject, item-specific URL, inventory, "
        "direct sale, and source-native numeric price and quantity patterns were verified on the "
        "exact public page. The single unambiguous source price/quantity pair was normalized "
        "without currency conversion, tax, customs or logistics calculation."
        if values_normalized
        else
        "Strict Exact-Lot evidence: CLOTHING_INVENTORY subject, item-specific URL, inventory, "
        "direct sale, and source-native numeric price and quantity patterns were verified on the "
        "exact public page. Source values remain ambiguous or unsupported for normalization."
    )
    missing_information = [
        "condition",
        "seller or company identity",
        "pickup or shipping terms",
    ]
    if not values_normalized:
        missing_information[:0] = [
            "normalized source-native price value for financial analysis",
            "normalized source-native quantity value for financial analysis",
        ]
    confirmed_information = [
        "clothing domain",
        "item-specific page",
        "inventory evidence",
        "direct-sale evidence",
        "source-native numeric price evidence" if price_detected else "price evidence",
        "source-native numeric quantity evidence" if quantity_detected else "quantity evidence",
    ]
    if values_normalized:
        confirmed_information.append("normalized source-native price and quantity values")
'''
if new not in text:
    if old not in text:
        raise SystemExit("candidate normalization anchor not found")
    text = text.replace(old, new, 1)

text = text.replace(
    '        "source_value_normalization_required": True,\n        "verification": [',
    '        "source_value_normalization_required": not values_normalized,\n        "source_value_normalization": normalization,\n        "verification": [',
    1,
)
text = text.replace(
    '                "source_value_normalization_required": True,\n                "verification_content_match": True,',
    '                "source_value_normalization_required": not values_normalized,\n                "source_value_normalization": normalization,\n                "verification_content_match": True,',
    1,
)

old = '''        "next_verification_step": (
            "Normalize the already verified source-native price and quantity values, then confirm "
            "condition, seller identity and pickup/shipping terms before financial analysis."
        ),
'''
new = '''        "next_verification_step": (
            "Confirm condition, seller identity and pickup/shipping terms before financial analysis."
            if values_normalized
            else
            "Resolve source price/quantity ambiguity or unsupported formatting, then confirm "
            "condition, seller identity and pickup/shipping terms before financial analysis."
        ),
'''
if new not in text:
    if old not in text:
        raise SystemExit("next step anchor not found")
    text = text.replace(old, new, 1)

text = text.replace(
    '"schema_version": "exa-exact-lot-checkpoint-bridge-1.8",',
    '"schema_version": "exa-exact-lot-checkpoint-bridge-1.9",',
    1,
)
old = '''        "source_value_normalization_required_count": sum(
            1 for candidate in candidates if candidate.get("source_value_normalization_required") is True
        ),
'''
new = '''        "source_value_normalized_count": sum(
            1
            for candidate in candidates
            if (candidate.get("source_value_normalization") or {}).get("status") == "NORMALIZED"
        ),
        "source_value_normalization_required_count": sum(
            1 for candidate in candidates if candidate.get("source_value_normalization_required") is True
        ),
'''
if new not in text:
    if old not in text:
        raise SystemExit("report count anchor not found")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
