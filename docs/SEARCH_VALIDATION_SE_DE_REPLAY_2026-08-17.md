# Search Validation Replay — Sweden / Germany

**Date:** 2026-08-17  
**Mode:** saved-artifact replay only  
**Live Brave requests:** 0  
**OpenAI requests:** 0

## Purpose

Identify the dominant loss stage in the core Search/Discovery layer before any new downstream work or paid live rerun.

Evidence comes from the saved scheduled Multi-Market Daily Operator Checkpoint artifacts:

- run #141 — 2026-08-15
- run #156 — 2026-08-16
- run #190 — 2026-08-17

This analysis does not treat a green workflow as search-quality proof.

## Sweden

### Blinto

Observed across the three saved runs:

| Run | Brave raw hits | Source accepted hits | Merged candidates | Historical/ended | Confirmed active |
|---|---:|---:|---:|---:|---:|
| #141 | 51 | 10 | 6 | 6 | 0 |
| #156 | 51 | 10 | 6 | 6 | 0 |
| #190 | 61 | 16 | 7 | 7 | 0 |

Diagnosis:

`RETRIEVAL_WORKS_BUT_INDEX_IS_STALE`

The source pack repeatedly retrieves traceable item pages, but every merged candidate is historical/ended. The correct response is not to weaken lifecycle verification.

### Klaravik

Run #190:

- 8 Brave requests;
- 80 raw hits;
- 47 source-accepted hits;
- 16 merged candidates;
- 16 historical/ended;
- 0 confirmed active.

Diagnosis:

`RETRIEVAL_WORKS_BUT_INDEX_IS_STALE`

The accepted examples include genuine bulk clothing inventory pages, but the source status gate correctly prevents old indexed auctions from becoming active opportunities.

### PS Auction

Run #190:

- 8 Brave requests;
- 72 raw hits;
- 47 source-accepted hits;
- 27 merged candidates;
- 21 strong leads requiring verification;
- 6 historical/ended before the final 21-lead verification block;
- 0 confirmed active;
- 14 verification failures;
- 7 verification-not-attempted blocks.

The bounded source-page verifier attempted six exact PS Auction pages and confirmed none as active. Indexed corroboration resolved those six as ended.

Diagnosis:

`STATUS_VERIFICATION_AND_STALE_INDEX_BOTTLENECK`

This is not primarily a retrieval-recall failure anymore. Search is finding relevant lot identities; the unresolved problem is proving current lifecycle state safely and efficiently.

## Germany

### Deutsche Pfandverwertung

Across runs #141/#156/#190 the active source watch discovered roughly 11–14 auction entries per day and selected two active catalog entries, but produced zero clothing catalogs and zero qualifying clothing child lots.

Diagnosis:

`CURRENT_SOURCE_INVENTORY_COVERAGE`

The collector is functioning. The sampled active inventory did not contain qualifying clothing stock.

### Riegermann

Across all three runs, approximately 13 current auctions were discovered each day, but zero auctions contained clothing evidence and zero auctions were selected for child-lot parsing.

Diagnosis:

`CURRENT_SOURCE_INVENTORY_COVERAGE`

The active auctions were from unrelated sectors such as camera retail, construction and vehicles. Zero clothing output here is not evidence that the collector is broken.

### VENTA

Across all three runs, roughly 598 public item URLs were observed from active catalogs, with zero qualifying clothing child lots.

Important false-positive guards worked correctly:

- a catalog was superficially marked with `textilien` because page chrome exposed `Textil (0)`, although the actual auction was gastronomy inventory;
- `Kleiderhaken` and `Kleiderstangen` were correctly rejected as fixtures/equipment rather than clothing stock.

Diagnosis:

`LOW_SOURCE_FIT_WITH_FALSE_POSITIVE_GUARDS_WORKING`

No gate should be weakened merely to force a German opportunity from this source.

### Sen & Sen — concrete false-negative defect

Run #190 used six bounded Brave requests and returned 21 raw Sen & Sen results. All 21 were rejected.

The dominant rejection was:

`Sen & Sen URL is not one specific public sale page` — 17 results.

However one repeated rejected result was itself a specific public object/lot page:

`o7580-1_Textilien-Warenbestand_aus_Insolvenz`

Its indexed evidence contained:

- explicit `Textilien` clothing identity;
- explicit `Warenbestand` bulk inventory identity;
- explicit insolvency/sale context;
- `Komplett-Verkauf bevorzugt` in the snippet.

The defect was structural: the source contract accepted only `/php/t<ID>-...` event pages even though Sen & Sen also exposes exact `/php/o<ID>-...` object/lot pages.

Diagnosis:

`URL_GATE_FALSE_NEGATIVE`

## P0 correction

The source gate should accept both exact Sen & Sen detail shapes:

```text
/php/t<ID>-...
/php/o<ID>-...
```

while still rejecting:

- generic `dilib.php` pages;
- PDF files;
- index/search pages;
- unrelated hosts;
- object pages without clothing evidence;
- object pages without bulk inventory evidence;
- object pages without sale/insolvency evidence.

The `o7580` page must become only a **traceable lead**. It must not be declared active from search-index evidence. Exact-page lifecycle verification remains authoritative.

## Decision

1. Fix the Sen & Sen exact-object URL false negative offline.
2. Keep Sweden lifecycle gates unchanged.
3. Do not widen VENTA/DPV/Riegermann gates to manufacture German output.
4. Run all regressions with zero Brave usage.
5. Only after the offline correction is green should one future production observation be used to measure whether Sen & Sen yields a verified active lead.
6. Search Validation Gate remains closed until the frozen proof policy is met.
