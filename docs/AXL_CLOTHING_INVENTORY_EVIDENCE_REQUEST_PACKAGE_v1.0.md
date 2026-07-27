# AXL Clothing Inventory Evidence Request Package v1.0

**Task:** `AXL_CLOTHING_INVENTORY_EVIDENCE_REQUEST_PACKAGE`  
**Domain:** `CLOTHING_INVENTORY`  
**Opportunity ID:** `CLOTHING_INVENTORY:NO:934309715:AXL`  
**Candidate:** `AXL Sport og Fritid Kolvereid AS konkursbo`  
**Prepared at:** `2026-07-27`  
**Package status:** `EVIDENCE_REQUEST_PACKAGE_PREPARED`  
**Send status:** `NOT_SENT`  
**Human approval:** `REQUIRED`  
**Commercial decision:** `NO_DECISION`  
**Automatic contact:** Prohibited

## 1. Purpose

Prepare one concise, human-reviewable Norwegian evidence request for the confirmed active AXL Clothing Inventory opportunity.

The package converts the material unknowns in the merged Opportunity Dossier into:

- one primary Norwegian email;
- one shorter contact-form version;
- one telephone script;
- one optional follow-up message;
- one evidence checklist;
- one structured response-intake contract;
- explicit human-approval and safety gates.

This package does not send any message, place a call, submit an offer, reserve goods, bid, purchase, pay, calculate profit, or create an investment decision.

## 2. Canonical package result

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
DOSSIER_EVIDENCE_REQUIRED
EVIDENCE_REQUEST_PACKAGE_PREPARED
HUMAN_APPROVAL_REQUIRED
NOT_SENT
NO_DECISION
```

The opportunity remains retained in operator and final reports while active. Incomplete information is not a rejection reason.

## 3. Authorised contact routing

### 3.1 Preferred first route

The merged AXL Opportunity Dossier identifies Norsk Avvikling as the preferred first route because it publicly presents the active bankruptcy sale.

| Field | Confirmed value | Use |
|---|---|---|
| Recipient organisation | `Norsk Avvikling AS` | Primary sale operator |
| Email | `info@norskavvikling.no` | Preferred written request |
| Telephone | `480 75 000` | Optional human follow-up |
| Website | `https://norskavvikling.no/` | Source and contact verification |
| Address | `Norvald Strands veg 45, 2212 Kongsvinger` | Published operator address |

### 3.2 Estate-administrator fallback

| Field | Confirmed value | Use |
|---|---|---|
| Estate | `AXL SPORT OG FRITID KOLVEREID AS KONKURSBO` | Estate identity |
| Estate organisation number | `937 325 746` | Reference |
| Administrator | `Adv. Nils Christian Sudbø Brandzæg` | Authorised estate route |
| Postal route | `Postboks 8809 Nedre Elvehavn, 7481 Trondheim` | Written fallback only |

No direct administrator email or telephone number is preserved in the dossier. None may be invented.

### 3.3 Store route

The public AXL store contact route proves traceability but is not automatically treated as the authoritative acquisition route after bankruptcy. It should not be used for sale negotiations unless Norsk Avvikling or the estate administrator confirms that it is authorised.

## 4. Human approval gate

Before any message is sent, the human operator must verify all of the following:

- the AXL sale is still publicly active;
- the recipient address is still published by the authorised operator;
- the sender name, company name, telephone, and email are correct;
- the message does not contain an offer or commitment;
- no unsupported quantity, price, value, or deadline is stated;
- no confidential or unnecessary personal data is included;
- attachments, if any, are intentional and safe;
- the operator explicitly approves the final wording and recipient.

Required state before manual sending:

```text
HUMAN_APPROVED_FOR_MANUAL_SEND
```

The repository, workflow, assistant, or program must not create that state automatically.

## 5. Primary Norwegian email

### 5.1 Recipient and subject

```text
Til: info@norskavvikling.no
Kopi: Ingen som standard
Emne: Forespørsel om lagerliste og salgsvilkår – AXL Sport og Fritid Kolvereid konkursbo
```

### 5.2 Ready-for-human-review message

```text
Hei,

Jeg vurderer muligheten for å kjøpe hele eller deler av varebeholdningen etter AXL Sport og Fritid Kolvereid AS konkursbo, særlig klær og fottøy.

For å kunne gjøre en seriøs og dokumentert vurdering, ønsker jeg gjerne følgende informasjon:

1. Er salget fortsatt aktivt, og hvem er riktig kontaktperson for videre dialog om kjøp?
2. Selges varebeholdningen samlet, i flere kategoripartier eller som enkeltvarer?
3. Finnes det en oppdatert lagerliste i Excel-, CSV- eller PDF-format?
4. Kan lagerlisten vise varenummer/SKU, merke, produktnavn, størrelse, farge, antall og tilstand?
5. Hvor mange fysiske enheter er fortsatt tilgjengelige, fordelt på klær, fottøy og øvrige varer?
6. Hva er prisforventningen eller prosessen for å gi tilbud, og er beløpet inkludert eller ekskludert merverdiavgift? Tilkommer det kjøpergebyr eller andre kostnader?
7. Er det mulig å kjøpe klær og fottøy separat fra fiske-, jakt-, hunde- og øvrige varer?
8. Er visning mulig, og finnes det oppdaterte bilder av den fysiske varebeholdningen?
9. Hvor er varene lagret, hva er fristen for henting, og finnes det hjelpemidler eller bemanning for lasting?
10. Er varene pakket i esker, på paller eller på stativer, og finnes det opplysninger om antall kolli, pallmål, volum eller vekt?
11. Er noen varer allerede solgt, reservert, returnert, unntatt fra salget eller eid av tredjepart?
12. Finnes det innkjøpsfakturaer, leverandørlister, kostprisopplysninger eller en offentlig bostyrerrapport som kan deles?

Dere kan gjerne sende det materialet som allerede er tilgjengelig. Dersom en annen person håndterer salget, setter jeg pris på å bli videresendt til riktig kontakt.

Denne henvendelsen er kun en forespørsel om informasjon og innebærer ikke et bindende tilbud eller en forpliktelse til kjøp.

På forhånd takk for hjelpen.

Vennlig hilsen
Mahmoud Hindawi
Namsos Skredderhus
Telefon: [FYLL INN OG KONTROLLER]
E-post: [FYLL INN OG KONTROLLER]
```

## 6. Short Norwegian contact-form version

Use only when the available contact form has a limited text field.

```text
Hei,

Jeg vurderer mulig kjøp av hele eller deler av varebeholdningen etter AXL Sport og Fritid Kolvereid AS konkursbo, særlig klær og fottøy.

Kan dere bekrefte om salget fortsatt er aktivt og sende en oppdatert lagerliste med SKU/produkt, merke, størrelse, antall og tilstand? Jeg ønsker også informasjon om salgsform, pris-/tilbudsgrunnlag, MVA og gebyrer, mulighet for delkjøp, visning, lagersted, henting, pakking og lasting.

Henvendelsen er kun en forespørsel om informasjon og er ikke et bindende tilbud.

Vennlig hilsen
Mahmoud Hindawi – Namsos Skredderhus
Telefon: [FYLL INN]
E-post: [FYLL INN]
```

## 7. Norwegian telephone script

This script is for a human call only. No automatic calling is permitted.

```text
Hei, mitt navn er Mahmoud Hindawi, og jeg ringer fra Namsos Skredderhus.

Jeg har sett at konkursboet etter AXL Sport og Fritid Kolvereid fortsatt er oppført med pågående salg. Jeg vurderer mulig kjøp av hele eller deler av varebeholdningen, særlig klær og fottøy.

Er du riktig person å snakke med om dette?
```

If yes:

```text
Takk. Før jeg kan vurdere dette seriøst, trenger jeg en oppdatert lagerliste og informasjon om salgsform, pris eller tilbudsprosess, MVA og gebyrer, mulighet for delkjøp, visning, lagersted, henting, pakking og lasting.

Kan dere sende dette til meg på e-post? Jeg kan også sende en skriftlig oversikt over spørsmålene.
```

If no:

```text
Kan du gi meg navn og kontaktinformasjon til personen som er ansvarlig for salget, eller videresende henvendelsen min?
```

Closing:

```text
Takk for hjelpen. Dette er foreløpig bare en informasjonsforespørsel og ikke et bindende tilbud.
```

## 8. Optional Norwegian follow-up message

This message may be used only after a human confirms that the original request was sent and no adequate response has been received. The program must not schedule or send it automatically.

```text
Emne: Oppfølging – forespørsel om AXL Sport og Fritid Kolvereid konkursbo

Hei,

Jeg følger opp min tidligere forespørsel om varebeholdningen etter AXL Sport og Fritid Kolvereid AS konkursbo.

Jeg er fortsatt interessert i å motta en oppdatert lagerliste og informasjon om salgsform, pris-/tilbudsgrunnlag, MVA og gebyrer, mulighet for delkjøp, visning, lagersted, henting, pakking og lasting.

Dersom en annen person er ansvarlig for salget, setter jeg pris på å bli henvist eller videresendt til riktig kontakt.

Henvendelsen er ikke et bindende tilbud.

Vennlig hilsen
Mahmoud Hindawi
Namsos Skredderhus
Telefon: [FYLL INN OG KONTROLLER]
E-post: [FYLL INN OG KONTROLLER]
```

## 9. Evidence request checklist

### 9.1 Inventory scope

| Requested evidence | Minimum acceptable response | Current status |
|---|---|---|
| Dated inventory list | Excel, CSV, PDF, or other machine-readable/exportable list | REQUIRED |
| Total physical units | Current count on response date | REQUIRED |
| Clothing units | Separate current count | REQUIRED |
| Footwear units | Separate current count | REQUIRED |
| Non-clothing units | Separate current count or explicit exclusion | REQUIRED |
| SKU/product identity | SKU or another stable product identifier | REQUIRED |
| Brand | Brand by line item where available | REQUIRED |
| Product name/model | Product identity by line item | REQUIRED |
| Size | Size by line item where relevant | REQUIRED |
| Colour | Colour by line item where available | REQUIRED |
| Quantity | Quantity by SKU/variant | REQUIRED |
| Condition | New, display, returned, used, damaged, incomplete, or other | REQUIRED |
| Physical availability | Confirmation that listed units remain available | REQUIRED |

### 9.2 Sale and legal scope

| Requested evidence | Minimum acceptable response | Current status |
|---|---|---|
| Sale remains active | Explicit dated confirmation | REQUIRED |
| Authorised contact | Name or function responsible for negotiations | REQUIRED |
| Sale structure | Whole lot, category lots, or individual products | REQUIRED |
| Ability to split | Explicit yes/no and permitted categories | REQUIRED |
| Included goods | Clear scope of what is included | REQUIRED |
| Sold/reserved/excluded goods | Updated exclusions or status flags | REQUIRED |
| Third-party ownership | Explicit disclosure or confirmation | REQUIRED |
| Retention-of-title issues | Explicit disclosure when applicable | REQUIRED |
| Warranty/condition basis | AXL-specific sale terms or reference to applicable terms | REQUIRED |

### 9.3 Price and payment

| Requested evidence | Minimum acceptable response | Current status |
|---|---|---|
| Asking price or offer basis | Published price, reserve, bid basis, or offer instruction | REQUIRED |
| Currency | Explicit transaction currency | REQUIRED |
| VAT treatment | Including/excluding MVA and applicable basis | REQUIRED |
| Buyer premium | Percentage or amount, or explicit none | REQUIRED |
| Other fees | Description and amount/basis, or explicit none | REQUIRED |
| Payment method | Accepted method | REQUIRED |
| Payment deadline | Dated term or rule | REQUIRED |
| Offer deadline | Dated term when applicable | REQUIRED |

### 9.4 Inspection and logistics

| Requested evidence | Minimum acceptable response | Current status |
|---|---|---|
| Inspection | Availability, booking route, date, and conditions | REQUIRED |
| Current physical photographs | Dated images of the remaining stock | REQUIRED |
| Storage address | Exact physical pickup location | REQUIRED |
| Pickup deadline | Date and time window | REQUIRED |
| Access restrictions | Vehicle, door, floor, stairs, loading-zone, or site limits | REQUIRED |
| Loading support | Labour, forklift, pallet jack, or explicit none | REQUIRED |
| Packing form | Boxes, racks, loose units, pallets, or mixed | REQUIRED |
| Number of packages/pallets | Current count | REQUIRED |
| Dimensions | Pallet/package dimensions when available | REQUIRED |
| Weight or volume | Verified or supplier-provided logistics data | REQUIRED |

### 9.5 Supporting documents

| Requested evidence | Use | Current status |
|---|---|---|
| Purchase invoices | Cost and provenance evidence; not automatically resale value | OPTIONAL_BUT_MATERIAL |
| Supplier list | Brand and replenishment/provenance context | OPTIONAL_BUT_MATERIAL |
| Original cost records | Cost evidence only | OPTIONAL_BUT_MATERIAL |
| Sale prospectus | Transaction scope and terms | OPTIONAL_BUT_MATERIAL |
| Estate report | Verified bankruptcy background; not required for inventory valuation | OPTIONAL_BUT_MATERIAL |

## 10. Response-intake contract

Every reply, attachment, photograph, and telephone note must be preserved with provenance.

### 10.1 Required intake metadata

```yaml
opportunity_id: CLOTHING_INVENTORY:NO:934309715:AXL
request_package_version: 1.0
request_sent: false
sent_by_human: null
sent_at: null
recipient: null
recipient_role: null
channel: null
response_received: false
response_received_at: null
response_sender: null
response_sender_role: null
attachments: []
telephone_notes: []
source_references: []
automatic_contact: false
automatic_purchase_decision: false
commercial_decision: NO_DECISION
```

A future intake task may replace `null` values only with human-confirmed or source-preserved facts.

### 10.2 Evidence classes

Every received field must use one of the approved classes:

```text
CONFIRMED_SOURCE_FACT
CONFIRMED_ATTACHMENT_FACT
CONFIRMED_IMAGE_FACT
SELLER_CLAIM_UNVERIFIED
ESTIMATE
UNKNOWN
CONFLICTING_EVIDENCE
```

Rules:

- an email statement from the authorised sale contact is a source fact for what the contact stated, but may still require independent verification for physical count or condition;
- an inventory spreadsheet is not automatically current unless it has a date or the sender confirms current remaining quantities;
- photographs support visible facts only and must not produce exact counts unless reliably countable;
- catalogue entries remain separate from physical inventory units;
- missing price, VAT, fee, or logistics values remain unknown and are never treated as zero;
- conflicting quantities or sale terms must be preserved as `CONFLICTING_EVIDENCE`.

## 11. Response completeness evaluation

### 11.1 Complete enough for dossier update

Use:

```text
EVIDENCE_RESPONSE_RECEIVED
DOSSIER_UPDATE_ALLOWED
NO_DECISION
```

when a traceable response provides meaningful new evidence, even if some fields remain missing.

### 11.2 Partial response

Use:

```text
EVIDENCE_RESPONSE_PARTIAL
DOSSIER_EVIDENCE_REQUIRED
NO_DECISION
```

The opportunity remains retained. Missing evidence must be listed precisely.

### 11.3 No response

Use:

```text
EVIDENCE_REQUEST_SENT_BY_HUMAN
NO_RESPONSE_RECORDED
DOSSIER_CONTACT_REQUIRED
NO_DECISION
```

No automatic follow-up, rejection, or deletion is permitted.

### 11.4 Sale ended or stock unavailable

Use an ended, withdrawn, sold, or unavailable state only when supported by dated evidence from the authorised operator or another reliable source.

Possible result:

```text
SALE_ENDED_OR_INVENTORY_UNAVAILABLE
DOSSIER_EXPIRED_OR_INACCESSIBLE
NO_DECISION
```

Incomplete information alone must not create this state.

## 12. Analysis gates after response

### 12.1 Market-comparable gate

Remain blocked until the response establishes enough representative or complete product identity, condition, sizes, and current physical availability to select valid comparables.

```text
BLOCKED_EVIDENCE_REQUIRED
```

### 12.2 Acquisition-cost gate

Remain blocked until acquisition price or offer basis, VAT, fees, payment terms, pickup conditions, packing/loading requirements, and transport evidence are verified.

```text
BLOCKED_EVIDENCE_REQUIRED
```

### 12.3 Financial-analysis gate

The existing Analysis Engine remains unavailable until its existing evidence contracts are satisfied.

The following remain prohibited now:

```text
expected_profit_nok
roi_percent
maximum_safe_bid_nok
BUY_REVIEW
WATCH
REJECT
```

No catalogue price may be used as an acquisition price or physical-stock valuation.

## 13. Operator-facing package summary

```text
AXL Clothing Inventory
Opportunity: Confirmed active bankruptcy inventory opportunity
Dossier: Evidence required
Request package: Prepared
Recipient: Norsk Avvikling AS
Primary channel: info@norskavvikling.no
Send status: Not sent
Human approval: Required
Decision: No decision
Requested evidence: current inventory, units, SKU/brand/size/condition, sale structure, price, MVA, fees, inspection, pickup, packing, loading, logistics, exclusions
Next external action: human reviews and manually sends the approved request
Next repository action: wait for a preserved response before response intake
```

## 14. Safety invariants

```text
automatic_contact: false
automatic_email_send: false
automatic_call: false
automatic_follow_up: false
automatic_offer: false
automatic_bid: false
automatic_reservation: false
automatic_purchase_decision: false
automatic_payment: false
```

The wording in this package is non-binding and must remain non-binding unless a later, separately approved human action explicitly authorises an offer.

## 15. Scope protection

This task must not:

- send the prepared request;
- create or edit a Gmail draft;
- place a telephone call;
- search for or invent private contact data;
- submit an offer or price;
- treat public catalogue counts as physical quantities;
- calculate market value, acquisition cost, expected profit, ROI, or maximum bid;
- invoke `BUY_REVIEW`, `WATCH`, or `REJECT`;
- modify workflows, production code, classifiers, tests, fixtures, state, cache, financial formulas, scoring thresholds, or decision policy;
- add another opportunity domain or source adapter.

## 16. Definition of done

This task is complete only when:

1. exactly one evidence-request-package document is added;
2. the preferred authorised route is preserved from the merged dossier;
3. one concise Norwegian primary email is prepared;
4. one short contact-form version is prepared;
5. one human telephone script is prepared;
6. one optional human follow-up message is prepared;
7. all material evidence requests map to known dossier gaps;
8. a response-intake contract and evidence classifications are defined;
9. incomplete evidence preserves the opportunity rather than rejecting it;
10. the send status remains `NOT_SENT` and human approval remains required;
11. no contact, offer, bid, reservation, purchase, payment, or financial decision occurs;
12. exactly one conditional next repository task is identified.

## 17. Conditional next task only

No immediate automated task may send this request.

The human operator may review, edit, and manually send the message outside the repository. After a reply or other traceable response is received and preserved, exactly one repository task may follow:

```text
AXL_CLOTHING_INVENTORY_EVIDENCE_RESPONSE_INTAKE
```

That task must ingest the response and attachments, classify every material field, update the dossier evidence state, and determine whether the market-comparable and acquisition-cost gates remain blocked.

It must not invent missing values or issue an investment decision.