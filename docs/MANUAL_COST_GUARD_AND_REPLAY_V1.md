# Manual Cost Guard and Artifact Replay V1

## Why this exists

A successful GitHub Actions run only proves the workflow executed. It must not require a new paid Brave scan every time we debug Math V1, data propagation, or regression behavior.

The project already isolates paid Targeted Enrichment behind eligibility gates. This guard extends the same cost discipline to manual diagnostic runs of the core discovery paths.

## Frozen rule

- `schedule` is the production discovery path. Paid Brave-backed discovery remains available there.
- `workflow_dispatch` is a diagnostic/manual path and is **zero-cost Brave by default**.
- A manual runner may opt into paid Brave only by explicitly setting `OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL=true` in its environment.
- Pull-request CI does not run the live operator job and therefore remains zero-cost.

## Protected paths

The manual guard covers:

1. the shared `run_market_clothing_inventory_discovery.py` entry point used by the SE/DE Brave-backed direct-source scans;
2. the Brave early-signal radar wrapper used by the intelligence feed.

When the radar is guarded it emits a structured diagnostic result:

- `status = SKIPPED_COST_GUARD`
- `requests_made = 0`
- `signal_count = 0`
- `block_reason = MANUAL_WORKFLOW_PAID_BRAVE_BLOCKED`

This is intentionally different from pretending the provider succeeded with zero findings.

## Math V1 / regression rule

Do **not** launch a new paid market scan merely to re-evaluate deterministic code.

Use the last trusted checkpoint artifact as the replay source. For the current Math V1 investigation, Run #191 is the frozen paid evidence bundle. Its artifact already contains:

- `multi-market-daily-operator-checkpoint/unified-market-cases.json`
- `multi-market-daily-operator-checkpoint/mathematical-logic-shadow-v1.json`
- the NO/SE/DE source evidence tree
- IT/NL/FR sidecars

Math/regression work should reuse that evidence until a code change has passed tests. Only then should one intentional production validation run be considered.

## Safety

This guard changes no commercial ranking, Top-5 selection, verification rule, source scope, lifecycle decision, or automatic action. It only prevents accidental paid Brave requests during manual diagnostics.
