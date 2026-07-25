# Workflow Wave 2A Prerequisite Audit Report v1.0

**Scope:** documentation-only audit  
**Audit date:** 2026-07-25  
**Workflow behavior changed:** none

## Canonical quality-gate identity

Tracked repository evidence supports `.github/workflows/tests.yml` as the canonical full-regression candidate.

| Field | Verified value |
|---|---|
| Displayed name | `تشغيل الاختبارات` |
| Job identifier | `test` |
| Push coverage | `main` |
| Pull-request coverage | `main` |
| Python | `3.11` |
| Dependency installation | `pip install -r requirements.txt` |
| Full-suite command | `pytest -q > pytest-output.log 2>&1` |
| Artifact | `pytest-output` from `pytest-output.log` |
| Failure propagation | Capture pytest exit code, upload artifact with `always()`, then exit `1` when pytest failed |

Conclusion: `tests.yml` is the strongest canonical repository-wide quality gate and the only workflow explicitly designed to preserve the complete pytest log before propagating failure.

## Repository-settings status

| Fact | Status |
|---|---|
| `tests.yml` is required by branch protection | `MANUAL_VERIFICATION_REQUIRED` |
| Exact required check name in repository settings | `MANUAL_VERIFICATION_REQUIRED` |
| External automation depends on existing check names | `MANUAL_VERIFICATION_REQUIRED` |
| Removing duplicate regressions will not weaken merge protection | `MANUAL_VERIFICATION_REQUIRED` |

No branch-protection setting was changed.

## Pull-request workflows containing complete `pytest -q`

| Workflow | PR trigger | Status |
|---|---|---|
| `tests.yml` | PR to `main` | Canonical full regression |
| `discovery-v1-clothing-inventory.yml` | PR to `main` | Duplicated; first Wave 2 candidate |
| `discovery-v1.1-live-search.yml` | PR to `main` | Duplicated; first Wave 2 candidate |
| `discovery-v1.2-live-pilot.yml` | PR to `main` | Duplicated; later Discovery cleanup |
| `v2.8.2b-comparable-evidence-e2e-acceptance.yml` | PR | Duplicated; later Analysis cleanup |
| `v2.10-verified-financial-integration.yml` | Path-scoped PR | Preserve pending contract review |
| `v2.11-live-opportunity-validation.yml` | Path-scoped PR | Preserve pending contract review |
| `v30-multi-opportunity-ranking.yml` | PR | Duplicated; later ranking cleanup |
| `v3.6-multi-source-ingestion.yml` | PR | Duplicated; later ingestion cleanup |
| `v3.7-production-pilot.yml` | PR | Later Wave 3 task |

This table does not authorize removal of any command.

## Exact first implementation slice

### `discovery-v1-clothing-inventory.yml`

Preserve:

- `workflow_dispatch`;
- job `discovery-v1-acceptance`;
- Python `3.11` and existing `PYTHONPATH`;
- focused tests:
  `pytest tests/test_discovery_opportunity_maps.py tests/test_discovery_classifier.py -q`.

Proposed later PR scope:

```yaml
pull_request:
  branches: [main]
  paths:
    - "src/opportunity_engine/discovery/opportunity_maps.py"
    - "src/opportunity_engine/discovery/classifier.py"
    - "src/opportunity_engine/discovery/models.py"
    - "src/opportunity_engine/discovery/__init__.py"
    - "tests/test_discovery_opportunity_maps.py"
    - "tests/test_discovery_classifier.py"
    - ".github/workflows/discovery-v1-clothing-inventory.yml"
```

Remove the duplicated `Run full regression suite` step only after manual quality-gate confirmation.

### `discovery-v1.1-live-search.yml`

Preserve:

- `workflow_dispatch`;
- job `discovery-live-search`;
- Python `3.11` and existing `PYTHONPATH`;
- focused test:
  `pytest tests/test_discovery_v11_live_search.py -q`.

Proposed later PR scope:

```yaml
pull_request:
  branches: [main]
  paths:
    - "src/opportunity_engine/discovery/brave_search.py"
    - "src/opportunity_engine/discovery/live_search.py"
    - "src/opportunity_engine/discovery/search_provider.py"
    - "src/opportunity_engine/discovery/models.py"
    - "src/opportunity_engine/discovery/__init__.py"
    - "tests/test_discovery_v11_live_search.py"
    - ".github/workflows/discovery-v1.1-live-search.yml"
```

Remove the duplicated `Run complete regression suite` step only after manual quality-gate confirmation.

## Risk

- Audit PR: `LOW` — documentation only.
- Later implementation: `MEDIUM` — path filters may omit relevant changes, and removing full regressions may weaken merge protection if `tests.yml` is not required.

## Rollback for future implementation

1. Preserve the pre-change blob SHA for both workflow files.
2. Revert the implementation commit if focused workflows or `tests.yml` do not run as expected.
3. Restore `pytest -q` if the canonical gate is absent, optional, skipped, or not required.
4. Restore broad PR triggers if a relevant Discovery path is missing.
5. Keep manual dispatch throughout.

## Verification bundle before implementation merge

- manually verify branch protection and exact required check names;
- validate both YAML files;
- run both focused Discovery test sets;
- confirm `tests.yml` runs the complete suite on the same commit;
- confirm the `pytest-output` artifact is uploaded;
- confirm both manual dispatch triggers remain;
- inspect PR checks for missing or renamed required checks;
- confirm no production code, financial formula, domain, source adapter, purchase, bid, or contact behavior changed.

## Conclusion

Tracked-file evidence defines an exact and reversible first Wave 2 implementation slice. It does **not** yet authorize removing duplicated full regressions because branch-protection and required-check settings remain `MANUAL_VERIFICATION_REQUIRED`.

No file under `.github/workflows/` was modified during this audit.