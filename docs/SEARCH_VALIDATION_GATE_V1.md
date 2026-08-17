# SEARCH VALIDATION GATE V1

## Purpose

Stop treating a green workflow as proof that Search/Discovery is commercially useful.

The project may continue to retain all existing layers, but **new downstream development is not authorized until the core search layer is proven from repeated live evidence**.

The gate is deliberately offline and read-only. It reads saved JSON artifacts only and makes **zero Brave, OpenAI, source-page, or other external API calls**.

## Required order

```text
SEARCH / DISCOVERY
  -> SEARCH VALIDATION GATE
  -> MEMORY / FOLLOW-UP (only after Search is PROVEN)
  -> VERIFICATION
  -> COMMERCIAL / MATH
  -> LANGUAGE
  -> PROBABILITY LAW
```

Existing downstream code is not deleted. It is simply not evidence that Search itself works.

## Source verdicts

Each source receives exactly one verdict:

- `PROVEN`
- `NOT_PROVEN`
- `INSUFFICIENT_EVIDENCE`

The frozen V1 proof policy is:

1. at least **3 independent live runs**;
2. retrieval success rate at least **80%**;
3. at least **50% of runs** produce one accepted traceable lead;
4. at least **2 independent runs** produce a **verified active** lead;
5. paid-search request accounting must be present before a paid source can be marked `PROVEN`.

The thresholds are defined before judging new runs. A green workflow, a large raw-hit count, or many unverified leads cannot substitute for these conditions.

## Cost accounting

The gate records:

- paid requests made;
- paid requests per verified active lead;
- accepted leads;
- rejected results;
- verification conversion rate.

V1 does not convert requests to USD because provider pricing can change. Dollar cost policy can be layered later without changing the search-proof evidence.

## Market and project verdict

A market is `PROVEN` when at least one source in that market is `PROVEN`.

The overall core Search layer is `PROVEN` only when all required core markets are proven. The default required markets remain:

```text
NO / SE / DE
```

IT / NL / FR are measured when their artifacts are supplied, but they do not weaken or silently change the frozen core-market contract.

When the overall verdict is not `PROVEN`:

```text
progression_gate_open = false
next_stage_authorized = null
```

When the overall verdict becomes `PROVEN`, the only newly authorized next stage is:

```text
MEMORY_FOLLOW_UP
```

Math, Language and probability-law work remain separately gated.

## First offline diagnosis using Run #191

The saved Run #191 artifact can be evaluated without any new Brave spending.

It contains useful evidence, including:

- Auksjonen: one active inventory opportunity in the source artifact;
- PS Auction: many traceable bulk leads but zero confirmed active sales in that run;
- several SE/DE source paths with zero accepted leads;
- active early-signal radar evidence;
- IT/NL/FR discovery sidecars.

But Run #191 is only **one live observation**. Therefore the correct Search proof verdict from that run alone is:

```text
INSUFFICIENT_EVIDENCE
```

This is intentionally different from GitHub Actions `PASS` / `SUCCESS`.

## Usage

Evaluate one saved run:

```bash
python scripts/build_search_validation_gate.py \
  --run-dir /path/to/run191
```

Evaluate repeated independent runs:

```bash
python scripts/build_search_validation_gate.py \
  --run-dir /path/to/run191 \
  --run-dir /path/to/run194 \
  --run-dir /path/to/run195
```

The default output is:

```text
artifacts/search-validation/search-validation-gate-v1.json
```

## Safety

This gate does not:

- call Brave;
- call OpenAI;
- browse any source site;
- add a workflow or schedule;
- change Top 5;
- change commercial scoring;
- contact a seller;
- bid, reserve, purchase or pay.
