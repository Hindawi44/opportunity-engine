# Implementation note

This change intentionally reuses existing exact item-page parsers instead of adding a generic arbitrary-web scraper.

Current routing coverage is VENTA + Auksjonen exact item URLs. Unsupported search-result URLs remain visible in the report as `UNSUPPORTED_SOURCE_OR_NON_EXACT_ITEM_URL` so later source adapters can be added without weakening verification quality.
