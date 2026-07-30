# Estate Manager Enrichment Pilot v1.0

## Goal

Enrich one manually selected, already-reviewed clothing bankruptcy lead with the
company identity and publicly registered professional estate-manager role needed
for human follow-up.

## Scope

The pilot performs exactly one lookup:

```text
GET https://konkurs.app/api/konkursbo/{estate_orgnr}
```

The estate organisation number must be supplied manually. The pilot does not run
a list search, schedule, person search, contact action, sale search, or financial
analysis.

## Retained fields

- estate organisation number and name;
- debtor organisation number and name;
- bankruptcy opening date;
- industry and municipality;
- publicly registered estate-manager professional role name;
- official Brønnøysund estate URL.

It does not retain private addresses, personal phone numbers, private email
addresses, birth dates, or unrelated roles.

## Output contract

```text
estate-manager-enrichment.json
live-clothing-top5.json
operator-summary.txt
```

`live-clothing-top5.json` remains empty because estate-manager identification is
not evidence that inventory exists or is offered for sale.

## Manual execution

```bash
python scripts/run_estate_manager_enrichment_pilot.py \
  --estate-orgnr 938018014
```

## State transition

```text
PRE_MARKET_LEAD
  -> ESTATE_MANAGER_IDENTIFIED
  -> OPERATOR_REVIEW_REQUIRED
```

The state cannot advance to `VERIFIED_ACTIVE_INVENTORY_SALE` without current sale
and inventory evidence.

## Safety boundaries

- one explicitly selected estate only;
- no systematic person database;
- no automatic contact or email;
- no bid, purchase, reservation, commitment, or payment;
- no commercial Top 5 or Analysis Engine admission.
