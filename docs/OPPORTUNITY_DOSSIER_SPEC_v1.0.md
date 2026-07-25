# Opportunity Dossier Specification v1.0

**Status:** APPROVED DESIGN SPECIFICATION  
**Domain for first validation:** `CLOTHING_INVENTORY`

## 1. Purpose

An Opportunity Dossier converts a discovered advertisement, auction, closure signal, bankruptcy lead, or sale listing into a traceable evidence package that the existing Analysis Engine can consume safely.

The dossier is not a financial decision. It is the evidence bridge between discovery and analysis.

## 2. Core rule

```text
Discovery finds the opportunity.
Dossier gathers and structures evidence.
Analysis evaluates economics.
```

No layer may invent missing facts.

## 3. Required dossier sections

### 3.1 Identity and source

- Opportunity ID
- Domain
- Scenario
- Record type
- Current status
- Source URL
- Source provider and source domain
- Discovery query
- Discovery timestamp
- Advertisement title
- Advertisement description
- Publication and expiry dates when available

### 3.2 Seller and location

- Seller or estate name
- Company organization number when public
- Contact route
- Physical location
- Pickup location
- Geographic evidence source

### 3.3 Sale terms

- Asking price or current bid
- Currency
- VAT statement exactly as published
- Sale method: fixed price, auction, offer, contact-required
- Whole lot or partial sale
- Deadline
- Inspection availability
- Pickup and removal terms

Unknown sale terms must remain unknown; they must not be inferred from normal market practice.

### 3.4 Inventory evidence

- What is being sold
- Product categories
- Stated quantity
- Stated units
- Brands explicitly named
- Sizes explicitly named
- Condition explicitly stated
- Original retail values only when supported by evidence
- Inventory list or attachments
- Whether the stock appears complete, partial, mixed, or unclear

### 3.5 Images and attachments

For every publicly accessible image or attachment:

- Preserve the source URL or file reference.
- Record image order and caption when available.
- Record what is visibly supported.
- Separate visible fact from estimate.
- Do not claim exact counts from crowded images unless reliably countable.
- Record inaccessible or protected images as unavailable.

Possible image-derived observations include:

- Product categories
- Visible brand labels
- Packaging condition
- Shelf, rack, pallet, box, or warehouse presence
- Signs of water, dirt, damage, or poor storage
- Evidence that the lot is larger or smaller than the text suggests

### 3.6 Evidence classification

Every extracted field must use one of these classes:

- `CONFIRMED_SOURCE_FACT`
- `CONFIRMED_IMAGE_FACT`
- `ESTIMATE`
- `SELLER_CLAIM_UNVERIFIED`
- `UNKNOWN`
- `CONFLICTING_EVIDENCE`

Estimates must include a confidence level and a short reason.

### 3.7 Missing data

The dossier must explicitly list missing information that affects analysis, including when relevant:

- Complete inventory list
- Exact quantity
- Brand and size distribution
- Purchase invoices
- Original cost basis
- Retail-price evidence
- VAT treatment
- Transport requirements
- Loading support
- Storage requirements
- Damage, returns, seconds, or obsolete stock
- Right to split the lot
- Sale deadline

Missing data is not a rejection reason during discovery.

### 3.8 Seller questions

Generate a concise, opportunity-specific question list. Questions must target only material unknowns and must not repeat facts already present.

Typical questions:

- Does the sale include the entire inventory or only the photographed items?
- Is there an Excel or PDF inventory list?
- How many total units are included?
- Which brands and size ranges are represented?
- Is the price including or excluding MVA?
- Can the lot be divided?
- Are purchase invoices or original cost records available?
- Where is the stock stored and what vehicle is required?
- Is loading equipment available?
- What is the final deadline?

### 3.9 Market-comparison handoff

The dossier may prepare comparable-search attributes but must not fabricate a market value.

Prepared attributes may include:

- Category
- Brand
- Condition
- New or used status
- Quantity range
- Geographic market
- Comparable unit type

The Analysis Engine owns comparable collection, valuation, costs, profitability, and ranking.

## 4. Minimum viable dossier

A dossier may proceed to analysis only when it has:

- A valid source or contact route
- A clear description of what may be sold
- A classified scenario
- Evidence that the opportunity is a commercial lot or inventory event rather than an ordinary single-item listing
- A complete list of known and unknown fields

A dossier does not need complete price, VAT, quantity, transport, or inventory details to exist.

## 5. Output states

- `DOSSIER_READY_FOR_ANALYSIS`
- `DOSSIER_EVIDENCE_REQUIRED`
- `DOSSIER_CONTACT_REQUIRED`
- `DOSSIER_REJECTED_NO_COMMERCIAL_OPPORTUNITY`
- `DOSSIER_EXPIRED_OR_INACCESSIBLE`

## 6. Safety and honesty rules

- Never invent price, quantity, brands, VAT, transport cost, or market value.
- Never convert a bankruptcy notice into a confirmed sale without sale evidence.
- Never describe an image as downloaded if only a thumbnail or inaccessible reference was available.
- Preserve conflicts instead of silently choosing one source.
- Every important statement must be traceable to a source, image, attachment, or explicit estimate method.
- No automatic purchase, bid, seller contact, or commitment is permitted.

## 7. First validation target

The first validation will use one Clothing Inventory case and prove that the system can:

1. Capture the advertisement and all accessible evidence.
2. Extract facts from text and images.
3. Identify unknowns.
4. Generate seller questions.
5. Prepare a safe handoff to the existing Analysis Engine.
6. Produce either a final report or an honest evidence-required result.
