---
phase: 1
slug: clean-platform-skeleton
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-01
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (per daimon fork; confirm version from copied pyproject) |
| **Config file** | none yet — Wave 0 sets up `pyproject`/pytest for the trimmed workspace |
| **Quick run command** | `uv run pytest -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~10-30 seconds (thin skeleton) |

Note: Phase 1 is platform/deploy — much of its verification is deploy-time (Fly boot, migrations run, `@bot → pong`) rather than unit-testable. See Manual-Only Verifications.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite green + a successful `herald-scraper-bot-test` deploy
- **Max feedback latency:** 30 seconds (local); deploy checks are manual

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (filled by planner / nyquist auditor) | 01 | 1 | PLAT-01..04 | T-1-xx | secrets only from env | mixed | `uv run pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] pytest configured in the trimmed `uv` workspace
- [ ] `tests/test_config.py` — asserts config loads from env, no hardcoded secrets
- [ ] `tests/test_health.py` — health endpoint / bot connects (mockable)

*Deploy-time checks (Fly boot, migrations, pong) are manual — see below.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Deploy to `herald-scraper-bot-test` succeeds | PLAT-04 | Requires live Fly deploy | `fly deploy -a herald-scraper-bot-test`; app boots |
| Alembic migrations run on release | PLAT-04 | Fly release_command | Check release logs show `alembic upgrade head` |
| `@bot → pong` in test server | PLAT-01 (health) | Requires live Discord + test server | Mention the bot in the herald replays test server; expect `pong` |
| Leaked token purged from history | PLAT-03 | Git-history assertion | `git log -p -- functions.py \| grep -c <token-fragment>` == 0 |
| No secrets in source | PLAT-02 | Repo scan | `git grep -nE '<secret patterns>'` returns nothing |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (or documented manual deploy checks)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
