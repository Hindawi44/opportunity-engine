# Pre-Market Sale Channel Search v1.0

## Goal

Close the most important gap in the pre-market path: determine whether a selected
clothing bankruptcy has produced a public sale listing or a traceable liquidation
channel before the opportunity is visible through the ordinary unified Top 5.

## Position in the path

```text
PRE_MARKET_LEAD
  -> ESTATE_MANAGER_IDENTIFIED
  -> TARGETED_SALE_CHANNEL_SEARCH
  -> SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION
     or LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION
  -> VERIFIED_ACTIVE_INVENTORY_SALE only after page evidence
```

## Search contract

For one manually selected estate, the runner first reads the approved single
Konkurs.app estate endpoint and then issues five bounded Brave searches using:

- the exact debtor name;
- the exact estate name;
- the debtor organisation number;
- the estate organisation number;
- sale, auction, inventory, estate-manager, and liquidation wording;
- direct targeting of Auksjonen, Vareauksjonen, Auksjoner.no, and FINN results.

The request budget is fixed at five searches per selected estate.

## Critical evidence rule

A Brave title or snippet can only create a candidate. It cannot confirm:

- that the page is still active;
- that the goods are clothing inventory;
- that the goods belong to the selected bankruptcy estate;
- that a liquidation company has a verified mandate;
- that the inventory remains available for sale.

Every candidate therefore remains:

```text
page_verified = false
public_sale_found = false
inventory_sale_verified = false
liquidation_channel_verified = false
top5_eligible = false
analysis_eligible = false
```

## Identity gate

A result is retained only when the title, snippet, or URL contains either:

1. the exact debtor or estate organisation number; or
2. the exact normalized debtor or estate name.

Fuzzy company-name matching is not accepted.

## Candidate classes

### Sale-listing candidate

Created when exact identity evidence appears together with sale wording, a known
sale-channel domain, or a FINN result.

```text
SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION
```

### Liquidation-channel candidate

Created when exact identity evidence appears with wording such as `bostyrer`,
`boet`, `avvikling`, `på vegne av`, or `realiseres`, without sufficient evidence
for a sale-listing candidate.

```text
LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION
```

### Identity reference only

A company-information or registry result with no sale or liquidation signal is
retained only for diagnostics.

## FINN boundary

FINN results may be discovered through the search provider, but the module does
not open or scrape FINN pages. Such results are marked:

```text
collection_mode = MANUAL_REVIEW_ONLY
automatic_page_open = false
```

## Manual execution

```bash
BRAVE_SEARCH_API_KEY=... \
python scripts/run_pre_market_sale_channel_search.py \
  --estate-orgnr 938018014 \
  --freshness py \
  --results-per-query 10
```

## Outputs

- `sale-channel-search.json`
- `sale-listing-candidates.json`
- `liquidation-channel-candidates.json`
- `live-clothing-top5.json` — always empty at this stage
- `operator-summary.txt`

## Safety boundaries

- one explicitly selected estate per execution;
- maximum five Brave requests;
- no automatic page opening;
- no FINN scraping;
- no automatic contact or email;
- no bid, purchase, reservation, commitment, or payment;
- no promotion to commercial Top 5 from search snippets.
