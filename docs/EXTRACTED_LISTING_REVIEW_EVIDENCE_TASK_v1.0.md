# Extracted Listing Review Evidence Task v1.0

## Status

**Planning-only task definition — implementation not yet approved**

## 1. Purpose

Define the minimum safe change required to make every listing extracted by the live Auksjonen Clothing Inventory scan reviewable by a human operator.

The verified live run after PR #299 produced:

```text
source_extraction_status: VERIFIED_LISTINGS
live_listings_extracted: 26
clothing_listings_extracted: 0
scan_outcome: NO_ACTIVE_CANDIDATE
```

The extraction result is now trustworthy, but the current artifact does not preserve the titles and URLs of all 26 extracted listings. Therefore the operator cannot verify whether:

1. the source truly contained no Clothing Inventory listing; or
2. the clothing classifier missed a relevant title.

This task adds review evidence only. It does not approve classifier expansion, financial analysis, automatic decisions, or workflow changes.

## 2. Approved implementation outcome

Exactly one later implementation task may add a machine-readable artifact:

```text
extracted-listings.json
```

The file must preserve one record for every listing parsed during the live scan, including records that do not match the Clothing Inventory classifier.

Each review record must contain only observed or deterministic fields:

```text
listing_id
title
url
asking_price_nok
location
listing_status
clothing_match
matched_clothing_terms
```

`matched_clothing_terms` must be derived from the existing approved Clothing Inventory term set. No semantic inference, external model call, invented category, or unsupported product classification is approved.

## 3. Truthfulness contract

The review artifact must allow an operator to distinguish:

```text
No relevant listing was present
```

from:

```text
A relevant listing may have been extracted but was not matched by the current term set
```

Creating this artifact must not change any of these outcomes:

```text
ACTIVE_CANDIDATE_SELECTED
NO_ACTIVE_CANDIDATE
SOURCE_EXTRACTION_UNVERIFIED
```

It must not change:

```text
source_extraction_status
final_outcome
final_decision
analysis_invoked
decision_invoked
requires_human_approval
```

## 4. Allowed implementation boundary

The subsequent implementation may modify only:

```text
scripts/run_active_clothing_inventory_scan.py
tests/test_active_clothing_inventory_scan.py
```

No workflow modification is required because the existing operator workflow already uploads the entire directory:

```text
artifacts/active-clothing-inventory-scan/
```

The implementation must reuse the listings already parsed by the live scan. It must not perform a second source request.

## 5. Required output behavior

For every successful source inspection with `VERIFIED_LISTINGS`, the output directory must contain:

```text
operator-summary.txt
scan-report.json
extracted-listings.json
```

For `VERIFIED_EMPTY`, the review file may contain an empty `listings` array with the verified source status.

For `UNVERIFIED_ZERO`, the review file may contain an empty `listings` array but must preserve:

```text
source_extraction_status: UNVERIFIED_ZERO
```

The review file must contain:

```text
schema_version
source_page
scan_observed_at
source_extraction_status
listing_count
listings
```

The `listing_count` must equal the number of records in `listings`.

## 6. Classifier transparency

The implementation may expose the current literal term matches, but it must not broaden the classifier.

For every listing:

```text
clothing_match == true
```

only when at least one existing Clothing Inventory term matches the normalized observed title.

`matched_clothing_terms` must be:

- deterministic;
- deduplicated;
- sorted;
- based only on the current approved term tuple;
- empty when no term matches.

A later classifier-change task may be proposed only after a human reviews the extracted titles and identifies concrete false negatives.

## 7. Required tests

Focused tests must prove:

1. every parsed listing appears once in `extracted-listings.json`;
2. observed title, URL, price, location, and status are preserved;
3. `clothing_match` and `matched_clothing_terms` are deterministic;
4. unmatched listings remain visible with an empty match list;
5. duplicate source listings do not reappear in review evidence;
6. `VERIFIED_EMPTY` and `UNVERIFIED_ZERO` produce truthful empty review artifacts;
7. active-candidate selection behavior remains unchanged;
8. no-candidate behavior remains unchanged;
9. no analysis or decision is invoked merely to create review evidence;
10. all automatic commercial actions remain false.

The focused test command is:

```bash
pytest tests/test_active_clothing_inventory_scan.py -q
```

The canonical repository regression suite must also pass.

## 8. Safety invariants

The implementation must preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_payment: false
```

It must also preserve:

- `BUY_REVIEW` as human-review-only;
- ACTIVE-only promotion into live review;
- ENDED listing traceability without promotion;
- source traceability;
- missing values as missing rather than invented;
- existing financial formulas and thresholds;
- the current Auksjonen source and domain boundary;
- the current operator workflow and artifact upload contract.

## 9. Out of scope

This task does not approve:

- modifying a GitHub Actions workflow;
- adding a new source or domain;
- expanding Clothing Inventory keywords;
- semantic or AI classification;
- fetching listing-detail pages;
- browser automation or authentication;
- changing extraction compatibility logic;
- changing scoring, financial, or decision policies;
- notifications or scheduled behavior;
- automatic purchase, bid, contact, or payment.

## 10. Subsequent implementation task

Exactly one implementation task may follow:

```text
EXTRACTED_LISTING_REVIEW_EVIDENCE_IMPLEMENTATION
```

## 11. Definition of done

This planning task is complete only when:

1. this document is the only changed file;
2. the verified 26-listing observation is recorded;
3. `extracted-listings.json` is defined precisely;
4. the allowed implementation boundary is limited to two files;
5. no workflow change is approved;
6. classifier transparency is added without classifier expansion;
7. required tests and safety invariants are explicit;
8. exactly one subsequent implementation task is identified;
9. all repository checks pass.
