"""Break each rule on purpose and confirm a test fails. Run from the repo root:

    .venv/bin/python scripts/mutation_check.py

Each mutation names the file it breaks and the test files that must catch it. Files are restored
afterwards. Exit code 1 if any mutation goes unnoticed.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ("src/model/rules.py", ["tests/test_model.py"])
CORE = ("src/collector/core.py", ["tests/test_core.py", "tests/test_http.py"])
HANDLER = ("src/collector/handler.py", ["tests/test_handler.py"])
STORE = ("src/collector/store.py", ["tests/test_store.py"])
TEMPLATE = ("template.yaml", ["tests/test_template.py"])

# name -> (file, text as it stands, the broken replacement) ; model entries use MODEL below
MODEL_MUTATIONS = {
    "R1 ambiguous hour resolved to the later instant": ("WHEN il_idt_ok(t) THEN t - INTERVAL 3 HOUR", "WHEN il_ist_ok(t) THEN t - INTERVAL 2 HOUR"),
    "R1 no nonexistent flag": ("CREATE MACRO il_nonexistent(t) AS NOT il_idt_ok(t) AND NOT il_ist_ok(t)", "CREATE MACRO il_nonexistent(t) AS false"),
    "R2 duplicates kept": ("        WHERE key_rank = 1\n", "\n"),
    "R2 repeated snapshots kept": ("            WHERE snapshot_id IN (SELECT snapshot_id FROM snapshot_runs WHERE NOT repeat AND NOT incomplete)\n", "            WHERE snapshot_id IN (SELECT snapshot_id FROM snapshot_runs WHERE NOT incomplete)\n"),
    "R2 missing total not refused": ("    if no_total:", "    if False:"),
    "R2 incomplete snapshots kept": ("                          count(*) < max(declared_total) AS incomplete", "                          false AS incomplete"),
    "R2 conflict keeps highest id": ("PARTITION BY snapshot_id, {key} ORDER BY row_id)", "PARTITION BY snapshot_id, {key} ORDER BY row_id DESC)"),
    "R3 counters not tracked": ('"est_local", "status", "status_he", "terminal", "counters", "zone",', '"est_local", "status", "status_he", "terminal", "zone",'),
    "R3 unchanged rows emitted": ("WHERE change_kind <> 'change' OR len(changed_fields) > 0", "WHERE true"),
    "R4 window 24h": ("RETIME_WINDOW_HOURS = 12", "RETIME_WINDOW_HOURS = 24"),
    "R4 terminal new status allowed": ("WHERE o.last_status NOT IN ({terminal}) AND n.first_status NOT IN ({terminal})", "WHERE o.last_status NOT IN ({terminal})"),
    "R4 links across gaps": ("          AND epoch(n.first_seen_at - o.last_seen_at) <= {GAP_HOURS} * 3600\n", "\n"),
    "R4 any later snapshot": ("AND n.first_rn = o.last_rn + 1", "AND n.first_rn > o.last_rn"),
    "R4 ties linked": ("WHERE r_old = 1 AND n_old = 1 AND r_new = 1 AND n_new = 1", "WHERE r_old = 1 AND r_new = 1"),
    "R5 est not in group key": ("coalesce(r.est_local::VARCHAR, ''), coalesce(r.terminal::VARCHAR, '')", "coalesce(r.terminal::VARCHAR, '')"),
    "R5 group at first appearance": ("SELECT flight_id, arg_max(group_key, snap_rn) AS group_key", "SELECT flight_id, arg_min(group_key, snap_rn) AS group_key"),
    "R6 operator by string order": ("ORDER BY try_cast(regexp_extract(flight_no, '[0-9]+') AS INTEGER) NULLS LAST, airline, flight_id", "ORDER BY flight_no, airline, flight_id"),
    "R7 vanished and dropped swapped": ("THEN 'vanished'\n                    ELSE 'dropped' END", "THEN 'dropped'\n                    ELSE 'vanished' END"),
    "R7 gap threshold 3h": ("GAP_HOURS = 1", "GAP_HOURS = 3"),
    "R8 upper bound from first canceled": ("epoch(o.canceled_sched.sched_utc - b.cancel_announced_after) / 60 AS cancel_lead_max_min", "epoch(o.canceled_sched.sched_utc - o.canceled_first_seen_at) / 60 AS cancel_lead_max_min"),
    "R8 never censored": ("OR o.canceled_first_seen_at - b.cancel_announced_after > INTERVAL {GAP_HOURS} HOUR END AS cancel_lead_censored", "END AS cancel_lead_censored"),
    "R4 many-to-one linked": ("WHERE r_old = 1 AND n_old = 1 AND r_new = 1 AND n_new = 1", "WHERE r_old = 1 AND n_old = 1"),
    "R4 adjacency from the old key's first snapshot": ("AND n.first_rn = o.last_rn + 1", "AND n.first_rn = o.first_rn + 1"),
    "R4 old key judged by first status": ("WHERE o.last_status NOT IN ({terminal})", "WHERE o.first_status NOT IN ({terminal})"),
    "R4 window without abs": ("AND abs(epoch(n.sched_utc - o.sched_utc)) <= {RETIME_WINDOW_HOURS} * 3600", "AND epoch(n.sched_utc - o.sched_utc) <= {RETIME_WINDOW_HOURS} * 3600"),
    "R5 terminal not in group key": ("coalesce(r.terminal::VARCHAR, ''), coalesce(r.counters, '')", "coalesce(r.counters, '')"),
    "R6 no airline tie-break": ("NULLS LAST, airline, flight_id", "NULLS LAST, flight_id"),
    "R7 horizon 6h": ("VANISH_HORIZON_HOURS = 1", "VANISH_HORIZON_HOURS = 6"),
    "R7 gap from first appearance": ("WHEN nxt.fetched_at - s.last_seen_at > INTERVAL {GAP_HOURS} HOUR THEN 'gap'", "WHEN nxt.fetched_at - o.first_seen_at > INTERVAL {GAP_HOURS} HOUR THEN 'gap'"),
    "Final state from a bare arg_max (NULL skipped)": ("o.fin.est_local AS est_local_final, o.fin.est_utc AS est_utc_final,", "coalesce(o.fin.est_local, o.fst.sched_local) AS est_local_final, o.fin.est_utc AS est_utc_final,"),
    "R8 uncanceled never": ("o.canceled_rn IS NOT NULL AND o.last_not_canceled_rn > o.canceled_rn AS uncanceled", "false AS uncanceled"),
    "reader buffer 256 MB": ("MAX_REPLY_BYTES = 32 * 1024 * 1024", "MAX_REPLY_BYTES = 256 * 1024 * 1024"),
}



COLLECTOR_MUTATIONS = {
    "status-check timeout 999 s": (CORE, "SHOW_TIMEOUT = 20.0", "SHOW_TIMEOUT = 999.0"),
    "download timeout 1 ms": (CORE, "SEARCH_TIMEOUT = 45.0", "SEARCH_TIMEOUT = 0.001"),
    "full fetch every 29 min": (CORE, "FULL_FETCH_EVERY = timedelta(minutes=30)", "FULL_FETCH_EVERY = timedelta(minutes=29)"),
    "pending window 11 min": (CORE, "PENDING_WINDOW = timedelta(minutes=10)", "PENDING_WINDOW = timedelta(minutes=11)"),
    "gzip with a timestamp": (CORE, "gzip.compress(page.body, mtime=0)", "gzip.compress(page.body, mtime=12345)"),
    "user agent not checked": (CORE, '    if "+http" not in user_agent or "@" not in user_agent:', "    if False:"),
    "body size not capped": (CORE, "    if len(body) > MAX_BODY_BYTES:", "    if False:"),
    "redirects to any host": (CORE, "        if (new.scheme, new.netloc) != (old.scheme, old.netloc):", "        if False:"),
    "redirects to any scheme": (CORE, "        if (new.scheme, new.netloc) != (old.scheme, old.netloc):", "        if new.netloc != old.netloc:"),
    "state written before the pages": (CORE, "    keys = []\n    for i, page in enumerate(pages):", "    store.write_state({**new_state, \"sha256\": digest})\n    keys = []\n    for i, page in enumerate(pages):"),
    "row ids not checked": (CORE, "            if not isinstance(row_id, int) or (last_id is not None and row_id <= last_id):", "            if False:"),
    "latch failure hides the block": (CORE, "        except Exception as latch_err:  # noqa: BLE001 - the block must still be reported as a block", "        except ValueError as latch_err:  # noqa: BLE001 - the block must still be reported as a block"),
    "plain 404 not treated as missing state": (STORE, 'in ("NoSuchKey", "404")', 'in ("NoSuchKey",)'),
    "ping sends no body": (HANDLER, "data=message.encode()[:10000]", "data=b''"),
    "ping sends no user agent": (HANDLER, 'headers={"User-Agent": user_agent})', "headers={})"),
    "ping timeout 999": (HANDLER, "urllib.request.urlopen(req, timeout=10).close()", "urllib.request.urlopen(req, timeout=999).close()"),
    "transient failure pings /fail again": (HANDLER, '        log.error("collector failed: %s", err)\n        raise', '        log.error("collector failed: %s", err)\n        pinger(fail_url, str(err))\n        raise'),
    "user agent not checked at startup": (HANDLER, '        core.check_user_agent(env["USER_AGENT"])\n', "\n"),
    "alarm on one window": (TEMPLATE, "      EvaluationPeriods: 2\n      DatapointsToAlarm: 2", "      EvaluationPeriods: 1\n      DatapointsToAlarm: 1"),
    "user agent pattern dropped": (TEMPLATE, "    AllowedPattern: '.*\\+https?://.*@.*'", "    AllowedPattern: '.*'"),
}

MUTATIONS = {name: (MODEL, old, new) for name, (old, new) in MODEL_MUTATIONS.items()} | COLLECTOR_MUTATIONS


def main() -> int:
    originals = {}
    missed = []
    try:
        for name, ((rel, tests), old, new) in MUTATIONS.items():
            path = ROOT / rel
            original = originals.setdefault(path, path.read_text())
            if original.count(old) != 1:
                print(f"STALE  {name}: the text to break occurs {original.count(old)} times in {rel}; update this script")
                missed.append(name)
                continue
            path.write_text(original.replace(old, new))
            try:
                run = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q", "-x", "-p", "no:cacheprovider"],
                                     capture_output=True, text=True, cwd=ROOT)
            finally:
                path.write_text(original)
            caught = run.returncode != 0
            print(("CAUGHT " if caught else "MISSED ") + name)
            if not caught:
                missed.append(name)
    finally:
        for path, original in originals.items():
            path.write_text(original)
    print("Files restored." + (f" Missed: {missed}" if missed else " Every mutation was caught."))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
