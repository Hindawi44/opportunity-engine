# Pre-Market Sale Channel — Five-Case Validation v1.0

**Validation date:** 2026-07-30  
**Domain:** `CLOTHING_INVENTORY`  
**Result:** `NO_PUBLIC_SALE_OR_LIQUIDATION_CHANNEL_CANDIDATE_FOUND`

## Purpose

Validate the most important missing bridge in the pre-market path: after a
clothing bankruptcy and estate-manager identity are known, determine whether an
indexed public sale listing or a traceable liquidation channel can be discovered
without weakening the evidence gate.

## Cases

The bounded live pilot searched these five manually selected estates:

| Debtor | Estate organisation number |
|---|---:|
| MENSWEAR NORGE AS | 938018014 |
| KEEPFIT AS | 938022038 |
| BIRKHANS AS | 938119295 |
| MARK AND BRANDY AS | 937884796 |
| CHEERMANIA AS | 938108897 |

## Search execution

For every estate, the runner:

1. read exactly one approved Konkurs.app estate record;
2. built five exact-identity search queries;
3. used the debtor name, estate name, debtor organisation number, and estate
   organisation number;
4. targeted sale, auction, inventory, estate-manager, and liquidation wording;
5. retained only exact organisation-number or exact legal-company-name matches.

Live totals:

```text
Estates searched: 5
Queries per estate: 5
Total search requests: 25
Raw web hits reviewed by the gate: 200
Search errors: 0
Completed estate scans: 5/5
```

## Strict final result

After the identity and inventory-lot gates:

```text
Sale-listing candidates requiring page verification: 0
Liquidation-channel candidates requiring page verification: 0
Public sale found: false
Inventory sale verified: false
Liquidation channel verified: false
Commercial Top 5 count: 0
```

This means no indexed public result found at the validation time simultaneously
provided enough exact company identity and sale/inventory or liquidation-channel
evidence to justify page verification.

It does **not** prove that:

- no inventory remains;
- no direct or private sale is taking place;
- no liquidator has been appointed outside indexed public pages;
- no future auction or listing will appear.

## False-positive correction

An initial live run retained a FINN result for a product named `Cheermania`.
The page described an ordinary gymnastics beam and was unrelated to CHEERMANIA
AS or its bankruptcy estate.

The gate was corrected before final validation:

- legal company suffixes such as `AS` and `ASA` are preserved in exact identity
  matching;
- a brand or product-name occurrence cannot equal the legal company identity;
- sale candidates require an explicit inventory-lot signal such as `vareparti`,
  `restlager`, `varelager`, `lagerbeholdning`, `kleslager`, or a material stated
  quantity;
- sale and liquidation signals are classified separately;
- URL path wording is not treated as sale or liquidation evidence.

The corrected live run excluded the false result and completed with zero errors.

## Commercial interpretation

The search layer is useful because it can test the public-sale bridge without
turning generic company references or ordinary products into opportunities. The
zero result is an honest outcome: the current public web did not expose a
traceable sale or liquidation-company relationship for these five estates under
the approved strict gate.

The strongest next evidence source is therefore the estate-management channel.
For each high-priority estate, a human-approved professional enquiry should ask:

1. whether clothing inventory remains in the estate;
2. whether it has already been sold or reserved;
3. whether a liquidator, auction house, or sale agent has been appointed;
4. where and when the sale will be announced;
5. whether interested buyers may be registered before public publication.

No message is sent automatically by the project.

## State contract

All five cases remain:

```text
ESTATE_MANAGER_IDENTIFIED
  -> TARGETED_SALE_CHANNEL_SEARCH_COMPLETE
  -> NO_PUBLIC_CANDIDATE_FOUND
  -> OPERATOR_CONTACT_REVIEW_REQUIRED
```

They do not advance to:

```text
VERIFIED_ACTIVE_INVENTORY_SALE
TOP5_ELIGIBLE
ANALYSIS_ELIGIBLE
```

## Safety

- no FINN page was opened or scraped;
- no login was used;
- no automatic contact was performed;
- no bid, purchase, reservation, commitment, or payment was made;
- search snippets were never treated as proof of sale.
