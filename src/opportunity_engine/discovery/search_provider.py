"""Provider-neutral contracts for Discovery Engine V1.1 live search."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One normalized public web-search result."""

    title: str
    url: str
    description: str = ""
    provider: str = ""


class SearchProvider(Protocol):
    """Minimal interface implemented by public web-search providers."""

    name: str

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        """Return normalized public search hits for one non-empty query."""
        ...
