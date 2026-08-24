# Query Family Shadow Generalization V1

Purpose: keep query-family learning on one reusable shadow path across markets and the two allowed project domains.

The generic core is `opportunity_engine.query_family_shadow`. It owns market anchoring, project-domain gating, scoring, ranking, deduplication metrics, safety flags, and the no-promotion contract.

Market/domain-specific files may provide query text and a verifier adapter only. They do not own ranking logic or production activation.

Current proof:
- NL / FABRIC_PROCUREMENT remains the first live benchmark and query-text fixture.
- Tests also exercise FR / FABRIC_PROCUREMENT and DE / CLOTHING_INVENTORY through the same generic core.

Safety:
- no automatic query promotion
- no production query mutation
- no source promotion
- no provider activation
- no contact, bid, reservation, purchase, or payment

This layer is evidence collection only. A live winner does not become a production query without a separate promotion decision and proof.
