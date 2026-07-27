# Auksjonen Live Extraction Compatibility Task v1.0

**Task type:** Planning-only compatibility task definition  
**Domain:** `CLOTHING_INVENTORY`  
**Implementation status:** `NOT_STARTED`  
**Automatic commercial action:** Prohibited

## 1. Purpose

Define the minimum safe correction for the live Auksjonen source path after the first approved manual operator run completed successfully but produced:

```text
Scan outcome: NO_ACTIVE_CANDIDATE
Listings extracted: 0
Clothing listings extracted: 0
Ended clothing listings: 0
```

The workflow and artifact contract were proven operational. The source extraction result was not proven trustworthy.

A zero-listing parse must not be treated as evidence that no active opportunity exists unless the source page contains a verified explicit empty-state signal.

This task-definition PR creates this document only. It must not modify workflows, production code, tests, fixtures, reports, artifacts, state, cache, decision policy, scoring thresholds, or financial formulas.

## 2. Verified evidence

The accepted operator workflow was manually dispatched with:

```text
operation: active_clothing_scan
```

The run completed successfully and uploaded the stable artifact:

```text
active-clothing-inventory-scan
```

The artifact contained:

```text
operator-summary.txt
scan-report.json
```

The stored summary established:

```text
live_listings_extracted: 0
analysis_invoked: false
decision_invoked: false
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_payment: false
```

This proves the manual operator integration and safety gates work. It does not prove that the public source contained no listings.

## 3. Compatibility defect

The current source adapter recognizes listings only from:

1. `application/ld+json` blocks containing a title, URL, and positive price; or
2. anchor text containing a valid Auksjonen listing URL and a positive NOK price.

The current live result may therefore be caused by one or more of the following:

- the public page now renders listing data through a different embedded JSON structure;
- listing cards are hydrated client-side;
- listing URLs or category paths changed;
- price text moved outside the anchor element;
- the public response is a shell, consent page, redirect page, or bot-protection response;
- the category page is genuinely empty.

Repository evidence does not yet distinguish these cases.

## 4. Correct outcome semantics

The subsequent implementation must separate three source states.

### State A — verified listings were extracted

```text
source_extraction_status: VERIFIED_LISTINGS
```

Normal Clothing Inventory filtering continues:

```text
ACTIVE listing found
  -> ACTIVE_CANDIDATE_SELECTED
```

or:

```text
listings extracted but no ACTIVE clothing listing
  -> NO_ACTIVE_CANDIDATE
```

### State B — the public page explicitly verifies an empty category

```text
source_extraction_status: VERIFIED_EMPTY
scan_outcome: NO_ACTIVE_CANDIDATE
final_decision: NO_DECISION
```

An explicit empty-state marker must be observed in the public response. An empty parser result alone is insufficient.

### State C — zero listings without a verified empty-state marker

```text
source_extraction_status: UNVERIFIED_ZERO
scan_outcome: SOURCE_EXTRACTION_UNVERIFIED
final_decision: NO_DECISION
```

Required behavior:

- analysis is not invoked;
- decision intelligence is not invoked;
- no Opportunity Dossier is created;
- the run remains operationally successful so the artifact is preserved;
- the operator summary clearly states that source extraction requires review;
- the result must not claim that no active candidate exists.

## 5. Investigation requirements

Before changing parsing rules, the subsequent implementation must inspect the live public response and record only non-sensitive diagnostics required to identify the rendering contract.

Required diagnostics:

```text
requested_url
final_url
http_status
content_type
response_byte_count
html_title when available
count of anchor tags
count of application/ld+json scripts
count of application/json scripts
presence of common hydration containers
presence of an explicit empty-state marker
```

Raw cookies, authorization headers, personal data, and secret values must never be stored.

If a fixture is created from the live public response, it must be reduced to the smallest representative public structure needed for deterministic tests.

## 6. Approved source strategies

The implementation may support only public, unauthenticated source structures delivered to an ordinary browser.

Allowed strategies, in lowest-risk order:

1. corrected server-rendered anchor/card extraction;
2. corrected JSON-LD extraction;
3. parsing a public embedded hydration payload already present in the HTML response;
4. using a stable public same-site data endpoint that the public page itself consumes, only when it requires no login, token, CAPTCHA bypass, or access-control circumvention.

The implementation must not:

- bypass CAPTCHA or bot protection;
- impersonate a logged-in user;
- use private or undocumented credentials;
- scrape personal account data;
- add browser automation unless a separately approved task proves it is necessary and compliant;
- add a new marketplace or source domain.

## 7. Compatibility requirements

The existing public interfaces must remain available:

```text
fetch_public_page(...)
parse_public_listings(...)
build_snapshot(...)
```

Existing fixture-backed extraction behavior must remain covered.

The implementation may add a backward-compatible diagnostic result or helper, but must not require callers to invent missing prices, statuses, locations, identifiers, or costs.

Listing status rules remain:

```text
ACTIVE listings may enter live review
ENDED listings may remain traceable evidence
ENDED listings may not enter live review
```

A listing without a verifiable positive observed price must not be promoted into financial review.

## 8. Subsequent implementation task

Exactly one implementation task may follow this document:

```text
AUKSJONEN_LIVE_EXTRACTION_COMPATIBILITY_IMPLEMENTATION
```

The implementation may modify only these files when evidence requires them:

```text
src/opportunity_engine/source_ingestion/auksjonen.py
scripts/run_active_clothing_inventory_scan.py
scripts/run_v33_auksjonen_ingestion.py
tests/test_v33_live_source_ingestion.py
tests/test_active_clothing_inventory_scan.py
tests/fixtures/v33_auksjonen_current_page.html
```

The new fixture may be created only if a distinct current public structure must be represented. No workflow modification is approved.

If the verified source requires browser automation, authentication, a new external dependency, or another domain, implementation must stop and create a separate task definition.

## 9. Required tests

The subsequent implementation must prove all of the following.

### Parser compatibility

- the legacy fixture still extracts its expected listings;
- the current-format fixture extracts the expected listing fields when listings are present;
- embedded public JSON is parsed only when the listing URL belongs to Auksjonen;
- invalid, external, price-less, or malformed records are rejected;
- duplicate listings remain deduplicated;
- explicit `ACTIVE` and `ENDED` status markers remain preserved.

### Zero-result semantics

- an explicit empty-state fixture produces `VERIFIED_EMPTY` and `NO_ACTIVE_CANDIDATE`;
- an unrecognized shell or non-empty page with zero parsed listings produces `UNVERIFIED_ZERO` and `SOURCE_EXTRACTION_UNVERIFIED`;
- neither zero-result path invokes analysis or decision intelligence;
- neither zero-result path creates an Opportunity Dossier;
- all automatic commercial actions remain false.

### Regression

The focused tests must pass:

```bash
pytest tests/test_v33_live_source_ingestion.py -q
pytest tests/test_active_clothing_inventory_scan.py -q
```

The canonical repository regression suite must also pass.

## 10. Manual verification after implementation

After merge, run the approved operator workflow manually with:

```text
operation: active_clothing_scan
```

The artifact must show one of these truthful outcomes:

```text
ACTIVE_CANDIDATE_SELECTED
NO_ACTIVE_CANDIDATE with source_extraction_status VERIFIED_LISTINGS
NO_ACTIVE_CANDIDATE with source_extraction_status VERIFIED_EMPTY
SOURCE_EXTRACTION_UNVERIFIED with source_extraction_status UNVERIFIED_ZERO
```

A successful workflow run with `Listings extracted: 0` is not accepted as product validation unless the artifact also proves `VERIFIED_EMPTY`.

## 11. Safety invariants

The implementation must preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_payment: false
```

It must also preserve:

- `BUY_REVIEW` as human-review-only;
- no automatic purchase, bid, contact, payment, or financial action;
- no invented values;
- source traceability;
- no financial-formula changes;
- no scoring-threshold changes;
- no decision-policy changes;
- no schedule changes;
- no new domain;
- no new source.

## 12. Out of scope

This task does not approve:

- modifying any GitHub Actions workflow;
- adding scheduled execution;
- adding notifications;
- changing the two-workflow operator surface;
- changing market-comparable or acquisition-cost logic;
- changing V2.8–V3.7 formulas;
- automatic commercial execution;
- browser automation;
- authentication or access-control bypass;
- expansion beyond `CLOTHING_INVENTORY` and Auksjonen.

## 13. Definition of done

This planning task is complete only when:

1. this document is the only changed file;
2. the observed zero-extraction evidence is recorded without claiming the category was empty;
3. `VERIFIED_LISTINGS`, `VERIFIED_EMPTY`, and `UNVERIFIED_ZERO` are defined;
4. `SOURCE_EXTRACTION_UNVERIFIED` is required for an unverified zero parse;
5. the allowed public-source strategies and prohibited bypass methods are explicit;
6. the implementation file boundary is exact;
7. focused and canonical regression tests are required;
8. all safety invariants remain explicit;
9. exactly one subsequent implementation task is identified;
10. all repository checks pass.
