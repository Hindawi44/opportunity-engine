"""Runtime application of learned Auksjonen parser rescue terms."""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
)


def _tokens(value: object) -> set[str]:
    import re

    return {
        match.group(0).casefold()
        for match in re.finditer(r"[^\W\d_]+(?:-[^\W\d_]+)*", " ".join(str(value or "").split()))
    }


def apply_auksjonen_parser_rescue(
    collection: AuksjonenLiveClothingCollection,
    learned_terms: Sequence[str],
) -> AuksjonenLiveClothingCollection:
    """Promote only already-normalized clothing listings on exact learned tokens."""
    terms = tuple(
        dict.fromkeys(
            term
            for raw in learned_terms
            if (term := " ".join(str(raw or "").casefold().split()).strip())
        )
    )
    if not terms:
        return collection

    changed = False
    rescued = []
    for listing in collection.listings:
        if listing.inventory_lot_signal:
            rescued.append(listing)
            continue
        title_tokens = _tokens(listing.title)
        if any(term in title_tokens for term in terms):
            rescued.append(replace(listing, inventory_lot_signal=True))
            changed = True
        else:
            rescued.append(listing)

    if not changed:
        return collection

    rescued.sort(
        key=lambda listing: (
            not listing.inventory_lot_signal,
            listing.ends_at or "",
            listing.object_id,
        )
    )
    return replace(collection, listings=tuple(rescued))
