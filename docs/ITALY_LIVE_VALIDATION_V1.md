# ITALY LIVE VALIDATION V1

## Purpose

Run the newly merged `ITALY_MARKET_DISCOVERY_V1` against the live public web once from an existing GitHub Actions workflow before any Italy persistence, follow-up memory, exact-lot verification, logistics, or Top-5 integration is added.

## Workflow reuse

The repository intentionally stays at five GitHub Actions workflow files. The existing `.github/workflows/tests.yml` gains a bounded `italy-market-discovery-live` job instead of adding a sixth workflow.

The live job runs only on a push to `main` whose head commit message contains `Italy`. This makes the first validation immediate after the Italy wiring PR is merged without turning every repository push into a market scan. Recurring daily Italy execution is a later decision after the live artifact is reviewed.

## Live contract

The job:

1. installs the existing project dependencies;
2. runs `tests/test_italy_market_discovery_v1.py`;
3. runs all seven bounded Italy discovery intents through `scripts/build_italy_market_discovery.py`;
4. uses the existing `BRAVE_SEARCH_API_KEY` secret;
5. writes `artifacts/italy-market-discovery/italy-market-discovery.json`;
6. uploads the artifact as `italy-market-discovery-v1` for inspection.

## Decision boundary

This step measures discovery yield only. It does not add Italy to the canonical NO/SE/DE checkpoint market coverage and does not persist or promote any Italy result.

No automatic contact, bid, reservation, purchase, or payment is introduced.
