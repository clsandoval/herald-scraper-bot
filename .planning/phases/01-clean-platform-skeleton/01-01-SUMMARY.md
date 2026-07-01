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

requirements-completed: [PLAT-01, PLAT-02, PLAT-03]

# Metrics
duration: 25min
completed: 2026-07-01
---

# Phase 1 Plan 1: Clean Platform Skeleton — Purge Legacy Code + Scaffold daimon-core Summary

**Legacy Telegram/Lambda bot deleted, uv workspace + trimmed daimon-core package (db/config/models/health/logging/ids/errors + inert turn/ MA engine + clean skills/fetch) scaffolded and import-clean, and the leaked Telegram token scrubbed from all git history via git filter-repo + one-time force-push (token also revoked by the user via @BotFather).**

## Checkpoint Status: RESOLVED (human approved — Task 4 completed)

This plan reached **Task 3**, a `checkpoint:human-verify` task with `gate="blocking-human"`
gating the `git filter-repo` history scrub and the leaked-Telegram-token revocation
confirmation. The user (via the coordinator) explicitly **approved** all three gated
conditions: (1) `git-filter-repo` package legitimacy accepted, (2) the leaked Telegram
token was revoked via @BotFather, and (3) the destructive history rewrite + one-time
force-push was authorized. Task 4 then ran to completion.

**All four tasks are complete.** The token no longer appears anywhere in git history
(grep-count 0 across `git log --all -p`); `functions.py` is absent from all history;
the working tree is secret-clean; and the rewritten history was force-pushed to
`origin` (single remote, single `main` branch, no CI/CD webhook — safe per D-03).

## Performance

- **Duration:** ~25 min (tasks 1–4; a human-verify checkpoint interrupted between tasks 2 and 4)
- **Started:** 2026-07-01T11:40:00Z (approx, first file op)
- **Completed:** 2026-07-01T11:50:00Z (approx, post force-push)
- **Tasks:** 4 of 4 completed (Task 3 checkpoint approved by user, Task 4 executed)
- **Files modified:** 43 (37 in task 1, 5 in task 2, plus history rewrite in task 4)

## Accomplishments
- Legacy Telegram/Lambda/dead code (`bot.py`, `lambda_function.py`, `database.py`, `discord_bot.py`, `functions.py`, `constants.py`, `ability_ids.json`, `requirements.txt`, `text.out`) removed from the working tree via `git rm` — including `functions.py`, which carried the leaked Telegram token at (former) line 94.
- **Leaked Telegram token scrubbed from ALL git history** (Task 4): `git filter-repo --path functions.py --invert-paths` purged every historical blob of `functions.py`, then two `git filter-repo --replace-text` passes redacted the token from every remaining doc blob that quoted it. The FIRST `--replace-text` pass covered only the raw `NNNN:AAG...` form and missed a URL-encoded copy (`NNNN%3AAAG...`, `%3A` for `:`) inside a `TG_URL` example string in `.planning/codebase/CONCERNS.md:58` — see Deviation 4. A SECOND `--replace-text` pass covering BOTH forms purged it. Final verification: `git log --all -p | grep -c "<secret-fragment>"` == 0 (the token's secret auth fragment, form-agnostic), working-tree `grep -rn "<secret-fragment>"` across `*.md`/`*.py` returns nothing, and `functions.py` has 0 commits in history. `origin` was re-added and the rewritten history force-pushed (`git push origin --force --all`). Token also revoked via @BotFather (user action — the real fix; the scrub is defense-in-depth). NOTE: the bare public bot-ID number (no `:AAG...` secret) still appears in a few grep-command EXAMPLES in the planning docs (e.g. `grep -c '<botid>...'` in PLAN/RESEARCH verification instructions) — this is the non-sensitive public identifier, not the credential, and is intentionally left so the verification commands remain readable.
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

Each task was committed atomically. **NOTE: the Task 4 history rewrites (`git filter-repo`,
run three times total — one path-purge + two `--replace-text` passes) changed every commit
SHA on each run.** Current post-rewrite SHAs are listed below.

1. **Task 1: Delete legacy code and scaffold the uv workspace + daimon-core package (incl. inert turn/ + skills/)** - `c5b4ee3` (feat)
2. **Task 2: Trim config.py to Phase-1 sections + empty models Base, verify uv sync + import smoke (incl. turn/ + skills/)** - `867321a` (feat)
3. **Task 3: checkpoint:human-verify** — approved by user via coordinator (git-filter-repo legitimacy + token revocation + force-push authorization). No code commit.
4. **Task 4: Install git-filter-repo, scrub functions.py + token literals from history, force-push** - a history-rewriting operation (no working-tree content commit for the rewrite itself). Working-tree token redactions were committed before each `--replace-text` pass: `810036a` (raw literal in PLAN.md) and the CONCERNS.md URL-encoded-form redaction (folded into the second rewrite). Force-pushed via `git push origin --force --all`.

**Plan metadata commit:** committed after this SUMMARY + STATE.md/ROADMAP.md/REQUIREMENTS.md update.

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
- **Verification:** `git check-ignore -v packages/core/alembic/env.py` returns nothing (not ignored); `git add packages/core/alembic/env.py` succeeds; file appears in the Task 1 commit's `--stat`.
- **Committed in:** Task 1's commit (`c5b4ee3` current post-rewrite SHA)

**2. [Rule 1 - Bug] `.gitignore`'s `__pycache__/*` pattern didn't cover nested package `__pycache__` dirs**
- **Found during:** Task 2, after `uv run pytest` generated bytecode caches under `packages/core/daimon/core/__pycache__/`, `packages/core/daimon/core/turn/__pycache__/`, `packages/core/daimon/core/skills/__pycache__/`, and `tests/__pycache__/`
- **Issue:** `__pycache__/*` (no leading `/`, trailing `/*`) matches contents of `__pycache__` directories anchored only at repo root in this git version's glob evaluation — nested `__pycache__` dirs under `packages/` and `tests/` showed as untracked (`??`) in `git status` instead of being silently ignored, which would have polluted every subsequent commit with generated bytecode files across a now-multi-package repo.
- **Fix:** Changed the pattern from `__pycache__/*` to `__pycache__/` (matches any directory named `__pycache__` at any depth, ignoring its full contents).
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` no longer lists any `__pycache__` path anywhere in the tree as untracked after the fix.
- **Committed in:** Task 2's commit (`867321a` current post-rewrite SHA)

**3. [Rule 1 - Bug / Rule 2 - Security] Leaked token literal quoted verbatim in the planning docs would leave the secret in history after scrubbing `functions.py`**
- **Found during:** Task 4, after `git filter-repo --path functions.py --invert-paths` — the token grep still returned 2 hits.
- **Issue:** `01-01-PLAN.md` (and the historical `ROADMAP.md` blob) quoted the leaked token string verbatim — once as the "token to purge" reference and once inside the verify command itself. Purging only `functions.py` from history therefore did NOT fully remove the secret string; the plan's own verify criterion (`grep -c '<token>'` == 0 across all history) could not pass while those doc blobs remained.
- **Fix:** Redacted the raw literal from the working-tree `01-01-PLAN.md` (committed as `810036a`), then ran a `git filter-repo --replace-text` pass mapping the raw token literal to `REDACTED` across every historical blob.
- **Files modified:** `.planning/phases/01-clean-platform-skeleton/01-01-PLAN.md` (working tree) + historical blobs containing the raw literal (via `--replace-text`).
- **Verification:** raw-form `git log --all -p | grep -c '<token>'` == 0 after this pass. (Incomplete — see Deviation 4: a URL-encoded copy survived.)
- **Committed in:** `810036a` (working-tree redaction) + the first `--replace-text` history rewrite.

**4. [Rule 1 - Bug / Rule 2 - Security] URL-encoded copy of the token survived the first `--replace-text` pass (raw-form-only match)**
- **Found during:** Post-completion review flagged by the coordinator — the first scrub's `grep -c` used the raw `NNNN:AAG...` form and missed a URL-encoded copy.
- **Issue:** `.planning/codebase/CONCERNS.md:58` quoted the token in URL-encoded form (`%3A` in place of `:`) inside a `TG_URL = "https://api.telegram.org/bot<token>/sendMessage"` example. The first `--replace-text` replacements file only listed the raw `:`-delimited literal, so the `%3A` variant survived in both the working tree AND one historical blob. The initial "0 occurrences" claim was therefore wrong — it only checked the raw form.
- **Fix:** Redacted the URL-encoded token in the working-tree `CONCERNS.md` to `***REDACTED-REVOKED-TOKEN***` (committed before the rewrite), then ran a SECOND `git filter-repo --replace-text` pass whose replacements file covered BOTH forms — raw `NNNN:AAG...` and URL-encoded `NNNN%3AAAG...` — extracted programmatically from a historical blob (never typed) so both were purged from every historical blob. Re-added `origin` and force-pushed.
- **Files modified:** `.planning/codebase/CONCERNS.md` (working tree) + historical blobs (via `--replace-text`).
- **Verification (form-agnostic, the fix for the flawed first check):** `git log --all -p | grep -c "<secret-fragment>"` (the token's secret auth fragment, matches both forms) == **0**; working-tree `grep -rn "<secret-fragment>" . --include="*.md" --include="*.py"` (excluding `.git`) returns **nothing**; `functions.py` still has 0 commits in history. The bare public bot-ID number remains only in grep-command examples in the docs (non-sensitive, intentional).
- **Committed in:** working-tree redaction folded into the second `--replace-text` history rewrite; force-pushed via `git push origin --force --all`.

---

**Total deviations:** 4 auto-fixed (Rule 1/2/3 — blocking correctness + secret-hygiene issues, not scope creep)
**Impact on plan:** All four fixes were necessary: two `.gitignore` bugs blocked Task 1/2 from committing required files; the token-in-docs discoveries (raw form, then URL-encoded form) were required for the Task 4 scrub to actually remove the secret from all history. Deviation 4 also corrected a flawed verification (raw-form-only grep) — the scrub is now verified form-agnostically. No architectural changes, no scope creep.

## Issues Encountered
- The plan's `files_modified` frontmatter listed `download.html`, which does not exist in this repo's working tree (likely a stale reference from an earlier codebase snapshot in `.planning/codebase/`). `git rm download.html` failed with "did not match any files"; the file was simply skipped — no impact, as it was never present to begin with.
- A pre-existing tracked `__pycache__/` directory (5 stale `.pyc` files from the legacy `functions.py`/`env.py` bot) was removed as part of Task 1's cleanup — an intentional deletion consistent with "purge legacy code," documented here per the destructive-git-prohibition self-check.

## User Setup Required

All required user actions are DONE (approved via coordinator):

1. **Leaked Telegram token revoked** via @BotFather — confirmed by the user.
2. **`git-filter-repo` install approved** — installed dev-only (`pip install git-filter-repo`, v2.47.0, `~/.local/bin/git-filter-repo`), NOT added to any package dependency and NOT in the Docker image.
3. **One-time force-push authorized and executed** — `git push origin --force --all` completed (`9273735...f76f6ef main -> main (forced update)`); no tags to push.

**One residual operator note for plan 01-03 (deploy):** the Fly `DATABASE_URL` secret comes back as `postgres://...` and must be set as `DAIMON_DATABASE__URL` with the scheme rewritten to `postgresql+asyncpg://` (see RESEARCH Pitfall 2). Not this plan's concern; flagged for the deploy plan.

## Next Phase Readiness

**Ready for plan 01-02.** PLAT-01 (trimmed core + inert turn/skills, no legacy/dead files), PLAT-02 (secrets from env only, SecretStr, no literals in source), and PLAT-03 (leaked token revoked + scrubbed from history + legacy code removed) are all satisfied. The uv workspace + daimon-core skeleton is importable and test-clean. Plan 01-02 (minimal mention→pong Discord adapter, inert scheduler package, baseline migration, Dockerfile/fly.toml/entrypoint) builds directly on this. PLAT-04 (live Fly deploy + @bot→pong) is plan 01-03's bar.

**Force-push coordination note:** every commit SHA in the repo changed. Any other local clone of this repo (there are none known besides this working tree) is now divergent and must re-clone or hard-reset to the rewritten `origin/main`.

---
*Phase: 01-clean-platform-skeleton*
*Status: COMPLETE (all 4 tasks) — Task 3 checkpoint approved by user, Task 4 scrub + force-push executed*

## Self-Check: PASSED

All 25 claimed files verified present (`test -f`); current post-rewrite task
commit hashes (`c5b4ee3`, `867321a`) verified present in `git log --oneline --all`;
all 9 legacy files verified absent from the working tree; leaked token verified
absent from all git history **form-agnostically** — `git log --all -p | grep -c "<secret-fragment>"`
== 0 (matches both raw `:` and URL-encoded `%3A` forms) — and working-tree
`grep -rn "<secret-fragment>" . --include="*.md" --include="*.py"` (excluding `.git`)
returns nothing; `functions.py` verified absent from all history (0 commits);
import smoke + 4 config tests pass. (Corrects the prior self-check, which used a
raw-form-only grep and missed the URL-encoded copy in CONCERNS.md — Deviation 4.)
