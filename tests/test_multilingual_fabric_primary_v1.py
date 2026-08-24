from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)


def test_multilingual_fabric_primary_commercial_phrases_win():
    cases = (
        "Activatextil - Din grossist for stoffer",
        "G&M Textiles - Tyg Grossist | Köp tyg på metervara till företag",
        "Stoffgroßhandel Resotex GmbH - Meterware Großhandel",
        "CYBITEX | Grossiste tissus, Tissu en Gros, Rouleau de Tissu",
        "Ingrosso Tessuti Prato - tessuti a stock abbigliamento",
    )
    for text in cases:
        assert classify_project_domain(text=text) == FABRIC_PROCUREMENT


def test_multilingual_fabric_primary_does_not_expand_generic_clothing():
    assert (
        classify_project_domain(
            text="Ingrosso abbigliamento stock: giacche pantaloni camicie e vestiti"
        )
        == CLOTHING_INVENTORY
    )
    assert (
        classify_project_domain(
            text="Modeware Restposten: Jacken Hosen Hemden Lagerverkauf"
        )
        == CLOTHING_INVENTORY
    )
