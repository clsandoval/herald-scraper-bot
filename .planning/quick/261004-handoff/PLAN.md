# Collaborator handoff

Authorized 2026-10-04: broad local restructuring; preserve the slow scheduled mode and private `/heralds` menu. Work in an isolated branch; do not touch the live one-shot worker or its artifacts.

1. Promote maintained ingest/board/render code to `herald/`, keep compatibility entrypoints, document historical experiments and experimental daimon workspace.
2. Fix cold-start, empty-result, stale-match and pagination menu failures using synthetic offline fixtures.
3. Replace stale onboarding with current architecture, setup, configuration, operation and collaborator handoff docs. Explicitly distinguish the legacy scheduled report policy from current board ingest.
4. Run offline checks and metadata-only tracked-secret inspection. No network services, Discord writes, paid calls, deploys or pushes.

Workflow note: attempted installed GSD quick initialization, but `gsd-sdk` is absent. Carlos explicitly authorized autonomous repository restructuring; this local plan and summary preserve tracking without another agent launch.
