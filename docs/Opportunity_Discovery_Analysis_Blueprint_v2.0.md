# Opportunity Discovery & Analysis Blueprint v2.0

## Status

**Approved strategic blueprint — design baseline**

## Vision

Build a specialized platform for discovering and analyzing apparel and textile opportunities in Norway.

The platform does not begin from a fixed website list. It begins from the commercial question:

> How can this opportunity appear in the real market?

It then discovers relevant opportunities, converts them into a standard opportunity record, and sends qualified records to the existing analysis engine.

## Product Goal

A user should be able to enter a search topic such as:

- Clothing inventory
- Wedding dresses
- Sewing equipment
- Fabrics
- Boutique fixtures

The system should return concise, practical opportunities such as:

- A clothing store closing and selling its complete stock
- A fashion company entering bankruptcy
- An auction containing a large apparel lot
- An importer liquidating excess inventory
- A warehouse surplus sale

The user should not need to choose websites manually.

## Core Architecture

```text
User search intent
        ↓
Opportunity Discovery Engine
        ↓
Opportunity Map
        ↓
Discovery Strategy
        ↓
Discovered Candidate
        ↓
Discovery Qualification
        ↓
Canonical Opportunity Contract
        ↓
Existing Analysis Engine
        ↓
Review Queue and Human Review
```

## System Boundaries

The project now consists of two clearly separated engines.

### 1. Opportunity Discovery Engine

Responsibilities:

- Understand what the user wants to find
- Expand the topic into real commercial opportunity scenarios
- Search for those scenarios
- Collect links and minimal facts
- Classify each result
- Reject irrelevant results
- Convert qualified discoveries into the canonical opportunity contract

The Discovery Engine does not calculate ROI, estimate unsupported costs, or issue a purchase decision.

### 2. Analysis Engine

The existing engine remains authoritative for financial analysis and operational review.

It includes:

- V2.8 — Market Comparables
- V2.9 — Auction Cost and Logistics Evidence
- V2.10 — Verified Financial Integration and Decision Gate
- V2.11 — Live Opportunity Validation
- V3.0 — Multi-Opportunity Ranking
- V3.1 — Live Batch Validation
- V3.2 — Continuous Monitoring
- V3.3 — Live Source Ingestion and Snapshot Refresh
- V3.4 — Persistent Opportunity State
- V3.5 — Opportunity Alert and Review Queue
- V3.6 — Multi-Source Ingestion
- V3.7 — Production Pilot

These versions are not replaced. They become the downstream analysis layer for newly discovered opportunities.

## Discovery Principle

The system must not begin with:

```text
FINN
Auksjonen
Konkurs
```

It must begin with:

```text
What type of commercial opportunity are we trying to find?
```

Websites are execution channels, not the product model.

## First Opportunity Domain

The first domain is:

# Clothing Inventory

This domain was selected because it covers a broad set of apparel-related opportunity scenarios and provides a strong test of the Discovery Engine.

## Clothing Inventory Opportunity Map

```text
Clothing Inventory
│
├── Store closing
├── Company bankruptcy
├── Inventory liquidation
├── Auction
├── Warehouse surplus
├── Importer liquidation
├── Manufacturer excess production
├── Large lot sale
├── Business model change
└── Branch closure
```

Each branch is a commercial scenario, not a source.

## Scenario Definitions

### Store Closing

A retail store is closing and offers all or part of its inventory for sale.

Typical signals:

- opphørssalg
- avvikling
- butikken legges ned
- alt skal bort
- closing sale

### Company Bankruptcy

A company in apparel, footwear, accessories, bridal, textile, or related retail has entered bankruptcy.

This can produce either:

- a bankruptcy lead requiring follow-up, or
- a confirmed asset sale

A bankruptcy notice alone is not a confirmed purchase opportunity.

### Inventory Liquidation

A company sells inventory to release capital, end a product line, or wind down operations.

### Auction

A lot or complete inventory is offered through a public auction.

### Warehouse Surplus

Excess stock is sold from a warehouse, importer, distributor, or wholesaler.

### Importer Liquidation

An importer or distributor sells remaining stock, discontinued lines, returns, or unsold seasonal goods.

### Manufacturer Excess Production

A manufacturer sells overproduction, cancelled orders, factory seconds, or discontinued production.

### Large Lot Sale

A person or company sells a substantial group of apparel products as one lot.

### Business Model Change

A business changes category, closes a department, moves online, or exits apparel retail.

### Branch Closure

A company closes one physical branch and disposes of inventory or fixtures.

## Minimum Discovery Data

The system must distinguish discovery data from decision data.

A result may qualify for discovery when the following minimum information is available:

- What is being sold or potentially available
- Opportunity scenario or record type
- Norway location, when available
- Public link or contact route
- Evidence that this is more than an irrelevant single-item listing

The following are not mandatory at discovery time:

- Complete brand list
- Size distribution
- Model year
- Full image set
- VAT treatment
- Transport cost
- Exact quantity
- Comparable market value

Missing details must remain `null` or explicitly unknown. The system must not invent them.

## Discovery Record Types

### SALE_LISTING

A confirmed public sale, auction, liquidation, or lot listing.

### BANKRUPTCY_LEAD

A company bankruptcy or closure signal where assets are not yet confirmed for sale.

### STORE_CLOSURE_LEAD

A store closure or operational shutdown signal requiring confirmation of available stock.

### LIQUIDATION_LEAD

A liquidation signal without a sufficiently defined sale listing.

### REJECTED_RESULT

A result outside the target commercial scope.

## Discovery Statuses

```text
DISCOVERED
QUALIFIED
CONTACT_REQUIRED
SALE_CONFIRMED
REJECTED
EXPIRED
```

## Qualification Rules

The Discovery Engine should classify results as follows.

### Green — Confirmed Opportunity

Use when there is a real sale or auction and the subject clearly matches the target domain.

Example:

> Complete clothing-store inventory for sale, approximately 1,800 items.

### Yellow — Follow-Up Required

Use when the commercial signal is relevant but the assets or sale are not yet confirmed.

Example:

> Fashion company entered bankruptcy; inventory availability is not confirmed.

### Red — Rejected

Use when the result is not commercially relevant to the configured objective.

Examples:

- One ordinary used garment
- Sewing services
- Fashion courses
- Job advertisements
- News articles without an opportunity signal
- Expired or inaccessible listings

## Discovery Workflow

```text
User enters: Clothing Inventory
        ↓
Load Clothing Inventory Opportunity Map
        ↓
Generate search strategies per scenario
        ↓
Collect public candidates
        ↓
Normalize title, URL, location, source and text
        ↓
Classify scenario and record type
        ↓
Reject irrelevant candidates
        ↓
Deduplicate candidates
        ↓
Save qualified discoveries
        ↓
Convert confirmed sales to Canonical Opportunity
        ↓
Send confirmed opportunities to V2.8–V3.7
```

## Relationship to Existing Analysis Engine

A `BANKRUPTCY_LEAD` or other unconfirmed lead must not be forced into financial analysis.

Correct path:

```text
Bankruptcy or closure signal
        ↓
Lead qualification
        ↓
Asset or sale confirmation
        ↓
Canonical Opportunity
        ↓
V2.8 Market Comparables
        ↓
V2.9 Acquisition Cost
        ↓
V2.10 Financial Integration
        ↓
Ranking, Monitoring and Review Queue
```

## User Experience

The user should not see raw technical versions or hundreds of unfiltered links.

Example output:

```text
Results: Clothing Inventory

🟢 Confirmed sale
A clothing store is closing and selling its complete inventory.
Location: Oslo
Source: public sale listing
Status: SALE_CONFIRMED
Next action: start evidence collection

🟡 Follow-up required
A fashion company entered bankruptcy.
Location: Bergen
Assets: not confirmed
Status: CONTACT_REQUIRED
Next action: identify the estate administrator and ask about inventory

🔴 Rejected
Single ordinary used jacket.
Reason: does not match the configured lot/inventory objective
```

## Initial Domain Roadmap

Domains will be added only after the Clothing Inventory map is validated.

Planned order:

1. Clothing inventory
2. Wedding dresses
3. Industrial sewing equipment
4. Fabrics and textile lots
5. Clothing-store fixtures and equipment

## Development Rules

- Do not modify V2.8–V3.7 unless a confirmed compatibility defect is found.
- Do not add new financial formulas during Discovery Engine development.
- Do not require complete decision data during discovery.
- Do not hard-code the product around one website.
- Do not treat a bankruptcy notice as a confirmed asset sale.
- Do not generate automatic purchase decisions.
- Do not invent missing facts.
- Add one opportunity map at a time.
- Require one end-to-end acceptance test before expanding to the next domain.

## First Acceptance Target

The first implementation milestone should prove one full Clothing Inventory discovery cycle.

Input:

```text
clothing inventory
```

The test must include at least:

- one confirmed sale listing
- one bankruptcy or closure lead
- one irrelevant result
- one duplicate result

Expected behavior:

- confirmed sale is converted to a canonical opportunity
- lead remains outside financial analysis until confirmed
- irrelevant result is rejected
- duplicate is removed
- no unsupported values are generated
- existing analysis engine receives only eligible opportunities

Suggested acceptance summary:

```json
{
  "blueprint_version": "2.0",
  "domain": "CLOTHING_INVENTORY",
  "confirmed_sales": 1,
  "follow_up_leads": 1,
  "rejected_results": 1,
  "duplicates_removed": 1,
  "unsupported_values_generated": false,
  "analysis_engine_compatibility": true,
  "automatic_purchase_decision": false,
  "status": "PASS"
}
```

## Final Product Definition

The product is not:

> A tool that monitors FINN and Auksjonen.

The product is:

> A Norwegian apparel and textile opportunity discovery and analysis platform that understands how commercial opportunities appear, discovers them across public channels, and evaluates confirmed opportunities using evidence-based financial analysis.

## Executive Decision

This blueprint is the architectural reference for the next phase of the project.

The immediate next step after approval is to design and validate the complete **Clothing Inventory Opportunity Map** before implementing broader discovery automation.
