# Human review learning and study-link memory — contract v1

This contract supplements issue #885. The user decides on real item-/lot-specific source URLs using three explicit actions: **STUDY**, **DELETE**, and **LATER**. No algorithm or commercial-qualification gate may make these decisions or silently suppress an otherwise valid direct listing.

## Durable decisions and links

- The existing append-only `human_review_outcomes` SQLite history is the authority for recorded operator actions. Do not claim that clicking a ChatGPT conversation control writes to it unless a verified connector call actually persisted the event. An explicit bridge from UI to the repository with a confirmed acknowledgement is required.
- Each reviewed listing has a stable opportunity identity, a canonical *direct original source URL*, title, market, source, evidence timestamp, latest human action and optional human-stated reason. Restore all unresolved STUDY bookmarks from prior successful checkpoint state; include them in a dedicated study inbox even if the source stops appearing in today's search. If source availability is stale, label it unverified; don't claim the item is still for sale.
- STUDY bookmarks the direct URL and queues more research. It **does not** mean `VERIFIED`, `ACTIVE_OPPORTUNITY`, profitable, or commercially qualified. DELETE suppresses future inbox duplicates but keeps the audit trail; LATER postpones without deletion. A later explicit user decision supersedes an earlier one; preserve both events.
- Existing `HumanReviewOutcome` enum offers VERIFIED/NEEDS_MORE_INFORMATION/REJECTED/CLOSED, which is not a lossless representation of STUDY versus LATER. Add explicit action storage or a versioned lossless, tested mapping before wiring controls; never map STUDY to VERIFIED or LATER to REJECTED. Avoid two competing authorities.

## Learning from human decisions

- Only actual persisted, explicit decisions are training signals. Store positive STUDY and negative DELETE feedback with optional stated reason; LATER is neutral. Missing actions and expired links are NOT negative votes.
- Build transparent counts/examples by supported source, market and evidence-backed category/route, deduplicated per opportunity with latest decision; keep original event history for audit. Display suggestions about which kinds of *direct offers to show first*, never auto-exclude other valid direct offers, change production queries/paid providers or declare commercial profitability.
- Present an explanation, sample size, timestamp, and uncertainty for each suggestion; sparse samples generate `INSUFFICIENT_FEEDBACK` instead of overconfident preferences. Keep preference memory distinct from source facts and commercial qualification.

## Acceptance checks

1. A manually chosen STUDY record is committed once and its real source URL survives the next successful checkpoint (including if it is not newly discovered); duplicate replay is idempotent.
2. DELETE suppresses that identity from the human-review inbox, not from auditable discovery and history. LATER stays retrievable and does not count as a rejection.
3. All direct offers are available for review even when `commercially_qualified_count=0`; category/search pages are tracked as signals, not listings.
4. User action counts and memory snapshots reflect real persisted decisions; they never infer choices from ChatGPT prose, image matches, novelty or model judgments.
5. No automatic contact, reservation, bid, purchase, payment, source promotion or paid API budget changes.

**Status:** specification, not an implemented feature; verify code, tests, workflow artifact and next-run restoration before announcing deployment.
