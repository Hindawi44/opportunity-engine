# BANKRUPTCY Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `BANKRUPTCY`  
**Status:** READY FOR REVIEW  
**Purpose:** Define how the Discovery Engine recognizes and preserves clothing-inventory opportunities that arise from a company bankruptcy without treating the bankruptcy itself as proof that assets are for sale.

---

## 1. Real-world event

A company operating in clothing, footwear, accessories, bridal, textiles, retail, wholesale, import, distribution, or related apparel activity enters bankruptcy proceedings.

The bankruptcy may create one of two fundamentally different records:

1. **Bankruptcy lead:** the company is bankrupt, but clothing inventory availability is not confirmed.
2. **Confirmed bankruptcy sale:** inventory or a clothing-related asset lot is publicly offered for sale, auction, tender, or direct negotiation.

A bankruptcy notice alone is not a purchase opportunity.

---

## 2. Seller and administrator motivation

Possible motivations include:

- converting estate assets into cash for creditors;
- reducing storage, rent, insurance, and handling costs;
- disposing of seasonal or time-sensitive inventory quickly;
- selling complete stock as one lot to simplify administration;
- selling selected categories separately when the estate expects higher recovery;
- transferring stock, webshop assets, fixtures, brand rights, or customer-facing operations together;
- accepting offers before a formal auction when permitted by the estate process.

The Discovery Engine must not assume which motivation applies unless supported by evidence.

---

## 3. Opportunity forms

The scenario may appear as:

- bankruptcy notice with no sale confirmation;
- estate administrator or trustee contact lead;
- complete clothing inventory for sale;
- partial inventory lot;
- mixed lot containing clothing, accessories, footwear, fixtures, and packing materials;
- public auction;
- sealed-bid or offer process;
- direct sale from the bankruptcy estate;
- sale of webshop inventory and operating assets;
- sale of one branch or warehouse stock;
- sale through an auction house, liquidation company, estate manager, or marketplace;
- already-sold or expired estate listing.

---

## 4. Scenario boundaries

### Included

- bankrupt clothing store;
- bankrupt fashion company;
- bankrupt footwear or accessories retailer with commercially meaningful stock;
- bankrupt bridal, textile, importer, distributor, wholesaler, or apparel webshop;
- estate sale containing apparel inventory;
- bankruptcy lead where company activity strongly suggests relevant inventory and a public contact route exists.

### Excluded

- bankruptcy news unrelated to apparel or textiles;
- personal bankruptcy with ordinary household clothing;
- one used garment sold by a private individual;
- job losses or closure news without a relevant company or contact route;
- legal commentary without an identifiable estate or asset lead;
- companies whose only relation to clothing is incidental uniforms or workwear with no commercial inventory signal;
- dissolved or deleted companies where no current bankruptcy or sale process is evidenced.

---

## 5. Norwegian language signals

Signals are evidence inputs, not automatic decisions.

### Strong bankruptcy signals

- `konkursbo`
- `konkursåpning`
- `tatt under konkursbehandling`
- `selskapet er konkurs`
- `konkursrammet`
- `boet selger`
- `selges av konkursboet`
- `på vegne av konkursboet`
- `bostyrer`
- `bobestyrer`
- `boets eiendeler`
- `varelager fra konkursbo`
- `hele varelageret fra konkursbo`
- `konkursauksjon`
- `bud ønskes på varelager`

### Strong clothing-inventory signals

- `klær`
- `bekledning`
- `mote`
- `tekstil`
- `sko`
- `tilbehør`
- `brudekjoler`
- `butikkvarer`
- `varelager`
- `restlager`
- `engrosparti`
- `partivarer`
- `nettbutikklager`
- `butikkinnredning og varelager`

### Medium bankruptcy signals

- `avvikles etter konkurs`
- `driften er innstilt`
- `virksomheten har opphørt`
- `boet vurderer salg`
- `interessenter bes melde seg`
- `aktiva til salgs`
- `eiendeler realiseres`
- `lager og driftsmidler`
- `frist for bud`
- `salg etter avtale med bostyrer`

### Weak or contextual signals

- `stengt`
- `nedlagt`
- `opphørt`
- `tvangsavvikling`
- `betalingsproblemer`
- `rekonstruksjon`
- `store rabatter`
- `alt skal bort`
- `lager tømmes`

Weak signals require additional evidence. They must not create a bankruptcy classification alone.

---

## 6. Context combinations

### A. Confirmed bankruptcy sale

Qualify as `SALE_CONFIRMED` when evidence combines:

1. a bankruptcy-estate or administrator signal;
2. a clear apparel or clothing-inventory subject;
3. an explicit sale, auction, bid, price, or offer process;
4. a public source URL or contact route.

Example pattern:

```text
konkursbo + varelager med klær + selges samlet + budfrist
```

### B. Bankruptcy lead requiring contact

Qualify as `CONTACT_REQUIRED` when evidence combines:

1. confirmed bankruptcy;
2. company activity relevant to clothing inventory;
3. identifiable company, estate, or administrator;
4. no verified asset-sale statement.

Example pattern:

```text
klesbutikk konkurs + bostyrer identified + inventory availability unknown
```

### C. Ambiguous insolvency signal

Preserve for manual review only when:

- the company appears apparel-related;
- bankruptcy status is uncertain or secondary;
- the source is incomplete, stale, or indirect;
- no public sale or administrator route has yet been verified.

### D. Rejected result

Reject when bankruptcy language appears but no commercially relevant apparel inventory or actionable lead exists.

---

## 7. False positives

Common false positives include:

- news reports about a fashion chain with no estate or sale information;
- ordinary clearance sales falsely described by advertisers as `konkurssalg`;
- marketing pages using `konkurspriser` without an actual bankruptcy estate;
- SEO pages aggregating bankruptcies with no company details or contact route;
- old auction pages where the deadline has passed and the lot is sold;
- articles about creditor losses, employees, or court proceedings without asset information;
- a bankruptcy involving a restaurant, contractor, or unrelated company that owned a few uniforms;
- duplicate pages describing the same estate sale;
- social-media reposts without a traceable original source;
- private sellers claiming goods came from a bankruptcy without supporting evidence.

---

## 8. Likely publication channels

Channels describe where the event may appear. They do not govern the architecture.

- public bankruptcy registers and court notices;
- estate administrator or law-firm websites;
- auction houses and liquidation companies;
- company websites and webshop closure pages;
- marketplaces and classified listings;
- local and national news;
- trade publications;
- Facebook pages, groups, and public posts;
- supplier, landlord, logistics, or warehouse announcements;
- direct public notices inviting offers;
- company registries and public corporate records.

The Discovery Engine should preserve the original source and any authoritative supporting source separately.

---

## 9. Minimum discovery data

A bankruptcy candidate may be preserved when the system can record:

- company or estate name;
- source URL;
- bankruptcy evidence or source statement;
- clothing-related business or inventory signal;
- scenario: `BANKRUPTCY`;
- record type: sale listing or bankruptcy lead;
- location when available;
- public contact route when available;
- discovered timestamp;
- source provider and source domain;
- short description of what may be available;
- current qualification status;
- missing fields.

A confirmed sale additionally requires explicit sale evidence.

---

## 10. Permitted unknowns

The following may remain unknown during discovery:

- exact quantity;
- brand list;
- size distribution;
- purchase price;
- VAT treatment;
- reserve price;
- bid deadline;
- condition;
- storage conditions;
- ownership of brands, webshop, or customer data;
- transport and collection terms;
- whether inventory is pledged or subject to third-party rights;
- whether the estate will split the lot;
- whether the goods have already been sold;
- market value and profitability.

Unknown fields must remain `null`, `unknown`, or `needs verification`.

---

## 11. Opportunity Dossier evidence targets

### Source and legal context

- original bankruptcy notice;
- estate administrator name and public contact details;
- court, registry, or authoritative company record;
- estate or case reference when public;
- dates: bankruptcy opening, publication, bid deadline, inspection, collection;
- terms and conditions of sale;
- statements about liens, retention of title, or third-party ownership when available.

### Inventory evidence

- listing title and full text;
- all publicly accessible images;
- inventory lists, spreadsheets, PDFs, catalogues, and attachments;
- visible product categories;
- visible brands, labels, packaging, sizes, and quantities;
- racks, shelves, boxes, pallets, warehouse context, and store condition;
- indicators of new, returned, damaged, seasonal, sample, or used stock;
- whether fixtures and equipment are included.

### Sale-process evidence

- asking price, reserve, current bid, or offer instruction;
- whether sale is whole-lot, partial-lot, auction, tender, or direct negotiation;
- inspection possibility;
- collection location;
- dismantling, loading, packing, and transport responsibility;
- VAT statement;
- payment deadline;
- exclusions and disclaimers;
- current availability status.

### Provenance rule

Every dossier fact must link to its source. Observations from images must be marked as observations, not confirmed inventory counts.

---

## 12. Qualification outcomes

### `SALE_CONFIRMED`

Use when the estate or authorized seller explicitly offers relevant clothing inventory for sale.

### `CONTACT_REQUIRED`

Use when bankruptcy and apparel relevance are confirmed, but inventory sale or availability is not.

### `DISCOVERED`

Use for an early candidate that needs authoritative bankruptcy or company verification.

### `REJECTED`

Use when the record is irrelevant, misleading, unsupported, or commercially insignificant.

### `EXPIRED`

Use when the sale deadline has passed, the assets are sold, or the source confirms that the opportunity is no longer active.

---

## 13. Seller or estate questions

Questions must be prepared for human use. The system must not send them automatically.

1. Is the clothing inventory still available?
2. Is the sale handled by the bankruptcy estate or an authorized third party?
3. Is an inventory list available?
4. What categories, brands, sizes, and quantities are included?
5. Are the goods new, returns, samples, damaged, or used?
6. Is the stock sold as one lot or can it be divided?
7. Is VAT added to the winning bid or sale price?
8. Are any goods pledged, leased, consigned, or owned by suppliers?
9. Are fixtures, racks, packaging, webshop assets, or trademarks included?
10. Where is the stock stored, and can it be inspected?
11. Who is responsible for packing, loading, dismantling, and transport?
12. What is the bid or offer deadline?
13. Has any part of the stock already been sold or removed?
14. Are there restrictions on resale, branding, customer data, or territorial rights?

---

## 14. Controlled example fixtures

These fixtures are synthetic and exist for later implementation tests. They are not live findings.

### Fixture A — confirmed sale

```yaml
raw_title: "Varelager fra konkursbo - dameklær og tilbehør"
raw_description: "Boet selger samlet ca. 2 400 nye varer. Budfrist 18. august. Visning etter avtale med bostyrer."
expected_scenario: BANKRUPTCY
expected_status: SALE_CONFIRMED
expected_record_type: SALE_LISTING
reason: "Bankruptcy estate, relevant inventory, explicit sale, quantity and bid process."
```

### Fixture B — contact-required lead

```yaml
raw_title: "Lokal motebutikk tatt under konkursbehandling"
raw_description: "Butikken er stengt. Advokat Kari Nord er oppnevnt som bostyrer. Ingen opplysninger om salg av varelageret."
expected_scenario: BANKRUPTCY
expected_status: CONTACT_REQUIRED
expected_record_type: BANKRUPTCY_LEAD
reason: "Bankruptcy and apparel activity are confirmed, but inventory sale is not."
```

### Fixture C — ambiguous marketing claim

```yaml
raw_title: "Konkurssalg - 70 % rabatt på klær"
raw_description: "Nettbutikken fortsetter som før. Ordinær kampanje denne uken."
expected_status: REJECTED
reason: "Marketing language without evidence of a bankruptcy estate."
```

### Fixture D — irrelevant bankruptcy

```yaml
raw_title: "Byggfirma konkurs"
raw_description: "Maskiner og verktøy kan bli solgt."
expected_status: REJECTED
reason: "No clothing-inventory relevance."
```

### Fixture E — expired estate sale

```yaml
raw_title: "Konkursbo selger komplett skobutikklager"
raw_description: "Budfrist 12. januar 2025. Solgt."
expected_status: EXPIRED
reason: "Relevant but no longer active."
```

### Fixture F — duplicate

```yaml
candidate_1_url: "https://example.no/estate/fashion-stock"
candidate_2_url: "https://example.no/estate/fashion-stock?utm_source=facebook"
expected_behavior: "Normalize URLs and preserve one canonical candidate with combined provenance."
```

---

## 15. Acceptance tests

The future implementation must satisfy all of the following:

1. A bankruptcy notice alone never becomes `SALE_CONFIRMED`.
2. A relevant bankruptcy with an identifiable public contact route may become `CONTACT_REQUIRED`.
3. An explicit estate sale of clothing inventory becomes `SALE_CONFIRMED`.
4. Missing price, quantity, VAT, brands, sizes, or transport data does not cause rejection.
5. Missing values are never invented.
6. `konkurssalg` used only as marketing language does not prove bankruptcy.
7. Unrelated bankruptcies are rejected.
8. Expired or sold estate listings are marked `EXPIRED`, not active.
9. Duplicate URLs are normalized without losing source provenance.
10. Image-derived observations remain separate from confirmed facts.
11. Confirmed sales may proceed to Opportunity Dossier collection.
12. Contact-required leads remain outside financial analysis until sale availability is confirmed.
13. No automatic purchase, bid, or contact action is generated.
14. Existing V2.8–V3.7 financial logic remains untouched.

---

## 16. Completion decision

This knowledge card is complete for review when it provides an implementable distinction between:

```text
bankruptcy event
  -> bankruptcy lead
  -> confirmed asset sale
  -> Opportunity Dossier
  -> existing Analysis Engine
```

The critical rule is:

> Bankruptcy is an opportunity signal, not proof that inventory is available for purchase.
