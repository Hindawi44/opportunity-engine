# Workflow Archive — Country Diagnostic Pilots V1

The standalone Sweden and Germany diagnostic GitHub Actions workflows are archived because production discovery for both markets already runs inside `multi-market-daily-operator-checkpoint.yaml`.

Archived from `.github/workflows` to `docs/workflow-archive`:

- `sweden-clothing-inventory-live.yaml`
- `germany-clothing-inventory-live.yaml`

No collector, verifier, provider, query pack, market, Exact-Lot rule, SQLite continuity logic, or source implementation is deleted. The archived files remain available for historical reference and can be restored deliberately if a dedicated manual diagnostic entry point is needed again.

After this cleanup, the active `.github/workflows` directory contains only:

1. `multi-market-daily-operator-checkpoint.yaml` — production six-market checkpoint.
2. `tests.yml` — canonical CI.
3. `one-opportunity-commercial-analysis.yaml` — explicit opportunity analysis.
4. `mind-forge-live-research-launcher.yaml` — current MIND FORGE launcher tied to the checkpoint.

This cleanup changes only GitHub Actions entry-point clutter. It does not change the fixed project domains, unified search runtime, markets, search budgets, qualification rules, or automatic commercial-action policy.
