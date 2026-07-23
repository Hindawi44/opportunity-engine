from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_research_bootstrap.py"
spec = importlib.util.spec_from_file_location("run_research_bootstrap", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_extracts_suffix_kr_price_from_title() -> None:
    item = {"title": "Industrimaskin til salgs 12 500 kr", "url": "https://example.no/item"}
    assert module._explicit_price(item) == 12500.0
    assert item["price_currency"] == "NOK"


def test_extracts_prefix_nok_price_from_snippet() -> None:
    item = {
        "title": "Brukt utstyr",
        "snippet": "Pris NOK 4.990. Kan hentes i Oslo.",
        "url": "https://example.no/item",
    }
    assert module._explicit_price(item) == 4990.0


def test_extracts_price_from_extra_snippets() -> None:
    item = {
        "title": "Vareparti",
        "extra_snippets": ["Lagerparti", "Selges for kr 18 000"],
        "url": "https://example.no/item",
    }
    assert module._explicit_price(item) == 18000.0


def test_rejects_numbers_without_currency_marker() -> None:
    item = {
        "title": "1530 stk fra 2024 modell 7788",
        "snippet": "Ring 99999999 for informasjon",
        "url": "https://example.no/item",
    }
    assert module._explicit_price(item) is None


def test_existing_numeric_price_remains_authoritative() -> None:
    item = {
        "title": "Oppført til 99 000 kr",
        "price_nok": 7500,
        "url": "https://example.no/item",
    }
    assert module._explicit_price(item) == 7500.0


def test_comparable_adapter_accepts_explicit_text_price() -> None:
    rows = [{
        "title": "Brukt maskin 8 500 kr",
        "url": "https://example.no/maskin",
        "snippet": "God stand",
        "source": "Brave Search",
    }]
    candidates = tuple(module.comparable_adapter(rows))
    assert len(candidates) == 1
    assert candidates[0].price_nok == 8500.0
