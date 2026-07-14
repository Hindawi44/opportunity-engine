import csv
import re
from pathlib import Path

from .models import Opportunity


ALIASES = {
    "title": {"title", "tittel", "objekt", "vare", "navn"},
    "auction_url": {"auction_url", "url", "lenke", "link", "annonse"},
    "purchase_price": {"purchase_price", "bud", "pris", "kjopspris", "tilslag"},
    "buyer_fee": {"buyer_fee", "salær", "salaer", "provisjon", "gebyr"},
    "transport_cost": {"transport_cost", "transport", "frakt", "levering"},
    "dismantling_cost": {"dismantling_cost", "demontering", "fjerning"},
    "storage_cost": {"storage_cost", "lagring", "lager"},
    "repair_cost": {"repair_cost", "reparasjon", "utbedring"},
    "other_costs": {"other_costs", "annet", "andre_kostnader"},
    "expected_resale_value": {"expected_resale_value", "videresalg", "markedsverdi", "salgsverdi"},
    "risk_score": {"risk_score", "risiko", "risikoniva", "risikonivå"},
    "vat_rate": {"vat_rate", "mva", "mva_sats", "mva_prosent"},
    "vat_applies_to_bid": {"vat_applies_to_bid", "mva_pa_bud", "mva_på_bud", "mva_tilkommer"},
}


def _normalize_header(value: str) -> str:
    value = value.strip().lower().replace(" ", "_").replace("-", "_")
    return re.sub(r"[^a-z0-9_æøå]", "", value)


def _canonical_headers(fieldnames: list[str]) -> dict[str, str]:
    normalized = {_normalize_header(name): name for name in fieldnames}
    mapping: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[canonical] = normalized[alias]
                break
    return mapping


def _parse_number(value: str | None, default: float = 0.0) -> float:
    if value is None or not value.strip():
        return default
    cleaned = value.strip().lower().replace("nok", "").replace("kr", "").replace("%", "")
    cleaned = cleaned.replace(" ", "").replace("\u00a0", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def _parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "ja", "j", "نعم"}


def load_auksjonen_csv(path: str | Path) -> list[Opportunity]:
    """Import an Auksjonen-style CSV using Norwegian or English column names."""
    source = Path(path)
    opportunities: list[Opportunity] = []

    with source.open("r", encoding="utf-8-sig", newline="") as file:
        sample = file.read(4096)
        file.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        reader = csv.DictReader(file, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("CSV file has no header row")

        mapping = _canonical_headers(reader.fieldnames)
        required = {"title", "purchase_price", "expected_resale_value"}
        missing = required.difference(mapping)
        if missing:
            raise ValueError(f"Missing required auction columns: {', '.join(sorted(missing))}")

        for line_number, row in enumerate(reader, start=2):
            title = (row.get(mapping["title"]) or "").strip()
            if not title:
                raise ValueError(f"Missing title on CSV line {line_number}")

            vat_raw = row.get(mapping.get("vat_rate", "")) if "vat_rate" in mapping else None
            vat_rate = _parse_number(vat_raw, 25.0)
            if vat_rate > 1:
                vat_rate /= 100

            opportunity = Opportunity(
                title=title,
                auction_url=(row.get(mapping.get("auction_url", "")) or "").strip(),
                purchase_price=_parse_number(row.get(mapping["purchase_price"])),
                buyer_fee=_parse_number(row.get(mapping.get("buyer_fee", ""))),
                transport_cost=_parse_number(row.get(mapping.get("transport_cost", ""))),
                dismantling_cost=_parse_number(row.get(mapping.get("dismantling_cost", ""))),
                storage_cost=_parse_number(row.get(mapping.get("storage_cost", ""))),
                repair_cost=_parse_number(row.get(mapping.get("repair_cost", ""))),
                other_costs=_parse_number(row.get(mapping.get("other_costs", ""))),
                expected_resale_value=_parse_number(row.get(mapping["expected_resale_value"])),
                risk_score=int(_parse_number(row.get(mapping.get("risk_score", "")), 3)),
                vat_rate=vat_rate,
                vat_applies_to_bid=_parse_bool(row.get(mapping.get("vat_applies_to_bid", ""))),
            )
            opportunities.append(opportunity)

    return opportunities
