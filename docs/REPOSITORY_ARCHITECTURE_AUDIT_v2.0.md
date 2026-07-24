# Opportunity Engine — Repository Architecture Audit v2.0

**Status:** Approved for repository reorganization planning  
**Primary reference:** `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`  
**Scope:** Architecture, ownership boundaries, legacy classification, and next implementation step.  
**Safety rule:** This audit does not delete production code, alter financial formulas, or change automatic decision safeguards.

---

## 1. Executive conclusion

The repository is not broken. It contains two valid generations of architecture that now overlap:

1. A source-first ingestion path built around named sites such as Auksjonen and FINN.
2. A discovery-first path built around Opportunity Maps, scenario-driven web discovery, and an Opportunity Contract.

The overlap creates ambiguity about which path owns discovery. The approved direction is:

```text
Opportunity Map
  -> Discovery Strategy
  -> Open Web Discovery
  -> Minimum Discovery Data
  -> Opportunity Contract
  -> Existing Analysis Engine (V2.8–V3.7)
  -> Ready For Review
```

The source-specific adapters remain usable as optional ingestion tools, but they are not the governing architecture.

---

## 2. Governing documents

### Primary strategic reference

- `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`

This document governs all new development. It separates:

- **Discovery Engine:** discovers opportunities and gathers the minimum discovery data.
- **Analysis Engine:** evaluates confirmed opportunities using the existing financial and evidence pipeline.

### Supporting historical references

- `docs/MASTER_BLUEPRINT.md`
- `docs/PROJECT_AUDIT_v1.0.md`

These remain useful for historical context and earlier design decisions, but they must not override Blueprint v2.0 when the documents conflict.

---

## 3. Repository capability inventory

### A. Discovery foundation — KEEP

The following capabilities align with Blueprint v2.0 and remain part of the active architecture:

- Discovery candidate/result contracts.
- Clothing inventory Opportunity Map.
- Scenario-driven Norwegian query generation.
- Brave live-search provider abstraction.
- URL normalization and deduplication.
- Initial classification into confirmed sale, contact-required lead, and rejected result.
- Safe handling of missing values without inventing price, quantity, location, or contact data.
- Phone-readable reporting and JSON artifacts.

Representative paths include:

- `src/opportunity_engine/discovery/`
- `tests/test_discovery_opportunity_maps.py`
- `.github/workflows/discovery-v1-clothing-inventory.yml`

### B. Discovery support filters — KEEP, BUT NON-GOVERNING

The following layers are useful support tools but must not define whether an opportunity is financially attractive:

- V1.5 Intelligent Result Filter.
- V1.6 Opportunity Quality Engine.

Their correct role is:

```text
reduce obvious noise
  -> prioritize human review
  -> never replace the Analysis Engine
```

They must remain optional and must not block a valid opportunity merely because price, VAT, transport, brands, sizes, or market comparables are not yet available during discovery.

### C. Existing Analysis Engine — KEEP AND FREEZE

The following completed capabilities form the current Analysis Engine and should not be rebuilt:

- V2.8 Market Comparables and verified comparable evidence.
- V2.9 Acquisition Cost and logistics evidence.
- V2.10 Verified Financial Integration and decision gate.
- V2.11 Live Opportunity Validation.
- V3.0 Ranking.
- V3.2–V3.4 Monitoring, snapshots, and persistent state.
- V3.5 Review Queue and non-duplicate alerts.
- V3.7 production-pilot orchestration.

These components remain the downstream analysis pipeline. New Discovery work must integrate with them through a stable contract rather than modify their formulas.

### D. Source-specific ingestion — LEGACY/OPTIONAL

The following work remains technically useful but is no longer the strategic starting point:

- Auksjonen-specific ingestion.
- FINN-specific ingestion.
- Multi-source ingestion built around a fixed list of sites.

Classification:

```text
LEGACY OPTIONAL ADAPTERS
```

Rules:

- Do not delete them now.
- Do not extend them as the default project direction.
- They may later serve as optional high-confidence source adapters behind the Discovery Strategy layer.
- They must not force the system to begin from a list of websites.

### E. Diagnostic and historical workflows — ARCHIVE CANDIDATES

The repository contains many workflows created to diagnose intermediate failures in Brave parsing, price extraction, evidence persistence, scoring traces, and contract regressions.

These workflows were valuable during development, but many are no longer part of the normal operator journey.

They should be classified into:

1. **Active production workflows** — retained in the main Actions view.
2. **Acceptance workflows** — retained but clearly named and manually triggered.
3. **Historical diagnostic workflows** — moved later to an archive directory or disabled from routine triggers.

No workflow is deleted by this audit. A separate cleanup PR must list every workflow before any move or disable action.

---

## 4. Architectural conflicts found

### Conflict 1 — Two discovery entry points

The repository currently supports both:

```text
Named source -> adapter -> normalized listing
```

and:

```text
Opportunity scenario -> search strategy -> discovered source
```

**Resolution:** The second path is authoritative. Named-source adapters become optional providers behind it.

### Conflict 2 — Discovery quality versus financial quality

V1.6 can score page-level evidence, but that score is not investment quality.

**Resolution:** Rename its conceptual role to **Discovery Review Priority** in future documentation. Financial attractiveness remains owned by V2.8–V3.x.

### Conflict 3 — Minimum discovery data versus analysis requirements

Some earlier paths rejected records without price or complete costs, while Blueprint v2.0 allows a discovered opportunity with only:

- what is being sold,
- opportunity type,
- location,
- contact or link,
- opportunity size.

**Resolution:** Discovery may preserve missing decision data as `null`. The Analysis Engine is responsible for evidence collection and completion gates.

### Conflict 4 — Too many operator-facing workflows

Development history is exposed as many separate Actions, making the project difficult to operate from a phone.

**Resolution:** Future cleanup should expose one primary discovery workflow and one end-to-end review workflow, while retaining acceptance and historical workflows outside the normal operator path.

---

## 5. Target ownership boundaries

### Discovery Engine owns

- Domain selection.
- Opportunity Maps.
- Discovery scenarios.
- Search-query generation.
- Search-provider execution.
- Source discovery.
- Deduplication.
- Minimum discovery data extraction.
- Discovery status: confirmed sale, lead requiring contact, rejected noise.
- Creating the Opportunity Contract.

### Discovery Engine does not own

- Market valuation.
- Acquisition-cost calculation.
- VAT assumptions.
- Transport, dismantling, storage, or repair estimates without evidence.
- Expected profit or ROI.
- Final investment ranking.
- Buy, bid, or contact decisions.

### Analysis Engine owns

- Market comparables.
- Acquisition-cost evidence.
- Financial integration.
- Evidence validation.
- Ranking.
- Monitoring and state.
- Review Queue.
- Ready-for-review output.

---

## 6. Required Opportunity Contract

The major missing integration point is a stable contract between Discovery and Analysis.

Minimum proposed fields:

```yaml
schema_version: opportunity-contract-1.0
opportunity_id: stable identifier
domain: clothing_inventory
scenario: store_closing | bankruptcy | liquidation | auction | warehouse_surplus | importer_clearance | factory_surplus | large_lot | business_change | branch_closure
status: sale_confirmed | contact_required
what_is_sold: text
opportunity_type: text
location: text | null
source_url: https URL
contact: text | null
opportunity_size:
  quantity: number | null
  unit: text | null
  description: text | null
discovered_at: timestamp
source_provider: text
source_domain: text
discovery_query: text
raw_title: text
raw_description: text | null
discovery_evidence: list
missing_discovery_fields: list
automatic_purchase_decision: false
```

Contract rules:

- Missing analysis data remains `null`.
- No financial estimate is created inside Discovery.
- `sale_confirmed` may enter the Analysis Engine.
- `contact_required` remains in a lead queue until sale availability is confirmed.
- Every field derived from a source must retain traceability.

---

## 7. Keep / freeze / archive matrix

| Area | Decision | Reason |
|---|---|---|
| Blueprint v2.0 | KEEP — PRIMARY | Governing strategic architecture |
| Clothing Inventory Opportunity Map | KEEP — ACTIVE | First approved discovery domain |
| Query Builder and Brave Search | KEEP — ACTIVE | Implements scenario-driven discovery |
| Deduplication and classifier | KEEP — ACTIVE | Required discovery hygiene |
| Phone report | KEEP — ACTIVE | Current mobile operator interface |
| V1.5 Result Filter | KEEP — SUPPORT | Removes obvious noise |
| V1.6 Quality Engine | KEEP — EXPERIMENTAL SUPPORT | Review priority only, not investment quality |
| V2.8–V3.7 | KEEP — FREEZE | Existing Analysis Engine |
| FINN/Auksjonen adapters | KEEP — LEGACY OPTIONAL | Useful providers, not governing architecture |
| Old diagnostics | ARCHIVE CANDIDATES | Reduce Actions and maintenance noise |
| New financial formulas | BLOCKED | Existing formulas are frozen |
| New fixed-source expansion | BLOCKED | Opportunity Maps come first |

---

## 8. Immediate implementation plan

### Phase 1 — Architecture stabilization

1. Adopt this audit with Blueprint v2.0.
2. Do not delete code.
3. Mark legacy adapters and experimental filters in documentation.
4. Freeze financial and ranking formulas.

### Phase 2 — Build the missing bridge

1. Define `OpportunityContract` as a versioned model.
2. Add contract validation tests.
3. Convert confirmed Discovery results to that contract.
4. Keep contact-required leads outside financial analysis.
5. Prove one end-to-end fixture:

```text
Clothing Inventory Opportunity Map
  -> Discovery result
  -> Opportunity Contract
  -> V2.8–V2.11
  -> V3.x
  -> Ready For Review
```

### Phase 3 — Operator simplification

1. Identify the one primary phone workflow.
2. Identify one end-to-end review workflow.
3. Classify all other workflows as acceptance or historical diagnostics.
4. Archive only after a dedicated inventory PR and successful regression run.

### Phase 4 — Expand domains

Only after the clothing-inventory bridge passes:

1. Wedding dresses.
2. Sewing equipment.
3. Fabrics.
4. Clothing-store fixtures.

Each domain must begin with an approved Opportunity Map before code changes.

---

## 9. Next approved development task

The next code task is not V1.7 and not a new source adapter.

It is:

> **Opportunity Contract Bridge v1.0 — Clothing Inventory Discovery to Existing Analysis Engine**

Acceptance criteria:

- One stable contract model.
- No invented values.
- Confirmed sales only enter Analysis.
- Contact-required leads remain separate.
- Existing V2.8–V3.7 tests remain unchanged and passing.
- One end-to-end test reaches `Ready For Review` or returns an honest evidence-required state.
- No automatic purchase, bid, or contact action.

---

## 10. Final decision

The repository will be reorganized conceptually around two engines:

```text
DISCOVERY ENGINE
Discovers and qualifies the existence of an opportunity.

ANALYSIS ENGINE
Evaluates the economics and evidence of that opportunity.
```

No deletion or destructive cleanup is authorized by this document. The first implementation after approval is the Opportunity Contract Bridge, followed by a separate workflow-cleanup inventory.