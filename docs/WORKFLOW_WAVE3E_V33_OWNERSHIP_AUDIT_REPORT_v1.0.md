# Workflow Wave 3E — V3.3 Live Source Ingestion Ownership Audit Report v1.0

**Status:** COMPLETE — DOCUMENTATION AND VERIFICATION ONLY  
**Audited workflow:** `.github/workflows/v3.3-live-source-ingestion.yml`  
**Scope lock:** no workflow, trigger, schedule, cache, state, report, artifact, source adapter, or production-code change

## 1. Executive conclusion

Tracked repository evidence supports the following conclusions:

1. V3.3 is the repository-owned Auksjonen live-source ingestion and snapshot-refresh workflow.
2. Its job owns retrieval or fixture-based parsing of the public Auksjonen category page, conversion into the V3.3 snapshot schema, and immediate handoff into V3.2 monitoring logic.
3. The hourly schedule `12 * * * *` is technically independent of V3.2's minute-17 schedule and gives V3.3 a five-minute lead, but repository evidence alone does not prove that hourly live refresh remains operationally necessary.
4. V3.3 and V3.2 use the same logical state path, `data/monitoring/v3.2-seen-state.json`, but restore and save that path under different cache namespaces. This can produce divergent hosted-cache copies of one logical state.
5. The tracked downstream consumer of the V3.3 snapshot is `scripts/run_v34_persistent_opportunity_state.py`. No tracked consumer of the V3.3 report or artifact name was found beyond the workflow and producer script.
6. A later implementation PR should path-scope the broad pull-request trigger. Any schedule reduction, manual-only conversion, cache unification, or state-contract change requires a separate decision and verification PR.
7. Branch-protection rules, external artifact consumers, hosted-cache retention behavior, and external operational dependence remain `MANUAL_VERIFICATION_REQUIRED`.

## 2. Audited workflow contract

### 2.1 Identity and triggers

The workflow contract is:

- display name: `V3.3 Live Source Ingestion & Snapshot Refresh`;
- job identifier: `auksjonen-source-ingestion`;
- pull-request trigger: all pull requests targeting `main`;
- manual trigger: `workflow_dispatch`;
- scheduled trigger: `12 * * * *`.

The pull-request path currently has no `paths` filter. Therefore unrelated pull requests can start V3.3.

### 2.2 Runtime and environment

The job uses:

- `ubuntu-latest`;
- Python `3.11`;
- `PYTHONPATH=${{ github.workspace }}/src:${{ github.workspace }}`;
- `pytest` as its only installed test dependency.

### 2.3 Directly executed test and command

Before ingestion, V3.3 runs:

```text
pytest tests/test_v33_live_source_ingestion.py -q
```

It then runs one of two forms of the same producer script:

```text
python scripts/run_v33_auksjonen_ingestion.py \
  --html-file tests/fixtures/v33_auksjonen_page.html
```

for pull requests, or:

```text
python scripts/run_v33_auksjonen_ingestion.py
```

for manual and scheduled executions.

The pull-request path is deterministic and avoids a live network dependency. Manual and scheduled executions call the public Auksjonen page.

## 3. Source ownership

### 3.1 Owned source

The V3.3 adapter owns the public category page:

```text
https://www.auksjonen.no/auksjoner/overskuddsvarer/vareparti-og-konkursbo
```

The adapter is implemented in:

```text
src/opportunity_engine/source_ingestion/auksjonen.py
```

### 3.2 Adapter responsibilities

The adapter:

- fetches the public HTTPS page with a fixed user agent and HTML accept header;
- rejects non-200 responses and non-HTML content;
- parses JSON-LD and anchor links;
- accepts only Auksjonen HTTPS listing URLs;
- requires a positive NOK asking price;
- derives a stable listing identifier;
- deduplicates listings by listing ID;
- builds a V3.3 snapshot.

It explicitly does not infer:

- missing prices;
- market comparables;
- auction fees;
- VAT;
- transport, dismantling, or storage costs;
- financial or purchase decisions.

### 3.3 Snapshot contract

The producer writes:

```text
data/live_validation/v3.3-auksjonen-live-snapshot.json
```

Each opportunity includes source traceability, active listing status, asking price, empty market-price sources, explicit missing evidence, and no automatic purchase decision.

## 4. Snapshot refresh and monitoring handoff

The producer script is:

```text
scripts/run_v33_auksjonen_ingestion.py
```

Its `run_refresh` function performs this sequence:

```text
public HTML
  -> parse Auksjonen listings
  -> build V3.3 snapshot
  -> call V3.2 build_monitoring_report
  -> produce next seen-state
  -> produce V3.3 ingestion report
```

The script imports V3.2 monitoring logic directly from:

```text
scripts/run_v32_continuous_opportunity_monitoring.py
```

This establishes a direct code dependency: V3.3 is a source-ingestion producer that immediately reuses V3.2 duplicate-detection and monitoring evaluation.

On source failure, the producer:

- records `SOURCE_UNAVAILABLE`;
- records the exception type and message;
- does not overwrite the snapshot, state, or monitoring report;
- returns a failing exit status.

This failure path is explicit and non-destructive.

## 5. State and cache relationship with V3.2

### 5.1 Shared logical state path

V3.3 reads and writes:

```text
data/monitoring/v3.2-seen-state.json
```

V3.2 also owns that same logical state path. The state contains seen fingerprints used to prevent repeated opportunities from being reported as new.

### 5.2 Separate hosted-cache namespaces

V3.3 uses:

```text
v3.3-auksjonen-seen-${{ runner.os }}-${{ github.run_id }}
v3.3-auksjonen-seen-${{ runner.os }}-
```

V3.2 uses its own `v3.2-monitoring-state-...` namespace.

Therefore, GitHub-hosted cache restoration is isolated by workflow namespace even though the restored file path is identical.

### 5.3 Consequence

Tracked evidence supports this risk:

- V3.2 can restore one cached copy of `v3.2-seen-state.json`;
- V3.3 can restore another cached copy;
- both can advance independently;
- the repository does not contain a merge or reconciliation mechanism for those hosted-cache copies.

This does not prove that divergence currently causes a production defect. Hosted-cache continuity and actual run ordering are operational facts outside tracked files and remain `MANUAL_VERIFICATION_REQUIRED`.

### 5.4 Test evidence

`tests/test_v33_live_source_ingestion.py` proves deterministic duplicate protection when the first run's returned state is explicitly supplied to the second run:

- first refresh: three extracted and three new opportunities;
- second refresh with prior state: three extracted and zero new opportunities;
- the seen fingerprints remain stable.

This verifies the state contract in-process. It does not verify cross-workflow GitHub cache synchronization.

## 6. Reports and artifacts

### 6.1 Reports written

V3.3 writes:

```text
data/validation/v3.3-source-ingestion.json
data/validation/v3.2-continuous-monitoring.json
```

The V3.3 report includes:

- source identity and page;
- capture time;
- number of listings extracted;
- snapshot-written flag;
- new-opportunity count;
- ready-for-financial-review count;
- monitoring status;
- errors;
- explicit `automatic_purchase_decision: false`.

### 6.2 Artifact contract

The workflow uploads artifact:

```text
v3.3-auksjonen-source-ingestion
```

containing:

```text
data/live_validation/v3.3-auksjonen-live-snapshot.json
data/validation/v3.3-source-ingestion.json
data/validation/v3.2-continuous-monitoring.json
data/monitoring/v3.2-seen-state.json
```

The upload uses `if: always()` and `if-no-files-found: warn`.

## 7. Tracked consumers

### 7.1 Snapshot consumer

Tracked code search identifies:

```text
scripts/run_v34_persistent_opportunity_state.py
```

as a downstream consumer of:

```text
data/live_validation/v3.3-auksjonen-live-snapshot.json
```

V3.4 compares the refreshed snapshot with lifecycle state, derives NEW/UPDATED/UNCHANGED/REMOVED/ARCHIVED events, and passes actionable changes into V3.2 monitoring.

### 7.2 State consumers

Both V3.3 and V3.4 read or write:

```text
data/monitoring/v3.2-seen-state.json
```

V3.2 is the logical monitoring owner. V3.3 and V3.4 reuse that state contract.

### 7.3 Report and artifact consumers

Tracked search found no separate repository consumer of:

```text
data/validation/v3.3-source-ingestion.json
v3.3-auksjonen-source-ingestion
```

beyond the producer workflow and script.

This is not evidence that no external consumer exists. External downloads, dashboards, notifications, or manual operating procedures remain `MANUAL_VERIFICATION_REQUIRED`.

## 8. Schedule assessment

### 8.1 Current timing

V3.3 runs hourly at minute 12. V3.2 runs hourly at minute 17.

The five-minute spacing is consistent with an intended sequence:

```text
V3.3 source ingestion at :12
  -> V3.2 monitoring at :17
```

However, the workflows do not exchange artifacts or cache namespaces directly, and no tracked orchestration contract guarantees that the V3.3 run finishes before V3.2 starts.

### 8.2 Operational justification status

Repository evidence proves that V3.3 can perform hourly ingestion. It does not prove:

- that Auksjonen changes require hourly polling;
- that rate limits or source terms support this cadence;
- that an operator or external system depends on hourly snapshots;
- that scheduled runs consistently preserve one shared seen-state with V3.2.

Therefore the schedule decision is:

```text
RETAIN_TEMPORARILY_PENDING_DEDICATED_IMPLEMENTATION_DECISION
```

No schedule change is authorized in Wave 3E.

## 9. Future trigger and schedule proposal

### 9.1 Recommended next implementation

The lowest-risk later change is to retain manual and scheduled execution while path-scoping the pull-request trigger to V3.3's tracked dependencies.

Candidate path scope for a dedicated implementation document and PR:

```text
.github/workflows/v3.3-live-source-ingestion.yml
scripts/run_v33_auksjonen_ingestion.py
src/opportunity_engine/source_ingestion/auksjonen.py
scripts/run_v32_continuous_opportunity_monitoring.py
tests/test_v33_live_source_ingestion.py
tests/fixtures/v33_auksjonen_page.html
```

This list is a proposal, not an approved implementation in Wave 3E.

### 9.2 Schedule options for a later decision

A later ownership decision may choose one of:

1. retain hourly minute-12 schedule;
2. reduce cadence while retaining manual dispatch;
3. make V3.3 manual-only;
4. move source ingestion under a separately approved Discovery owner.

Options 2–4 require external-consumer, source-cadence, state/cache, and downstream-snapshot verification first.

### 9.3 State/cache decision required before consolidation

No future PR should unify or rename cache keys merely because the file path is shared. A dedicated state-ownership decision must define:

- the single authoritative writer;
- synchronization or handoff behavior;
- rollback behavior;
- cache retention assumptions;
- duplicate-protection verification across actual workflow runs.

## 10. Risks

| Risk | Classification | Treatment |
|---|---|---|
| Broad pull-request trigger creates unnecessary runs | Confirmed from YAML | Path-scope in a later reversible PR |
| Two cache namespaces can hold divergent copies of one state file | Confirmed structural risk | Dedicated state-ownership decision |
| Hourly cadence may be unnecessary or externally required | Unknown operational fact | Manual verification before schedule change |
| External artifact/report consumers may exist | Unknown external fact | `MANUAL_VERIFICATION_REQUIRED` |
| Branch protection may depend on current check name | Unknown repository setting | `MANUAL_VERIFICATION_REQUIRED` |
| Live source markup or availability may change | Inherent source risk | Preserve fixture test and explicit source-failure report |
| V3.4 depends on the V3.3 snapshot path | Confirmed tracked dependency | Preserve snapshot path unless consumer migration is approved |

## 11. Rollback requirements for future implementation

A future trigger-only PR must record the pre-change workflow blob SHA:

```text
ba4f271395388b14881176b228efc211b0ea0a3f
```

Rollback is a direct revert restoring that workflow blob.

A future schedule, state, cache, report, artifact, or source-adapter change requires its own rollback contract and must not be bundled with trigger scoping.

## 12. Required verification for a future implementation PR

A future V3.3 trigger-scoping PR must verify:

1. valid YAML;
2. exact approved path scopes;
3. `workflow_dispatch` remains;
4. schedule `12 * * * *` remains unless a separate schedule decision is approved;
5. deterministic fixture path still runs on pull requests;
6. live path remains limited to non-pull-request events;
7. focused V3.3 test passes;
8. canonical `tests.yml` suite passes on the same commit;
9. state path, cache keys, commands, reports, artifact name, artifact paths, and failure behavior remain unchanged;
10. no production code or financial formula changes.

## 13. Manual verification gates

The following are not established by tracked repository files:

- branch-protection required checks;
- external report or artifact consumers;
- operational dependence on hourly snapshots;
- source-access policies and safe polling cadence;
- hosted-cache retention and continuity across workflows;
- actual timing relationship between scheduled V3.3 and V3.2 runs.

They remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

## 14. Final Wave 3E decision

Wave 3E authorizes no workflow change.

The repository-supported next direction is:

```text
V3.3 remains the temporary Auksjonen ingestion owner.
Retain manual dispatch and minute-12 hourly schedule for now.
Define a later, separate path-scoping implementation PR.
Do not alter shared state or separate cache namespaces without a dedicated ownership decision.
```
