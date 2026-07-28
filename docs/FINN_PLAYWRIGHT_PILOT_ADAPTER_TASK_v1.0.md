# FINN Playwright Pilot Adapter v1.0

**Domain:** `CLOTHING_INVENTORY` only
**Mode:** manual, bounded, replaceable collection adapter
**Automatic schedule:** prohibited
**Commercial actions:** prohibited

## Purpose

Add a temporary browser-based collection adapter for the first Clothing
Inventory end-to-end pilot while preserving the existing boundary:

```text
authorized source collection
  -> Discovery Engine
  -> Opportunity Dossier
  -> Existing Analysis Engine
  -> Final Investment Report or Evidence-Required Outcome
```

The adapter does not change the Opportunity Dossier, market-comparable logic,
acquisition-cost logic, financial formulas, scoring, or decision intelligence.

## Authorization gate

FINN's public robots notice says automated collection requires explicit written
permission. The pilot therefore fails closed unless the operator supplies:

```text
FINN_WRITTEN_AUTOMATION_PERMISSION_REF
```

The value is a private reference to the written authorization. It is not written
to artifacts. Artifacts record only:

```text
permission_reference_present: true
```

The adapter must not be run before written permission exists.

## Collection contract

- 20–50 listings per run.
- One to three search pages.
- At least two seconds between public-page visits.
- Public HTTPS FINN Torget search and item pages only.
- No login, cookie import, proxy rotation, CAPTCHA bypass, or access-control
  bypass.
- Collect title, URL, rendered description, verified price when available,
  verified location when available, public image URLs, listing status, stable
  listing ID, capture timestamp, and source search URL.
- Preserve unavailable values as `null`.
- Verify rendered HTML using the existing Clothing Inventory bounded verifier.
- Save the existing four Discovery artifacts plus
  `finn-playwright-collection.json`.

## Installation

```bash
python -m pip install -r requirements-playwright.txt
python -m playwright install chromium
```

## Manual execution

Only after written permission:

```bash
export FINN_WRITTEN_AUTOMATION_PERMISSION_REF="<private authorization reference>"
python scripts/run_finn_playwright_clothing_pilot.py \
  --max-listings 20 \
  --delay-seconds 3
```

The reference itself must not be committed or copied into generated artifacts.

## Replaceability

Playwright owns browser collection only. It produces ordinary normalized
`SearchHit` records and cached `PageVerification` evidence for the current
Discovery Engine. A future authorized FINN API adapter can replace the browser
collector without changing the Opportunity Dossier or Analysis Engine.

## Success criteria

1. Missing written-permission reference blocks execution.
2. Values outside the 20–50 listing range are rejected.
3. Delay below two seconds is rejected.
4. Non-FINN and non-search URLs are rejected.
5. Stable FINN item IDs are deduplicated.
6. Images remain attached to the Discovery candidate as source evidence.
7. Missing or failed detail pages remain unresolved and never become confirmed
   sales.
8. The existing Discovery verification and early-opportunity gates still run.
9. No seller contact, bid, reservation, purchase, payment, schedule, or
   automatic investment decision is added.
