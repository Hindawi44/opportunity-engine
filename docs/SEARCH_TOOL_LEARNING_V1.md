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
→ provider metrics
→ read-only Tool Learning decision
```

Both providers use the same page classifier and the same commercial-useful definition.

Useful clothing evidence is currently:

```text
EXACT_LOT_CANDIDATE
ACTIVE_STOCK_SIGNAL
```

`OUT_OF_DOMAIN`, informational/legal pages, buyer/source pages, fetch failures, and unproven pages do not count as useful clothing signals.

## Decision rule

The scorecard compares:

```text
useful_clothing_yield - out_of_domain_rate
```

A minimum symmetrically verified sample is required for **both** providers before a lead can be declared.

Possible decisions:

```text
EXA_LEADS
BRAVE_LEADS
NO_CLEAR_LEADER
INSUFFICIENT_EVIDENCE
```

Raw result count is diagnostic only and cannot choose a provider.

## Safety / architecture

- Shadow/read-only only.
- No automatic provider activation or disabling.
- No production mutation.
- No new workflow is required by V1.
- No provider is promoted from one run.
- Out-of-domain results may be measured as noise but cannot teach positive provider quality.

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
