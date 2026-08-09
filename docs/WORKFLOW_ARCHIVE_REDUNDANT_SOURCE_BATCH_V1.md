# Workflow Archive — Redundant German Source Batch V1

The standalone GitHub Actions shells for Riegermann, VENTA, and Deutsche Pfandverwertung
are archived because their production execution already lives inside
`multi-market-daily-operator-checkpoint.yaml`.

Archived from `.github/workflows` to `docs/workflow-archive`:

- `riegermann-active-auctions-live.yaml`
- `venta-active-clothing-watch.yaml`
- `dpv-active-clothing-watch.yaml`

No collector or source implementation is deleted. The daily checkpoint continues to call:

- `scripts/run_riegermann_active_discovery.py`
- `scripts/run_venta_active_discovery.py`
- `scripts/run_dpv_active_discovery.py`

This removes three duplicate Actions entry points, including their pull-request-triggered live
source work, while preserving source logic, artifacts, tests, and Git history.

After this batch, `.github/workflows` contains five current workflows:

1. `multi-market-daily-operator-checkpoint.yaml` — automatic production owner.
2. `tests.yml` — canonical CI.
3. `one-opportunity-commercial-analysis.yaml` — explicit human analysis.
4. `sweden-clothing-inventory-live.yaml` — manual diagnostic for Swedish source modes.
5. `germany-clothing-inventory-live.yaml` — manual diagnostic for German source modes.

The Sweden and Germany diagnostic workflows are already manual-only. No OpenAI limits,
checkpoint cadence, markets, or automatic commercial actions change in this batch.
