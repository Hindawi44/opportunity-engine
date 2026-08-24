from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)


def test_mutsaers_primary_fabric_wholesale_beats_incidental_clothing_words() -> None:
    text = (
        "Mutsaers Textiles | B2B Textielgroothandel in Stoffen Europa. "
        "Stoffen voor kleding, jurken en modecollecties."
    )
    assert classify_project_domain(text=text) == FABRIC_PROCUREMENT


def test_wouters_stoffen_groothandel_is_fabric_procurement() -> None:
    text = (
        "Stoffen groothandel Nederland | Wouters Textiles. "
        "Groothandel voor stoffen die worden gebruikt voor kleding en mode."
    )
    assert classify_project_domain(text=text) == FABRIC_PROCUREMENT


def test_rijs_stoffen_en_fournituren_is_fabric_procurement() -> None:
    text = (
        "Stoffen en fournituren tegen groothandelsprijzen voor iedereen! "
        "Materialen voor kleding, jurken en andere toepassingen."
    )
    assert classify_project_domain(text=text) == FABRIC_PROCUREMENT


def test_clothing_inventory_with_incidental_stoffen_stays_clothing() -> None:
    text = (
        "Kledingvoorraad: 500 jurken en jassen uit een modewinkel. "
        "De kleding is gemaakt van verschillende stoffen."
    )
    assert classify_project_domain(text=text) == CLOTHING_INVENTORY
