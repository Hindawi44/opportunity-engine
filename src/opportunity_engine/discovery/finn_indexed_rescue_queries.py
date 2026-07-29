"""Broad FINN-indexed query set for the bounded rescue experiment.

The queries intentionally keep Brave retrieval broad and let the existing URL,
clothing, quantity, buyer-intent, and reference gates decide what survives.
"""
from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery


FINN_INDEXED_BROAD_RESCUE_QUERIES: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery(
        "finn-broad-01",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "site:finn.no Rains jakker selges samlet",
    ),
    DiscoveryQuery(
        "finn-broad-02",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "site:finn.no 150 par damesko selges",
    ),
    DiscoveryQuery(
        "finn-broad-03",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "site:finn.no klær sko vesker stativ selges",
    ),
    DiscoveryQuery(
        "finn-broad-04",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "site:finn.no vareparti klær",
    ),
    DiscoveryQuery(
        "finn-broad-05",
        "WAREHOUSE_SURPLUS",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "site:finn.no restlager klær",
    ),
    DiscoveryQuery(
        "finn-broad-06",
        "WAREHOUSE_SURPLUS",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        "site:finn.no arbeidstøy parti",
        "SECONDARY",
    ),
    DiscoveryQuery(
        "finn-broad-07",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        "site:finn.no damebukser parti",
        "SECONDARY",
    ),
    DiscoveryQuery(
        "finn-broad-08",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        "site:finn.no klær sko selges samlet",
        "SECONDARY",
    ),
)
