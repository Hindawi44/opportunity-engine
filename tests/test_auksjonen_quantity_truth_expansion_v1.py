from __future__ import annotations

import json

from opportunity_engine.discovery.auksjonen_exact_item_verification import (
    parse_auksjonen_item_page,
)


def _html(title: str, description: str, *, condition: str | None = None) -> str:
    payload: dict[str, object] = {
        "name": title,
        "description": description,
    }
    if condition is not None:
        payload["itemCondition"] = condition
    return f"""
    <html><body>
      <h1>{title}</h1>
      <script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>
    </body></html>
    """


def test_pair_unit_is_explicit_lot_quantity() -> None:
    result = parse_auksjonen_item_page(
        _html(
            "Sko Parti på 3600 par",
            "Et nytt parti med fritidssko til salg. Det er ca 3600 par sko fordelt på flere modeller.",
            condition="https://schema.org/NewCondition",
        )
    )

    assert result["quantity"] == 3600
    assert result["condition"] == "NEW_OR_UNUSED"
    assert result["quantity_explicitly_unknown"] is False


def test_compound_garment_title_sums_explicit_components() -> None:
    result = parse_auksjonen_item_page(
        _html(
            "Univern arbeidsklær - 5 forede overaller str. 46 og 5 jakker str. 68",
            "Parti med arbeidsklær fra Univern.",
        )
    )

    assert result["quantity"] == 10


def test_model_numbers_are_not_added_to_quantity() -> None:
    result = parse_auksjonen_item_page(
        _html(
            "22 stk Blåkläder arbeidsjakker i størrelse S - modell 3463 og 4830",
            "Parti med 22 stk Blåkläder arbeidsjakker fordelt på to modeller.",
        )
    )

    assert result["quantity"] == 22


def test_unknown_quantity_still_vetoes_pair_and_component_numbers() -> None:
    result = parse_auksjonen_item_page(
        _html(
            "Parti med 5 jakker og 5 bukser",
            "Selges samlet. Eksakt antall er ikke kontrollert. 20 par ligger i navigasjonen.",
        )
    )

    assert result["quantity"] is None
    assert result["quantity_explicitly_unknown"] is True
