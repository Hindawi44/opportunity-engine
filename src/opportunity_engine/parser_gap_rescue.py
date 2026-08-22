"""Conservative PARSER_GAP rescue overlay for Auksjonen clothing inventory.

The public module keeps V1's learning API stable while separating the small
post-normalization runtime application from durable verified-gap learning.
Neither layer broadens the clothing classifier or adds network requests.
"""
from opportunity_engine.parser_gap_rescue_learning import (
    MEMORY_RELATIVE_PATH,
    OUTPUT_FILENAME,
    OVERLAY_FILENAME,
    REPORT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SUPPORTED_SOURCE,
    build_parser_rescue_overlay,
    load_parser_rescue_overlay,
    load_parser_rescue_terms,
    save_parser_rescue_overlay,
    write_parser_gap_rescue_overlay,
)
from opportunity_engine.parser_gap_rescue_runtime import apply_auksjonen_parser_rescue

__all__ = [
    "MEMORY_RELATIVE_PATH",
    "OUTPUT_FILENAME",
    "OVERLAY_FILENAME",
    "REPORT_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "SUPPORTED_SOURCE",
    "apply_auksjonen_parser_rescue",
    "build_parser_rescue_overlay",
    "load_parser_rescue_overlay",
    "load_parser_rescue_terms",
    "save_parser_rescue_overlay",
    "write_parser_gap_rescue_overlay",
]
