---
phase: 01-clean-platform-skeleton
plan: 01
subsystem: infra
tags: [uv, pydantic-settings, sqlalchemy, alembic, anthropic-managed-agents, daimon-fork]

# Dependency graph
requires: []
provides:
  - Legacy Telegram/Lambda/dead code removed from the working tree (bot.py, lambda_function.py, database.py, discord_bot.py, functions.py, constants.py, ability_ids.json, requirements.txt, text.out)
  - uv workspace root (pyproject.toml) declaring packages/core + packages/adapters/*
  - daimon-core package: db.py, health.py, logging_setup.py, ids.py, errors.py, ma.py copied verbatim
  - Inert turn/ MA engine (driver/gating/lifecycle/reducers/render/state) + inert clean skills/ subset (fetch.py only)
  - Trimmed pydantic-settings config.py (database/anthropic/discord/log only, SecretStr on tokens)
  - Empty declarative Base (_models.py) — zero domain tables
  - Async Alembic env.py + alembic.ini + script.py.mako, empty versions/ dir
  - Passing import-smoke + config test suite (tests/test_config.py)
affects: [01-02, 01-03, all later phases building on daimon-core]

# Tech tracking
tech-stack:
  added: [uv workspace, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, structlog, anthropic SDK (Managed Agents beta), tenacity, httpx]
  patterns: ["construct-at-edge Settings (no module-level singleton)", "SecretStr on all token fields", "inert-but-present dependency copying (turn/ + skills/ importable, zero Phase-1 callers)"]

key-files:
  created:
    - pyproject.toml
    - packages/core/pyproject.toml
    - packages/core/daimon/core/config.py
    - packages/core/daimon/core/_models.py
    - packages/core/daimon/core/db.py
    - packages/core/daimon/core/health.py
    - packages/core/daimon/core/logging_setup.py
    - packages/core/daimon/core/ids.py
    - packages/core/daimon/core/errors.py
    - packages/core/daimon/core/ma.py
    - packages/core/daimon/core/turn/__init__.py
    - packages/core/daimon/core/turn/driver.py
    - packages/core/daimon/core/turn/gating.py
    - packages/core/daimon/core/turn/lifecycle.py
    - packages/core/daimon/core/turn/reducers.py
    - packages/core/daimon/core/turn/render.py
    - packages/core/daimon/core/turn/state.py
    - packages/core/daimon/core/skills/__init__.py
    - packages/core/daimon/core/skills/fetch.py
    - packages/core/alembic/env.py
    - packages/core/alembic/script.py.mako
    - alembic.ini
    - tests/test_config.py
    - uv.lock
  modified:
    - .gitignore

key-decisions:
  - "Workspace root pyproject.toml only lists packages/core as an existing member for now (packages/adapters/* declared in [tool.uv.workspace] but no adapter package exists yet — added in plan 01-02)"
  - "Dropped google-auth, PyJWT, cachetools, httpx-sse, pyyaml, croniter, cryptography, sentry-sdk from daimon-core's dependency list — none are imported by db/health/logging_setup/ids/errors/ma/turn/skills-fetch (verified by import smoke)"
  - "Fixed .gitignore: the stale bare `env.py` pattern was silently blocking packages/core/alembic/env.py (a required file); scoped to /env.py (repo-root only) and broadened __pycache__/* to __pycache__/ so nested package caches are also ignored"

patterns-established:
  - "Settings constructed via load_settings() at the process edge, never a module-level singleton"
  - "SecretStr on every credential field (bot_token, api_key) — repr/log safe by construction"
  - "Verbatim-copy-then-trim for daimon fork adoption: db/health/logging_setup/ids/errors/ma/turn/skills-fetch copied byte-for-byte; only config.py and _models.py are rewritten (trimmed sections / empty schema)"

requirements-completed: []  # PLAT-01/02/03 NOT yet complete — history scrub (task 4) still pending human checkpoint

# Metrics
duration: 20min (tasks 1-2 only; plan halted before task 4)
completed: 2026-07-01 (PARTIAL — see Checkpoint Status below)
---

# Phase 1 Plan 1: Clean Platform Skeleton — Purge Legacy Code + Scaffold daimon-core Summary

**Legacy Telegram/Lambda bot deleted, uv workspace + trimmed daimon-core package (db/config/models/health/logging/ids/errors + inert turn/ MA engine + clean skills/fetch) scaffolded and import-clean — HALTED at the git-filter-repo human-verify checkpoint before any history rewrite or force-push.**

## Checkpoint Status: HALTED (human-verify required before Task 4)

This plan reached **Task 3**, a `checkpoint:human-verify` task with `gate="blocking-human"`
gating the `git filter-repo` history scrub and the leaked-Telegram-token revocation
confirmation. Per protocol, this checkpoint type is **never auto-approved** — even
though this session's `workflow.auto_advance` config is `false` (auto-mode was not
active anyway), a `blocking-human` gate on a destructive, irreversible operation
(`git filter-repo` rewrite + `git push --force`) always requires an explicit human
decision before proceeding.

**Tasks 1 and 2 are complete and committed.** Task 4 (install git-filter-repo, scrub
`functions.py` from all git history, force-push) has NOT run. No history rewrite, no
force-push, no `pip install git-filter-repo` has occurred.

## Performance

- **Duration:** ~20 min (tasks 1–2)
- **Started:** 2026-07-01T11:40:00Z (approx, first file op)
- **Completed:** N/A — plan not finished; halted 2026-07-01T11:44:25Z
- **Tasks:** 2 of 4 completed (Task 3 halted, Task 4 not started)
- **Files modified:** 42 (37 in task 1's commit, 5 in task 2's commit)

## Accomplishments
- Legacy Telegram/Lambda/dead code (`bot.py`, `lambda_function.py`, `database.py`, `discord_bot.py`, `functions.py`, `constants.py`, `ability_ids.json`, `requirements.txt`, `text.out`) removed from the working tree via `git rm` — including `functions.py`, which carries the leaked Telegram token at (former) line 94. The token is STILL in git history at this point; that scrub is Task 4, not yet run.
- uv workspace root (`pyproject.toml`) + `daimon-core` package (`packages/core/pyproject.toml`) scaffolded; `uv sync` resolves cleanly and produced `uv.lock`.
- Copied verbatim from the daimon fork: `db.py`, `health.py`, `logging_setup.py`, `ids.py`, `errors.py` (full error taxonomy, not stubbed — `TurnError`/`DefaultsError`/`SpecError` are hard deps of `turn/`/`ma.py`/`skills/fetch.py`), `ma.py`.
- Copied the entire `turn/` MA engine (7 files: `__init__.py`, `driver.py`, `gating.py`, `lifecycle.py`, `reducers.py`, `render.py`, `state.py`) verbatim — INERT, no Phase-1 caller, wired in a later phase per D-09.
- Copied the clean `skills/` subset (`__init__.py` + `fetch.py` only) — `discover.py`/`sync.py`/`pipeline.py` deliberately NOT copied (hard deps on excluded `daimon.core.defaults.*` machinery per D-04).
- Wrote a trimmed `config.py`: only `database`/`anthropic`/`discord`/`log` sections survive; `bot_token` and `api_key` stay `SecretStr` (D-11 — no plaintext secret leakage via repr/log).
- Wrote an empty `_models.py` (`Base` only, zero tables) — Phase 1 has no DATA-* requirements.
- Copied `alembic.ini`, `packages/core/alembic/env.py`, `script.py.mako` verbatim; created empty `packages/core/alembic/versions/` with `.gitkeep`. No baseline migration yet (that's plan 01-02's job).
- `uv run python -c "import daimon.core.turn; import daimon.core.skills; ..."` succeeds — the inert engine's dependency graph (ma.py, errors.py, tenacity, httpx) is self-consistent.
- `tests/test_config.py` — 4 tests, all passing: import smoke, config-from-env with `SecretStr` repr protection, empty `Base.metadata`, and turn/skills inert-import smoke.
- Fixed a pre-existing `.gitignore` bug (Rule 3 — blocking issue): a bare `env.py` pattern was silently excluding `packages/core/alembic/env.py`, one of this plan's required deliverables. Scoped to `/env.py` (repo-root only) and broadened `__pycache__/*` to `__pycache__/` so nested package/test bytecode caches are also ignored (previously only the repo-root `__pycache__` was covered).

## Task Commits

Each completed task was committed atomically:

1. **Task 1: Delete legacy code and scaffold the uv workspace + daimon-core package (incl. inert turn/ + skills/)** - `a6b38ae` (feat)
2. **Task 2: Trim config.py to Phase-1 sections + empty models Base, verify uv sync + import smoke (incl. turn/ + skills/)** - `89fa79e` (feat)

**Task 3 (checkpoint:human-verify, gate="blocking-human"): NOT RESOLVED — plan halted here.**
**Task 4 (git-filter-repo scrub + force-push): NOT STARTED — blocked by Task 3.**

**Plan metadata commit:** pending (this SUMMARY + STATE.md/ROADMAP.md update, committed separately below)

## Files Created/Modified
- `pyproject.toml` - uv workspace root, `packages/core` + `packages/adapters/*` members
- `packages/core/pyproject.toml` - `daimon-core` package, trimmed dependency list (dropped google-auth/PyJWT/cachetools/httpx-sse/pyyaml/croniter/cryptography/sentry-sdk — unused by the copied subset)
- `packages/core/daimon/core/{db,health,logging_setup,ids,errors,ma}.py` - copied verbatim from daimon fork
- `packages/core/daimon/core/turn/{__init__,driver,gating,lifecycle,reducers,render,state}.py` - copied verbatim, inert MA turn engine
- `packages/core/daimon/core/skills/{__init__,fetch}.py` - copied verbatim, clean subset only
- `packages/core/daimon/core/config.py` - trimmed `Settings` (database/anthropic/discord/log)
- `packages/core/daimon/core/_models.py` - empty declarative `Base`
- `packages/core/alembic/{env.py,script.py.mako}`, `alembic.ini` - copied verbatim, async Alembic wiring
- `packages/core/alembic/versions/.gitkeep` - empty migrations dir placeholder
- `tests/test_config.py` - import smoke + config-from-env + SecretStr-repr + empty-Base + turn/skills-import tests
- `uv.lock` - generated by `uv sync`
- `.gitignore` - fixed stale `env.py` pattern (Rule 3 auto-fix, blocking)
- Deleted: `bot.py`, `lambda_function.py`, `database.py`, `discord_bot.py`, `functions.py`, `constants.py`, `ability_ids.json`, `requirements.txt`, `text.out`

## Decisions Made
- Workspace root's `[tool.uv.workspace]` lists `packages/adapters/*` even though no adapter package exists yet — matches the daimon fork's shape and avoids a second edit in plan 01-02 when the Discord adapter package is added.
- Dependency trimming for `packages/core/pyproject.toml`: kept only what the copied files actually import (verified via `uv run python -c "import ..."`), dropping `google-auth`, `PyJWT`, `cachetools`, `httpx-sse`, `pyyaml`, `croniter`, `cryptography`, `sentry-sdk` from the fork's full list — none of `db.py`/`health.py`/`logging_setup.py`/`ids.py`/`errors.py`/`ma.py`/`turn/*`/`skills/fetch.py` import them.
- `.gitignore` fix folded into task 2's commit (task 3 checkpoint intervened before a dedicated fix commit was warranted) — documented here for traceability.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] `.gitignore`'s bare `env.py` pattern silently excluded `packages/core/alembic/env.py`**
- **Found during:** Task 1, staging `packages/core/alembic/env.py` for commit
- **Issue:** The repo's pre-existing `.gitignore` had a bare `env.py` line (intended to ignore a local dev script from the old flat-file bot layout). Because git ignore patterns without a leading `/` match at any depth, this silently blocked `packages/core/alembic/env.py` — a required Task 1 deliverable — from being tracked at all. `git add` on that specific path failed with "The following paths are ignored."
- **Fix:** Scoped the pattern to `/env.py` (repo-root only, preserving original intent for the legacy dev script which no longer exists anyway) so the alembic `env.py` is trackable.
- **Files modified:** `.gitignore`
- **Verification:** `git check-ignore -v packages/core/alembic/env.py` returns nothing (not ignored); `git add packages/core/alembic/env.py` succeeds; file appears in `git show a6b38ae --stat`.
- **Committed in:** `a6b38ae` (part of Task 1's commit)

**2. [Rule 1 - Bug] `.gitignore`'s `__pycache__/*` pattern didn't cover nested package `__pycache__` dirs**
- **Found during:** Task 2, after `uv run pytest` generated bytecode caches under `packages/core/daimon/core/__pycache__/`, `packages/core/daimon/core/turn/__pycache__/`, `packages/core/daimon/core/skills/__pycache__/`, and `tests/__pycache__/`
- **Issue:** `__pycache__/*` (no leading `/`, trailing `/*`) matches contents of `__pycache__` directories anchored only at repo root in this git version's glob evaluation — nested `__pycache__` dirs under `packages/` and `tests/` showed as untracked (`??`) in `git status` instead of being silently ignored, which would have polluted every subsequent commit with generated bytecode files across a now-multi-package repo.
- **Fix:** Changed the pattern from `__pycache__/*` to `__pycache__/` (matches any directory named `__pycache__` at any depth, ignoring its full contents).
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` no longer lists any `__pycache__` path anywhere in the tree as untracked after the fix.
- **Committed in:** `89fa79e` (part of Task 2's commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1/3 — blocking correctness issues in `.gitignore`, not scope creep)
**Impact on plan:** Both fixes were necessary for Task 1/2 to complete at all (untrackable required file; repo hygiene). No architectural changes, no scope creep.

## Issues Encountered
- The plan's `files_modified` frontmatter listed `download.html`, which does not exist in this repo's working tree (likely a stale reference from an earlier codebase snapshot in `.planning/codebase/`). `git rm download.html` failed with "did not match any files"; the file was simply skipped — no impact, as it was never present to begin with.
- A pre-existing tracked `__pycache__/` directory (5 stale `.pyc` files from the legacy `functions.py`/`env.py` bot) was removed as part of Task 1's cleanup — an intentional deletion consistent with "purge legacy code," documented here per the destructive-git-prohibition self-check.

## User Setup Required

None yet for tasks 1–2. **Task 3/4 require direct user action before this plan can complete:**

1. **Confirm the leaked Telegram token is revoked** via @BotFather (D-11 user action) — this is the real fix; the history scrub in Task 4 is defense-in-depth on top of it.
2. **Approve the `git-filter-repo` install** (`pip install git-filter-repo`, dev-machine-only, not shipped in the Docker image) — legitimacy confirmed by research (github.com/newren/git-filter-repo, endorsed by GitHub's own "Removing sensitive data" docs, 7+ years maintained, packaged by Homebrew/Debian) but gated for explicit human sign-off per the package-legitimacy protocol (T-01-SC) since slopcheck was not run mechanically this session.
3. **Authorize the one-time force-push** (`git push origin --force --all && git push origin --force --tags`) that will follow the `git filter-repo --path functions.py --invert-paths --force` history rewrite — this rewrites every commit SHA in the repo. Confirmed safe in RESEARCH (single remote, single branch, no CI/CD git webhook, prod runs off its Fly machine not the repo) but still requires explicit authorization before any destructive/irreversible git history operation runs.

Resume with: `/gsd:execute-phase` (or equivalent continuation) once you've verified revocation and are ready to authorize the filter-repo + force-push.

## Next Phase Readiness

**NOT ready for plan 01-02 yet.** This plan's Task 4 (history scrub) must complete before PLAT-03 ("leaked token revoked and scrubbed") is satisfied. Tasks 1–2's deliverables (uv workspace, daimon-core skeleton, trimmed config, empty models, inert turn/+skills/) are solid and importable — plan 01-02 (Discord adapter + scheduler adapter + Dockerfile/fly.toml) can theoretically build on top of what exists now, but per the phase's own success criteria, PLAT-01/02/03 are only complete once Task 4 runs. Recommend resuming THIS plan (01-01) to finish Task 3/4 before starting 01-02.

---
*Phase: 01-clean-platform-skeleton*
*Status: HALTED at checkpoint (Task 3 of 4) — awaiting human verification*

## Self-Check: PASSED

All 25 claimed files verified present (`test -f`); both task commit hashes
(`a6b38ae`, `89fa79e`) verified present in `git log --oneline --all`; all 9
legacy files verified absent from the working tree.
