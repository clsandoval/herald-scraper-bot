"""Bounded, reporter-owned reference data for experimental build evidence.

Only already-fetched eligible reports enter this cache. No account IDs, raw
matches, menu database, network calls, or eligibility policy live here. A pass
fits a frozen reference once per patch; later targets are held out, not silently
subtracted from counts they never entered. Stored delivery specs remain immutable.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import math
from pathlib import Path
import re

from . import novelty, report_signals

RETENTION_DAYS = 30
MAX_MATCHES = 5000
MAX_ROW_BYTES = 32768
MAX_PURCHASES = 64
MIN_HERO_BUILDS = 30
MIN_MODE_BUILDS = 30
MIN_POSITION_BUILDS = 20
EXCLUDED_SKILL_MODES = frozenset({"SINGLE_DRAFT", "RANDOM_DRAFT"})
POPULATION = "eligible long-Herald scheduled reports"
_ASSETS = Path(__file__).parent / "assets"
_ITEM_DATA = (_ASSETS / "items.json").read_bytes()
ITEM_FAMILIES = {v["id"]: v.get("dname") or str(v["id"])
                 for v in json.loads(_ITEM_DATA).values() if (v.get("cost") or 0) >= 1000}
VERSION = "report-build-v1-" + hashlib.sha256(
    _ITEM_DATA + (_ASSETS / "ability_ids.json").read_bytes()).hexdigest()[:12]


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _unscored(reason, **support):
    return {"status": "unscored", "reason": reason, "score": None, "support": support,
            "receipts": []}


def compact_match(raw, duration):
    """Validate and retain only cheap purchases and first 12 observed skill picks.

    Absent/malformed/oversized logs are unavailable, never an observed zero.
    Bound the work even for a malformed giant provider response.
    """
    mode = raw.get("gameMode")
    if not isinstance(mode, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", mode):
        mode = None
    players = []
    for p in raw.get("players", [])[:10]:
        hero = p.get("heroId") if _integer(p.get("heroId")) else None
        events = p.get("abilities")
        skills = report_signals._skill_ids(p) if isinstance(events, list) and len(events) <= 128 else None
        stats = p.get("stats") if isinstance(p.get("stats"), dict) else {}
        events = stats.get("itemPurchases")
        purchases = None
        if isinstance(events, list) and len(events) <= 512:
            if all(isinstance(e, dict) and _integer(e.get("itemId"))
                   and _number(e.get("time")) and -120 <= e["time"] <= duration
                   for e in events):
                purchases = [{"itemId": e["itemId"], "time": e["time"]}
                             for e in events if e["itemId"] in ITEM_FAMILIES and e["time"] > 0]
                if len(purchases) > MAX_PURCHASES:
                    purchases = None
        players.append({"heroId": hero,
                        "abilities": [{"abilityId": a, "isTalent": False}
                                      for a in (skills or [])[:12]],
                        "stats": {"itemPurchases": purchases or []},
                        "items_available": purchases is not None,
                        "skills_available": skills is not None})
    return {"gameMode": mode, "players": players}


class ReferenceStore:
    """Small SQLite cache using the reporter connection, never the menu archive."""

    def __init__(self, conn):
        self.conn = conn
        conn.execute("""CREATE TABLE IF NOT EXISTS report_builds (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL UNIQUE, start_time INTEGER NOT NULL,
            patch INTEGER NOT NULL, version TEXT NOT NULL, data TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS report_builds_patch ON report_builds(version, patch, seq)")
        conn.execute("CREATE INDEX IF NOT EXISTS report_builds_age ON report_builds(start_time, match_id)")
        conn.commit()
        self._models = OrderedDict()
        self._snapshot_seq = None
        self._now = None

    def begin_pass(self, now):
        """Prune compact references only, and freeze membership for this pass."""
        self._now = int(now)
        with self.conn:
            self.conn.execute("DELETE FROM report_builds WHERE start_time < ? OR version != ?",
                              (self._now - RETENTION_DAYS * 86400, VERSION))
            self._cap()
        self._snapshot_seq = self.conn.execute("SELECT coalesce(max(seq),0) FROM report_builds").fetchone()[0]
        # SQLite's bounded TEMP snapshot keeps late-patch/LRU fits stable even
        # when newly observed matches evict old records from the rolling cache.
        self.conn.execute("DROP TABLE IF EXISTS temp.report_builds_snapshot")
        self.conn.execute("CREATE TEMP TABLE report_builds_snapshot AS SELECT * FROM report_builds")
        self.conn.execute("CREATE INDEX temp.report_builds_snapshot_patch ON report_builds_snapshot(version,patch,seq)")
        self._models.clear()

    def _cap(self):
        self.conn.execute("DELETE FROM report_builds WHERE seq IN (SELECT seq FROM report_builds "
                          "ORDER BY start_time DESC, match_id DESC LIMIT -1 OFFSET ?)", (MAX_MATCHES,))

    def _reference(self, patch):
        if patch in self._models:
            self._models.move_to_end(patch)
            return self._models[patch]
        params = (VERSION, patch, self._snapshot_seq)
        where = "version=? AND patch=? AND seq<=?"

        def matches():
            for data, in self.conn.execute(f"SELECT data FROM report_builds_snapshot WHERE {where} ORDER BY seq", params):
                match = json.loads(data)
                match["players"] = [p for p in match["players"] if _integer(p.get("heroId"))]
                yield match

        def skills():
            return (m for m in matches() if m.get("gameMode")
                    and m["gameMode"] not in EXCLUDED_SKILL_MODES)

        rows = self.conn.execute(
            f"SELECT match_id, seq, start_time FROM report_builds_snapshot WHERE {where} ORDER BY seq", params).fetchall()
        ids = {row[0] for row in rows}
        starts = [row[2] for row in rows]
        provenance = {"population": POPULATION, "version": VERSION, "patch": patch,
                      "matches": len(rows), "from": min(starts) if starts else None,
                      "through": max(starts) if starts else None,
                      "snapshot": f"{VERSION}:{patch}:{self._snapshot_seq}:{self._now}",
                      "retention_days": RETENTION_DAYS, "max_matches": MAX_MATCHES,
                      "item_method": "hero-relative purchase PMI; top 3 distinct item families",
                      "skill_method": "hero/mode/position surprisal; first 12 picks; top 3 distinct abilities"}
        reference = (novelty.ItemCorpus.fit(matches, ITEM_FAMILIES),
                     novelty.SkillCorpus.fit(skills), ids, provenance)
        self._models[patch] = reference
        if len(self._models) > 2:
            self._models.popitem(last=False)
        return reference

    def observe_and_score(self, candidate, raw, opendota):
        """Score against the frozen reference, then keep this eligible build once.

        Caller owns eligibility. Old reports aren't fetched again for warm-up;
        receipt JSON isn't rescored and previously sent messages aren't edited.
        """
        if self._snapshot_seq is None:
            self.begin_pass(candidate["start_time"])
        match = compact_match(raw, candidate["duration"])
        patch = opendota.get("patch")
        if not _integer(patch):
            return unavailable(match, "OpenDota patch unavailable")
        items, skills, ids, provenance = self._reference(patch)
        included = candidate["match_id"] in ids
        data = json.dumps(match, separators=(",", ":"), allow_nan=False)
        if included:
            old = self.conn.execute("SELECT data FROM report_builds_snapshot WHERE match_id=?",
                                    (candidate["match_id"],)).fetchone()[0]
            if json.loads(old) != match:
                result = unavailable(match, "retained target changed; reference incompatible")
                result["reference"] = {**provenance, "target_in_reference": None,
                                       "game_mode": match["gameMode"]}
                return result
        result = {"reference": {**provenance, "target_in_reference": included,
                                "game_mode": match["gameMode"]}, "items": {}, "skills": {}}
        for index, player in enumerate(match["players"]):
            hero = player["heroId"]
            item_support = max(0, items.hero_builds[hero] - int(included and
                bool(player["stats"]["itemPurchases"])))
            mode = match["gameMode"]
            if not _integer(hero):
                result["items"][index] = _unscored("hero unavailable")
                result["skills"][index] = _unscored("hero unavailable")
                continue
            skill_support = max(0, skills.mode_builds[(hero, mode)] - int(included and
                len([e for e in player["abilities"] if e["abilityId"] in skills.pool.get(hero, ())]) >= 6))
            item_result = _unscored("item reference warming up", hero_builds=item_support,
                                    minimum=MIN_HERO_BUILDS)
            if not player["items_available"]:
                item_result = _unscored("purchase log unavailable")
            elif not player["stats"]["itemPurchases"]:
                item_result = _unscored("no eligible purchase evidence")
            elif item_support >= MIN_HERO_BUILDS:
                if any(not items.gcount[e["itemId"]] for e in player["stats"]["itemPurchases"]):
                    item_result = _unscored("item absent from reference", hero_builds=item_support)
                else:
                    scored = items.score_player(player, target_in_reference=included)
                    item_result = {"status": "scored", "score": round(scored.score, 2),
                        "support": {"hero_builds": item_support, "purchases": items.gtot},
                        "receipts": [{"item_id": r.item_id, "family": r.family,
                                      "minute": int(r.minute), "score": round(r.score, 2)}
                                     for r in scored.items]}
            skill_result = _unscored("skill reference warming up", hero_mode_builds=skill_support,
                                     minimum=MIN_MODE_BUILDS)
            picks = [e["abilityId"] for e in player["abilities"]]
            if not player["skills_available"]:
                skill_result = _unscored("skill log unavailable")
            elif not mode:
                skill_result = _unscored("game mode unavailable")
            elif mode in EXCLUDED_SKILL_MODES:
                skill_result = _unscored("unsupported sparse game mode")
            elif len(picks) < 6:
                skill_result = _unscored("fewer than 6 observed skill picks")
            elif skill_support >= MIN_MODE_BUILDS:
                if any(a not in skills.pool.get(hero, ()) for a in picks):
                    skill_result = _unscored("ability outside reference hero pool",
                                             hero_mode_builds=skill_support)
                else:
                    floor = min(skills.tot[(hero, mode, i)] - int(included) for i in range(len(picks)))
                    if floor < MIN_POSITION_BUILDS:
                        skill_result = _unscored("skill position reference warming up",
                            hero_mode_builds=skill_support, position_builds=floor,
                            minimum=MIN_POSITION_BUILDS)
                    else:
                        scored = skills.score_player(player, mode, target_in_reference=included)
                        if scored is not None:
                            skill_result = {"status": "scored", "score": round(scored.score, 2),
                                "support": {"hero_mode_builds": skill_support, "position_builds": floor},
                                "receipts": [{"ability_id": r.ability_id, "pick": r.original_pick,
                                    "model_pick": r.pick, "score": round(r.score, 2)} for r in scored.picks],
                                "picks": picks}
            result["items"][index] = item_result
            result["skills"][index] = skill_result
        if (len(data.encode()) <= MAX_ROW_BYTES and candidate["start_time"] >=
                self._now - RETENTION_DAYS * 86400):
            with self.conn:
                self.conn.execute("INSERT OR IGNORE INTO report_builds "
                    "(match_id,start_time,patch,version,data) VALUES (?,?,?,?,?)",
                    (candidate["match_id"], candidate["start_time"], patch, VERSION, data))
                self._cap()
        return result


def unavailable(match, reason="reference unavailable"):
    return {"reference": {"population": POPULATION, "version": VERSION, "patch": None,
                          "matches": 0, "game_mode": match.get("gameMode")},
            **{kind: {i: _unscored(reason) for i, _ in enumerate(match.get("players", []))}
               for kind in ("items", "skills")}}


def best_player(evidence, kind):
    """Choose a preview by actual evidence, not raw team/player order."""
    scored = [(entry["score"], index) for index, entry in evidence.get(kind, {}).items()
              if entry.get("status") == "scored" and entry.get("receipts")]
    return max(scored, key=lambda pair: (pair[0], -pair[1]))[1] if scored else None


def evidence_text(evidence, kind, index, hero, *, limit=230):
    """A bounded concrete receipt, with explicit unscored support on cold starts."""
    from . import render
    entry = evidence.get(kind, {}).get(index) or _unscored("reference unavailable")
    if entry["status"] != "scored":
        support = entry.get("support", {})
        count = support.get("hero_mode_builds", support.get("hero_builds"))
        suffix = f" ({count}/{support['minimum']} builds)" if count is not None and support.get("minimum") else ""
        return render.clip("Unscored: " + entry["reason"] + suffix, limit)
    receipts = entry.get("receipts", [])
    if kind == "items":
        details = [f"{r['family']} @{r['minute']}m ({r['score']:.1f})" for r in receipts[:2]]
        title = f"PMI {entry['score']:.1f}"
        support = f"n={entry['support']['hero_builds']} hero builds"
    else:
        details = [f"pick {r['pick']} {report_signals.ability_name(r['ability_id'], hero)} ({r['score']:.1f})"
                   for r in receipts[:2]]
        title = f"Surprisal {entry['score']:.1f}"
        support = f"n={entry['support']['hero_mode_builds']} hero/mode builds"
    return render.clip(f"{title} · {support}: " + ("; ".join(details) or "no positive purchase receipts"), limit)


def reference_text(evidence):
    from datetime import datetime, timezone
    ref = evidence["reference"]
    dates = [datetime.fromtimestamp(ref[key], timezone.utc).strftime("%Y-%m-%d")
             for key in ("from", "through") if ref.get(key) is not None]
    window = " · " + "–".join(dates) if dates else ""
    return (f"Experimental · {ref.get('matches', 0):,} {POPULATION}; "
            f"patch {ref.get('patch') or 'unavailable'}{window}. "
            "Skills use the same hero and game mode. Unscored means insufficient or unavailable evidence, not normal.")
