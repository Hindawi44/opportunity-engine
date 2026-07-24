"""Commercial scenario maps for Discovery Engine V1."""
from __future__ import annotations

CLOTHING_INVENTORY_MAP: dict[str, tuple[str, ...]] = {
    "STORE_CLOSING": ("opphørssalg", "avvikling", "butikken legges ned", "alt skal bort"),
    "COMPANY_BANKRUPTCY": ("konkursbo klær", "konkurs klesbutikk", "konkurs varelager klær"),
    "INVENTORY_LIQUIDATION": ("tømmesalg klær", "lageravvikling klær", "varelager til salgs"),
    "AUCTION": ("auksjon klær", "auksjon varelager klær", "vareparti klær auksjon"),
    "WAREHOUSE_SURPLUS": ("overskuddslager klær", "restlager klær", "lagerutsalg klær"),
    "IMPORTER_LIQUIDATION": ("importør restlager klær", "grossist varelager klær", "parti klær engros"),
    "MANUFACTURER_EXCESS": ("overskuddsproduksjon klær", "restparti tekstil", "produksjonsparti klær"),
    "LARGE_LOT_SALE": ("vareparti klær", "klesparti til salgs", "parti med klær selges"),
    "BUSINESS_MODEL_CHANGE": ("klesbutikk endrer drift", "butikk går over til nett", "avvikler klesavdeling"),
    "BRANCH_CLOSURE": ("klesbutikk filial legges ned", "butikkavdeling stenger", "filial opphørssalg"),
}

SCENARIO_RECORD_TYPES: dict[str, str] = {
    "STORE_CLOSING": "STORE_CLOSURE_LEAD",
    "COMPANY_BANKRUPTCY": "BANKRUPTCY_LEAD",
    "INVENTORY_LIQUIDATION": "SALE_LISTING",
    "AUCTION": "SALE_LISTING",
    "WAREHOUSE_SURPLUS": "SALE_LISTING",
    "IMPORTER_LIQUIDATION": "SALE_LISTING",
    "MANUFACTURER_EXCESS": "SALE_LISTING",
    "LARGE_LOT_SALE": "SALE_LISTING",
    "BUSINESS_MODEL_CHANGE": "LIQUIDATION_LEAD",
    "BRANCH_CLOSURE": "STORE_CLOSURE_LEAD",
}
