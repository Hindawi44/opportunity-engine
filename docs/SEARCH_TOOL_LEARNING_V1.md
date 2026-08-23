# SEARCH TOOL LEARNING V1

## Purpose

Measure whether Exa or Brave is actually helping the Opportunity Engine find better clothing-inventory evidence.

The layer does **not** reward raw search-hit volume. Search results are observations only. Provider quality is learned from original pages that are fetched and classified under `PROJECT_DOMAIN_BOUNDARY_V1`.

## Scope

This V1 lane is explicitly:

```text
CLOTHING_INVENTORY
```

Fabric procurement remains a separate bounded lane and is not mixed into this provider comparison.

The six-market coverage inherited from the existing Exa-vs-Brave Shadow Lab is diagnostic only. It does **not** promote FR, IT, or NL into canonical clothing-inventory production markets; the current daily market model remains unchanged, including Italy's bounded `FABRIC_PROCUREMENT` role.

The Exa-vs-Brave benchmark queries are clothing/fashion anchored in every supported shadow market. Generic liquidation or business-closure results cannot improve a provider's Tool Learning result merely because they are numerous.

## Evidence flow

```text
same clothing-domain query
→ Exa results + Brave results
→ remove URLs both providers found
→ exact-page verification of Exa-unique URLs
→ exact-page verification of Brave-unique URLs
→ PROJECT_DOMAIN_BOUNDARY_V1 classification
→ commercial-specificity gate
→ provider metrics
→ read-only Tool Learning decision
```

Both providers use the same page classifier and the same commercial-useful definition.

## Strict useful-evidence rule

A broad `ACTIVE_STOCK_SIGNAL` is **not** enough to teach positive provider quality.

Positive Tool Learning credit is currently limited to:

```text
EXACT_LOT_CANDIDATE
ACTIVE_STOCK_SIGNAL + item_specific_url_evidence = true
```

This prevents news articles, guides, aggregate auction/index pages, and other broad pages from winning provider credit merely because their text contains clothing, stock, price, or sale vocabulary.

`OUT_OF_DOMAIN` is measured from the project-domain evidence itself, even when the broader page classification is `UNPROVEN_PAGE` or another non-sale state. Therefore out-of-domain pages remain measurable provider noise and can never teach positive quality.

The verifier also reports:

```text
non_specific_active_filtered_count
```

so broad active-looking pages remain visible diagnostically without being counted as useful commercial evidence.

## Decision rule

The scorecard compares:

```text
item_specific_verified_clothing_yield - out_of_domain_rate
```

A minimum symmetrically verified sample is required for **both** providers before a lead can be declared.

In addition, at least one provider must prove at least one strictly useful commercial page. If the combined useful count is zero, the decision must be:

```text
INSUFFICIENT_EVIDENCE
```

with:

```text
NO_VERIFIED_USEFUL_COMMERCIAL_PAGES
```

A provider cannot win merely because it has fewer bad pages when neither provider has proved a useful commercial page.

Possible decisions remain:

```text
EXA_LEADS
BRAVE_LEADS
NO_CLEAR_LEADER
INSUFFICIENT_EVIDENCE
```

Raw result count is diagnostic only and cannot choose a provider.

## Live RED evidence — 2026-08-23

Temporary run:

```text
32650319776
```

was the first post-domain-boundary symmetric Exa-vs-Brave live proof. The initial scorecard returned `BRAVE_LEADS`, but exact-page review showed that broad `ACTIVE_STOCK_SIGNAL` pages were being over-credited. The credited Brave set included non-commercial article/aggregate pages such as Steigan, Shoplabs, WDR, and a Troostwijk auctions index.

That provider conclusion is invalid and must not be used as promotion evidence. The run is retained only as RED evidence that established the commercial-specificity requirement above.

Temporary PR `#696` was closed without merge.

## Safety / architecture

- Shadow/read-only only.
- No automatic provider activation or disabling.
- No production mutation.
- No new permanent workflow is required by V1.
- No provider is promoted from one run.
- Out-of-domain results may be measured as noise but cannot teach positive provider quality.
- Temporary live-proof workflows are closed without merge after evidence capture.

## Runner

First produce the bounded benchmark:

```bash
python scripts/run_exa_brave_shadow_benchmark.py --output benchmark.json --provider-mode both
```

Then run symmetric exact-page verification and Tool Learning:

```bash
python scripts/run_exa_brave_tool_learning.py --benchmark benchmark.json --output tool-learning.json
```

The resulting artifact retains both provider verification reports and the advisory Tool Learning decision.
