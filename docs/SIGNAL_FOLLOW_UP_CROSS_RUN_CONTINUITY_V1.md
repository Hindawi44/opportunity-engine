# SIGNAL_FOLLOW_UP_CROSS_RUN_CONTINUITY_V1

## Decision

`SIGNAL_FOLLOW_UP_ENGINE_V1` remains unchanged. Cross-run continuity is added as a wrapper above it.

The purpose is to keep a qualified company scent alive across daily checkpoint runs until source-verifiable commercial inventory evidence appears.

## Durable identity

Only cross-source signals already classified by `ENTITY_SCENT_QUALITY_GATE_V1` as `ENTITY_SCENT` enter this memory path. They are grouped by:

```text
market_code + entity_key
```

The signals are stored through the existing `MarketSignalRepository` in the SQLite files that the daily checkpoint already restores from the previous successful artifact. No new database technology or table is introduced.

The first post-deployment run can also bootstrap from the previous checkpoint's exact allow-listed file:

```text
cross-source-scent-v2/cross-source-scent-expansion-v2.json
```

No arbitrary JSON is restored.

## Search progression

A persistent German entity rotates by calendar day through:

```text
WARENBESTAND
→ AUKTION
→ LAGERVERKAUF
→ VERWERTUNG
→ KONKRETE_LOTS
→ repeat
```

Sweden and Norway use equivalent local-language stages. Multiple runs on the same calendar day keep the same stage; the next day advances the scent rather than restarting the same broad query.

## Budget and priority

Persistent entity cases are selected before generic current-run early signals. The existing bounded follow-up case limit is retained. Any unused case slots are filled by the unchanged `SIGNAL_FOLLOW_UP_ENGINE_V1`.

This fixes the observed Run #151 starvation pattern where the strong entity scents:

- Adenauer & Co (DE)
- Stores For You AB (SE)
- Schümer Textil GmbH (DE)

were present in Cross-Source Scent V2 but the four follow-up slots were consumed by newer unrelated cases.

## Evidence boundary

A search result remains:

```text
UNVERIFIED_PUBLIC_WEB_SEARCH_HIT
```

It is not commercial proof. Source-page verification remains required before the existing opportunity gates can act on it.

The continuity layer never:

- promotes a search hit directly into an opportunity;
- changes Top 5 eligibility;
- contacts a seller;
- bids or reserves;
- purchases or pays.

The human operator remains the decision owner.
