---
phase: quick-260711-wqo
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - spikes/menu-v2/live_board.py
autonomous: true
requirements:
  - QUICK-TELEMETRY-01  # log ts + user (id + display name) per board interaction and per /heralds use
  - QUICK-HINT-01       # static hint line on public board main view pointing to /heralds
user_setup: []

must_haves:
  truths:
    - "Every board button/component click writes one row to the usage table (ts, user_id, user_name, action)"
    - "Every /heralds slash command invocation writes one usage row"
    - "Every Advanced modal submit writes one usage row"
    - "usage rows are queryable later from herald.db (who used what, when)"
    - "The public live board main view shows a static line telling users they can type /heralds for a private view"
  artifacts:
    - path: "spikes/menu-v2/live_board.py"
      provides: "usage table DDL, read-write conn with busy_timeout, log_usage helper, three call sites, hint text"
      contains: "CREATE TABLE IF NOT EXISTS usage"
  key_links:
    - from: "log_usage"
      to: "usage table in herald.db"
      via: "parameterized INSERT on read-write connection with PRAGMA busy_timeout=30000"
      pattern: "INSERT INTO usage"
    - from: "_update / AdvModal.on_submit / board_cmd"
      to: "log_usage"
      via: "direct call passing itx.user + action string"
      pattern: "log_usage\\("
---

<objective>
Add lightweight usage telemetry to the Herald board Discord bot and a static
hint line pointing users at the private `/heralds` view.

Every board interaction (button/component clicks in list & focus mode, the
Advanced modal submit) and every `/heralds` slash invocation records one row —
timestamp, Discord user id, display name, and a short action string — into a new
`usage` table in the shared herald.db. The table is raw and queryable ad hoc
later (who used what, when); no dashboards, no aggregation views.

Purpose: understand who actually uses the board and how, and gently advertise the
private view so viewers stop treating the public board as a scratch pad.
Output: edits to `spikes/menu-v2/live_board.py` only.

Ponytail mode: minimal diff, stdlib only. One table, one insert helper, three
call sites, one hint line.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@spikes/menu-v2/live_board.py

<interfaces>
<!-- Existing structures the executor edits. Do NOT re-explore the codebase. -->

live_board.py — existing state at module top:
- `_conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)`
  This connection is READ-ONLY — it cannot write the usage table. A separate
  read-write connection is required.
- `_conn.execute("PRAGMA busy_timeout=30000")` — the board and ingest loop share
  herald.db; any writer MUST set busy_timeout.
- `DB_PATH = os.environ.get("HERALD_DB", str(REPO / "herald.db"))` — already
  respects the prod HERALD_DB env var (/data/herald.db on Fly herald-board).
- Current imports: io, json, logging, pathlib, sqlite3, sys, discord, os, math,
  and an inline `import datetime`. There is NO `import time` yet — add it.

live_board.py — the three interaction entry points to instrument:
1. `async def _update(self, itx, **changes)` (~line 268) — central plumbing for
   ALL list/focus buttons and selects (sort, filter, open, prev/next page, dice,
   flip direction, back-to-board). Already logs `log.info(f"{itx.user} -> {changes}")`.
2. `AdvModal.on_submit(self, itx)` (~line 446) — Advanced search modal submit.
   Already logs `log.info(f"{itx.user} advanced: {adv}")`.
3. `board_cmd(itx)` (~line 488) — the `/heralds` slash command handler.
   Already logs `log.info(f"{itx.user} opened a private board")`.

live_board.py — the public board main view:
- `def _list(self)` (~line 341) builds the list-mode Container `c`. Header
  TextDisplay is added at ~line 351-352 (`## HERALD MATCH BOARD\n-# {total} matches...`).
  Nav row is added last via `c.add_item(self._nav_row(pages))` (~line 362).
- `def default_state()` (~line 162) returns the state dict used by BOTH the public
  board (on_ready) and the ephemeral board (board_cmd). The public board is created
  in `on_ready`; the ephemeral one in `board_cmd`.
- `render.check`/MAX_CHARS budget guard exists but is not called in the live list
  path — a single short hint line is safely within budget.

ingest.py schema conventions (match these exactly):
- `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=30000`
- `CREATE TABLE IF NOT EXISTS`, INTEGER epoch timestamps (e.g. `start_time INTEGER`)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: usage table + read-write conn + log_usage helper wired into all three entry points</name>
  <files>spikes/menu-v2/live_board.py</files>
  <action>
Add usage telemetry with a minimal diff, following ingest.py DB conventions.

1. Add `import time` to the stdlib import block near the top (it is currently missing).

2. After the existing read-only `_conn` setup block (right after the
   `_conn.execute("PRAGMA busy_timeout=30000")` line, ~line 41), add a SEPARATE
   read-WRITE connection dedicated to telemetry. The `mode=ro` `_conn` cannot write.
   - `_wconn = sqlite3.connect(DB_PATH, check_same_thread=False)`
   - Set `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=30000` on `_wconn`
     (the board and ingest loop share herald.db — a writer MUST wait, not die).
   - Create the table:
     `CREATE TABLE IF NOT EXISTS usage (ts INTEGER, user_id INTEGER, user_name TEXT, action TEXT)`
     using INTEGER epoch for ts to match ingest.py's timestamp convention.
   - `_wconn.commit()`.
   Add a one-line ponytail comment explaining why a second conn exists (the main
   conn is read-only; discord.py runs callbacks on one loop thread so a single
   shared write conn is fine).

3. Define a module-level helper `log_usage(user, action)` near the other helpers.
   It inserts one row using a PARAMETERIZED statement (never string-format user
   input into SQL):
   `_wconn.execute("INSERT INTO usage(ts, user_id, user_name, action) VALUES (?,?,?,?)", (int(time.time()), user.id, user.display_name, action))`
   then `_wconn.commit()`. Wrap the body in try/except that logs a warning on
   failure (`log.warning(f"usage log failed: {e}")`) — telemetry must never crash
   an interaction. This mirrors the codebase's "log and continue, don't raise" DB
   precedent (database.py insert_row, per CLAUDE.md).

4. Wire the three call sites (add ONE line each, alongside the existing log.info):
   - In `_update` (~line 274): `log_usage(itx.user, ",".join(changes) or "noop")`
     — the changes dict keys identify which control was used (sort, filters, page,
     match, mode, dir, spoiler), which is exactly "who used what".
   - In `AdvModal.on_submit` (~line 478): `log_usage(itx.user, "advanced")`.
   - In `board_cmd` (~line 495): `log_usage(itx.user, "slash:/heralds")`.

Do not add any aggregation, views, or query commands — raw table only, queried
ad hoc later. Do not touch render.py.
  </action>
  <verify>
    <automated>cd /home/clsandoval/cs/herald-scraper-bot && python -m py_compile spikes/menu-v2/live_board.py && grep -q "CREATE TABLE IF NOT EXISTS usage" spikes/menu-v2/live_board.py && grep -q "def log_usage" spikes/menu-v2/live_board.py && grep -q "INSERT INTO usage" spikes/menu-v2/live_board.py && [ "$(grep -v '^#' spikes/menu-v2/live_board.py | grep -c 'log_usage(')" -ge 4 ] && grep -q "^import time\|^import time$" spikes/menu-v2/live_board.py && echo PASS</automated>
    <automated>cd /home/clsandoval/cs/herald-scraper-bot && python -c "import sqlite3,time; c=sqlite3.connect(':memory:'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA busy_timeout=30000'); c.execute('CREATE TABLE IF NOT EXISTS usage (ts INTEGER, user_id INTEGER, user_name TEXT, action TEXT)'); c.execute('INSERT INTO usage(ts,user_id,user_name,action) VALUES (?,?,?,?)',(int(time.time()),123,'tester','slash:/heralds')); assert c.execute('SELECT count(*) FROM usage').fetchone()[0]==1; print('SQL_OK')"</automated>
  </verify>
  <done>
live_board.py compiles. A dedicated read-write `_wconn` with WAL + busy_timeout
creates the `usage(ts,user_id,user_name,action)` table on boot. `log_usage` is
defined and called from `_update`, `AdvModal.on_submit`, and `board_cmd`
(≥4 call sites total counting the definition-adjacent usage). The insert SQL is
valid and parameterized.
  </done>
</task>

<task type="auto">
  <name>Task 2: static /heralds hint line on the public board main view</name>
  <files>spikes/menu-v2/live_board.py</files>
  <action>
Add ONE static hint line to the public board's list view telling users they can
type `/heralds` for their own private, ephemeral board.

Placement (planner's choice): put it as a subtle footer inside the list-mode
Container, added right after the nav row in `_list()` (after
`c.add_item(self._nav_row(pages))`, ~line 362). Use a small-text TextDisplay:
`c.add_item(discord.ui.TextDisplay("-# 💡 Type `/heralds` anywhere to open your own private board only you can see."))`
(the `-#` prefix renders as Discord small/subtext, matching the existing header
subline style).

Gate it to the PUBLIC board only — showing "type /heralds" inside an already
private /heralds board is confusing. Since `default_state()` is shared by both
boards, distinguish them with a minimal flag rather than duplicating state:
- In `board_cmd` (~line 489), after `st = default_state()`, set `st["private"] = True`.
- In `_list`, only add the hint TextDisplay when `not self.st.get("private")`.
The public board (created in `on_ready`) leaves the flag unset/falsey, so it shows
the hint; the ephemeral board suppresses it.

Keep it to this one line. Do not add it to focus mode. Do not touch render.py.
  </action>
  <verify>
    <automated>cd /home/clsandoval/cs/herald-scraper-bot && python -m py_compile spikes/menu-v2/live_board.py && grep -q '/heralds' spikes/menu-v2/live_board.py && grep -q 'private board' spikes/menu-v2/live_board.py && grep -q 'st\["private"\] = True' spikes/menu-v2/live_board.py && grep -q 'self.st.get("private")' spikes/menu-v2/live_board.py && echo PASS</automated>
  </verify>
  <done>
The public board list view renders a single small-text footer line pointing to
`/heralds`. The ephemeral board (private=True) suppresses the line. File compiles.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Discord user → live_board callbacks | Untrusted user identity + interaction data crosses into telemetry writes |
| live_board → herald.db (shared with ingest loop) | Concurrent writer on a WAL SQLite file |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wqo-01 | Tampering | usage INSERT | mitigate | Parameterized INSERT only; user id/name/action bound as params, never string-formatted into SQL |
| T-wqo-02 | Denial of Service | shared herald.db writer | mitigate | `_wconn` sets `busy_timeout=30000` + WAL so it waits on the ingest writer instead of erroring; log_usage failures are caught and logged, never propagated to the interaction |
| T-wqo-03 | Information disclosure | usage table stores display names | accept | Personal single-server bot on a test/prod Herald server; display names are already public in the channel, no PII beyond what Discord surfaces |
| T-wqo-SC | Tampering | package installs | mitigate | No new packages — stdlib `time`/`sqlite3` only; nothing to install |
</threat_model>

<verification>
- `python -m py_compile spikes/menu-v2/live_board.py` succeeds.
- `usage` table DDL, `log_usage` helper, and ≥3 wired call sites present.
- Standalone SQLite smoke proves the CREATE + parameterized INSERT are valid.
- Public board shows the `/heralds` hint; ephemeral board suppresses it.
- No new imports beyond stdlib `time`; render.py untouched.
</verification>

<success_criteria>
- Board interactions, Advanced submits, and /heralds invocations each append one
  row to herald.db `usage(ts, user_id, user_name, action)`.
- Writes use a dedicated read-write connection with WAL + busy_timeout=30000 and
  never crash an interaction on failure.
- Public live board main view carries one static line pointing to /heralds; the
  private board does not.
- Diff is confined to spikes/menu-v2/live_board.py.
</success_criteria>

<output>
Create `.planning/quick/260711-wqo-add-usage-telemetry-timestamp-discord-us/260711-wqo-SUMMARY.md` when done.
</output>
