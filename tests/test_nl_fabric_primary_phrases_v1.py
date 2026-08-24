from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)


def test_deadstock_fabrics_outrank_incidental_fashion_words() -> None:
    text = (
        "DEADSTOCK DESIGNER FABRICS. High-quality European designer deadstock "
        "in 3-meter cuts for fashion brands and creative makers."
    )
    assert classify_project_domain(text=text) == FABRIC_PROCUREMENT


def test_deadstock_stoffen_outrank_incidental_kleding_words() -> None:
    text = (
        "Deadstock stoffen van Europese makelij. Op voorraad per meter, geschikt "
        "voor kleding en creatieve projecten."
    )
    assert classify_project_domain(text=text) == FABRIC_PROCUREMENT


def test_restpartijen_stoffen_and_stoffenwinkel_are_fabric_procurement() -> None:
    text = (
        "Welkom bij onze stoffenwinkel. Aanbod restpartijen stoffen met diverse "
        "metrages, actuele voorraad en scherpe groothandelsprijzen. Perfect voor mode."
    )
    assert classify_project_domain(text=text) == FABRIC_PROCUREMENT


def test_partijhandel_stoffen_is_fabric_procurement() -> None:
    assert (
        classify_project_domain(text="Partijhandel stoffen, diverse metrages op voorraad")
        == FABRIC_PROCUREMENT
    )


def test_clothing_inventory_with_incidental_stoffen_remains_clothing() -> None:
    text = (
        "Kledingwinkel met jurken en jassen op voorraad. De kleding is gemaakt van "
        "verschillende stoffen en materialen."
    )
    assert classify_project_domain(text=text) == CLOTHING_INVENTORY
