from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from opportunity_engine.auksjonen_import import load_auksjonen_csv
from opportunity_engine import evaluate_opportunity


def test_imports_norwegian_semicolon_csv(tmp_path: Path) -> None:
    source = tmp_path / "auksjonen.csv"
    source.write_text(
        "Tittel;Tilslag;Salær;MVA prosent;MVA tilkommer;Frakt;Markedsverdi;Risiko\n"
        "Butikkinnredning;10 000 kr;1 500 kr;25%;ja;2 000 kr;26 000 kr;2\n",
        encoding="utf-8",
    )

    items = load_auksjonen_csv(source)
    result = evaluate_opportunity(items[0])

    assert len(items) == 1
    assert items[0].title == "Butikkinnredning"
    assert items[0].purchase_price == 10000
    assert items[0].buyer_fee == 1500
    assert items[0].vat_rate == 0.25
    assert items[0].vat_applies_to_bid is True
    assert result.vat_cost == 2500


def test_missing_required_column(tmp_path: Path) -> None:
    source = tmp_path / "bad.csv"
    source.write_text("Tittel;Tilslag\nTest;1000\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected_resale_value"):
        load_auksjonen_csv(source)


def test_decimal_comma_and_english_headers(tmp_path: Path) -> None:
    source = tmp_path / "english.csv"
    source.write_text(
        "title,purchase_price,expected_resale_value,risk_score\n"
        'Item,"1.250,50","3.000,00",3\n',
        encoding="utf-8",
    )

    items = load_auksjonen_csv(source)

    assert items[0].purchase_price == pytest.approx(1250.50)
    assert items[0].expected_resale_value == pytest.approx(3000.00)
