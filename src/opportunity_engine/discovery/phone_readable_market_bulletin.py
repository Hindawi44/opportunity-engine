"""Six-market compatibility facade for the phone-readable daily bulletin.

This module extends presentation coverage only. Discovery, verification, scoring,
action selection, and all commercial safety gates remain owned by the base module.
"""
from __future__ import annotations

from . import _phone_readable_market_bulletin_base as _base
from ._phone_readable_market_bulletin_base import *  # noqa: F401,F403


_base.COUNTRY_LABELS.update(
    {
        "FR": "فرنسا",
        "IT": "إيطاليا",
        "NL": "هولندا",
    }
)
COUNTRY_LABELS = _base.COUNTRY_LABELS

_OLD_MARKETS_LINE = "الأسواق: النرويج | السويد | ألمانيا"
_OPERATED_MARKETS_LINE = (
    "الأسواق: النرويج | السويد | ألمانيا | فرنسا | إيطاليا | هولندا"
)


def render_phone_readable_market_bulletin(brief):
    """Render the existing bulletin while naming all six operated markets."""
    rendered = _base.render_phone_readable_market_bulletin(brief)
    return rendered.replace(_OLD_MARKETS_LINE, _OPERATED_MARKETS_LINE, 1)
