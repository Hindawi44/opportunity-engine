from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    OUT_OF_DOMAIN,
    classify_project_domain,
)


def test_compound_french_garment_family_subject_is_clothing() -> None:
    assert (
        classify_project_domain(
            text="Hauts femme au kilo à revendre /products/hauts-femme-au-kilo"
        )
        == CLOTHING_INVENTORY
    )


def test_generic_french_haut_language_does_not_expand_domain() -> None:
    assert classify_project_domain(text="Hauts revenus et prix en hausse") == OUT_OF_DOMAIN
    assert classify_project_domain(text="Le haut de gamme immobilier à vendre") == OUT_OF_DOMAIN
