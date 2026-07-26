# Project Status Patch Guide — Wave 2K

After this task-definition PR is accepted, update `docs/00_PROJECT_STATUS.md` with the following authoritative state:

```text
Wave 2J — READY_FOR_PATH_SCOPING
Wave 2K — NEXT_IMPLEMENTATION_TASK
```

Current implementation checkpoint:

```text
WAVE2K_V35_PATH_SCOPING_IMPLEMENTATION
```

Current task document:

```text
docs/OPERATOR_WORKFLOW_WAVE2K_v1.0.md
```

The implementation must modify only `.github/workflows/v3.5-opportunity-alert-review-queue.yml` by adding the four approved `pull_request.paths` entries. This guide changes no workflow or production behavior.