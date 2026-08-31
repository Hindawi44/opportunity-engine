from __future__ import annotations

from pathlib import Path

runner = Path("scripts/run_exa_exact_lot_checkpoint.py")
text = runner.read_text(encoding="utf-8")

helper_anchor = '''def _compact(value: object) -> str:\n    return " ".join(str(value or "").split()).strip()\n\n\n'''
helper_code = '''def _compact(value: object) -> str:\n    return " ".join(str(value or "").split()).strip()\n\n\ndef _exact_lot_identity_key(value: object) -> str:\n    """Normalize cosmetic URL variants without collapsing distinct listing queries."""\n    raw = _compact(value)\n    if not raw:\n        return ""\n    try:\n        parsed = urlsplit(raw)\n        host = (parsed.hostname or "").casefold().removeprefix("www.")\n        if not host:\n            return raw\n        port = parsed.port\n    except ValueError:\n        return raw\n\n    scheme = (parsed.scheme or "https").casefold()\n    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)\n    netloc = host if port is None or default_port else f"{host}:{port}"\n    path = (parsed.path or "/").rstrip("/") or "/"\n    query = f"?{parsed.query}" if parsed.query else ""\n    return f"{scheme}://{netloc}{path}{query}"\n\n\n'''
if "def _exact_lot_identity_key(" not in text:
    if helper_anchor not in text:
        raise SystemExit("expected compact helper anchor")
    text = text.replace(helper_anchor, helper_code, 1)

old_direct = '''        url = _compact(row.get("final_url") or row.get("url"))\n        if not url or url in seen:\n            continue\n        seen.add(url)\n        row["url"] = url\n'''
new_direct = '''        url = _compact(row.get("final_url") or row.get("url"))\n        identity_key = _exact_lot_identity_key(url)\n        if not url or identity_key in seen:\n            continue\n        seen.add(identity_key)\n        row["url"] = url\n'''
count = text.count(old_direct)
if count != 2 and "identity_key = _exact_lot_identity_key(url)" not in text:
    raise SystemExit(f"expected two Exact-Lot seen blocks, found {count}")
if "identity_key = _exact_lot_identity_key(url)" not in text:
    text = text.replace(old_direct, new_direct, 2)
runner.write_text(text, encoding="utf-8")


test = Path("tests/test_exact_lot_www_dedupe_v1.py")
test.write_text('''from __future__ import annotations\n\nimport importlib.util\nfrom pathlib import Path\n\nfrom opportunity_engine.discovery.exa_shadow_page_verification import EXACT_LOT_CANDIDATE\nfrom opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY\n\n\ndef _load_runner():\n    path = Path("scripts/run_exa_exact_lot_checkpoint.py")\n    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_dedupe_test", path)\n    assert spec is not None and spec.loader is not None\n    module = importlib.util.module_from_spec(spec)\n    spec.loader.exec_module(module)\n    return module\n\n\ndef _row(url: str) -> dict[str, object]:\n    return {\n        "classification": EXACT_LOT_CANDIDATE,\n        "title": "Kläder restparti",\n        "url": url,\n        "final_url": url,\n        "evidence": {\n            "project_domain": CLOTHING_INVENTORY,\n            "item_specific_url_evidence": True,\n            "inventory_evidence": True,\n            "direct_sale_evidence": True,\n            "price_evidence": True,\n            "quantity_evidence": True,\n        },\n    }\n\n\ndef test_exact_lot_rows_dedupes_www_and_trailing_slash_variants() -> None:\n    runner = _load_runner()\n    verification = {\n        "verified_pages": [\n            _row("https://grossist.se/restpartier/1/20/parti/2359"),\n            _row("https://www.grossist.se/restpartier/1/20/parti/2359/"),\n        ]\n    }\n    rows = runner._exact_lot_rows(verification, {"exact_lots": []})\n    assert len(rows) == 1\n    assert rows[0]["url"] == "https://grossist.se/restpartier/1/20/parti/2359"\n\n\ndef test_identity_key_preserves_distinct_query_parameters() -> None:\n    runner = _load_runner()\n    first = runner._exact_lot_identity_key("https://www.example.com/item/42/?lot=1")\n    second = runner._exact_lot_identity_key("https://example.com/item/42?lot=2")\n    assert first == "https://example.com/item/42?lot=1"\n    assert second == "https://example.com/item/42?lot=2"\n    assert first != second\n\n\ndef test_identity_key_normalizes_default_https_port_only() -> None:\n    runner = _load_runner()\n    assert (\n        runner._exact_lot_identity_key("https://www.example.com:443/item/42/")\n        == "https://example.com/item/42"\n    )\n    assert (\n        runner._exact_lot_identity_key("https://www.example.com:8443/item/42/")\n        == "https://example.com:8443/item/42"\n    )\n''', encoding="utf-8")
