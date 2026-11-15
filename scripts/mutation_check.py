"""Break each rule on purpose and confirm a test fails. Run from the repo root:

    .venv/bin/python scripts/mutation_check.py              # every mutation
    .venv/bin/python scripts/mutation_check.py "words: "    # only those whose name contains one of the arguments

Each mutation names the file it breaks and the test files that must catch it. It edits source files
in place while it runs: run nothing else from this checkout until it finishes. Files are restored
afterwards.

A mutation is caught only when pytest exits 1 (a test failed or errored). Any other exit means pytest
could not run the tests as asked (a test file or id that no longer exists, 4; a module that no longer
imports, 2; no tests collected, 5; pytest killed by a signal), which proves nothing about the rule, so
it is reported as ERROR with the line of pytest's output that names the cause. That includes a break
that stops the broken module importing (a syntax error, a name a test imports removed): pick a break
that leaves the module importable. A run past TIME_LIMIT is killed with everything it started and
counts as caught, reported as TIMEOUT: a break that makes a test hang is one the tests noticed.

No run can use bytecode cached from another version of a file the check writes. Python trusts a cached
.pyc whose source has the same size and the same whole-second mtime, so a same-size break written within
a second of the last one could otherwise run the last one's code, and be judged by its result. The runs
are given PYTHONDONTWRITEBYTECODE, but a test that starts Python with an environment of its own still
writes bytecode (tests/test_timeline_check.py does), so each time the check writes a file, the break or
the original, it deletes that module's cached bytecode too.

Exit code 1 if any mutation goes unnoticed or errs, or if its text to break is not found exactly once
(the script is out of date).
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

from pytest import ExitCode

ROOT = Path(__file__).resolve().parent.parent
# The longest one mutation's pytest run may take. Measured 2026-11-11 on the development Mac, unmutated: the model
# tests (tests/test_model.py with tests/test_model_receipts.py) took 7.7 to 11.3 s; every other target set under 9 s
# (tests/test_timeline_check.py with tests/test_publish.py: 5.9 to 6.5 s, and 8.4 s once in a review's run), but for
# one 12.5 s run of tests/test_mutation_check.py (about 5.5 s as a rule). Mutated, the slowest runs take 20 to 23 s
# (two planted bugs in the runner leave a hung test or a held pipe the full 20 s) and every other one 14 s at most.
# 120 s is about ten times the slowest unmutated run: room for a slower CI runner and for a break that slows its tests
# without hanging them.
TIME_LIMIT = 120
MODEL = ("src/model/rules.py", ["tests/test_model.py", "tests/test_model_receipts.py"])
CORE = ("src/collector/core.py", ["tests/test_core.py", "tests/test_http.py"])
HANDLER = ("src/collector/handler.py", ["tests/test_handler.py"])
STORE = ("src/collector/store.py", ["tests/test_store.py"])
TEMPLATE = ("template.yaml", ["tests/test_template.py"])
ALARMS = ("template.yaml", ["tests/test_template.py", "tests/test_alarms.py"])
HANDLER_LOGS = ("src/collector/handler.py", ["tests/test_handler.py", "tests/test_alarms.py"])
SYNC = ("scripts/sync.sh", ["tests/test_sync.py"])
WORDS = ("src/timeline/words.py", ["tests/test_timeline_words.py"])
FLIGHTS = ("src/timeline/flights.py", ["tests/test_timeline_flights.py"])
VIEWS = ("src/timeline/views.py", ["tests/test_timeline_views.py"])
SITE = ("src/timeline/build.py", ["tests/test_timeline_build.py"])
SEARCH = ("src/timeline/static/search.js", ["tests/test_timeline_search.py"])
STYLE = ("src/timeline/static/style.css", ["tests/test_timeline_style.py"])
CHECK = ("src/timeline/check.py", ["tests/test_timeline_check.py", "tests/test_publish.py"])
SITE_TEMPLATE = ("site-template.yaml", ["tests/test_site_template.py"])
PUBLISH = ("scripts/publish.sh", ["tests/test_publish.py"])
REPORT = ("src/model/report.py", ["tests/test_model.py", "tests/test_model_receipts.py"])
RUNNER = ("scripts/mutation_check.py", ["tests/test_mutation_check.py"])
LOAD = ("src/timeline/load.py", ["tests/test_timeline_build.py"])
COUNTING = ("src/timeline/counting.py", ["tests/test_counting.py", "tests/test_figures_check.py"])
RATES = ("src/timeline/rates.py", ["tests/test_rates.py"])
FROZEN_GUARD = ("src/timeline/counting.py", ["tests/test_frozen.py"])
FIGURES = ("scripts/figures_check.py", ["tests/test_figures_check.py"])
RECORD = ("src/timeline/record.py", ["tests/test_record.py"])
DISPLAY = ("src/timeline/display.py", ["tests/test_display.py"])

# name -> (file, text as it stands, the broken replacement) ; model entries use MODEL below
MODEL_MUTATIONS = {
    "R9 sightings ignored, a snapshot confirms only itself": ("coalesce(s.last_sighting, b.fetched_at) AS confirmed_until", "b.fetched_at AS confirmed_until"),
    "R9 gap measured from the store, not the last sighting": ("epoch(fetched_at - lag(confirmed_until) OVER w)::BIGINT AS gap_before_s", "epoch(fetched_at - lag(fetched_at) OVER w)::BIGINT AS gap_before_s"),
    "R9 a repeated store's receipt not a sighting": ("            FROM base b JOIN receipts r\n              ON r.run_started_at >= b.fetched_at", "            FROM base b JOIN (SELECT * FROM receipts WHERE action = 'unchanged') r\n              ON r.run_started_at >= b.fetched_at"),
    "R9 the next snapshot's own receipt credited to the one before": ("AND (b.next_fetched_at IS NULL OR r.run_started_at < b.next_fetched_at)\n            GROUP BY b.snapshot_id", "AND (b.next_fetched_at IS NULL OR r.run_started_at < b.next_fetched_at + INTERVAL 1 SECOND)\n            GROUP BY b.snapshot_id"),
    "R9 a sighting of other content not refused": ("    if misplaced:", "    if False:"),
    "R4 hole measured from the last store, not the last sighting": ("          AND epoch(n.first_seen_at - o.last_confirmed_at) <= {GAP_HOURS} * 3600", "          AND epoch(n.first_seen_at - o.last_seen_at) <= {GAP_HOURS} * 3600"),
    "R3 previous appearance from the store, not the last sighting": ("                   lag(s.confirmed_until) OVER w AS prev_observed_at,", "                   lag(r.fetched_at) OVER w AS prev_observed_at,"),
    "R7 last seen from the store, not the last sighting": ("                   max(s.snap_rn) AS last_rn, max(s.confirmed_until) AS last_seen_at", "                   max(s.snap_rn) AS last_rn, max(r.fetched_at) AS last_seen_at"),
    "R8 announced after from the store, not the last sighting": ("            SELECT k.flight_id, max(s.confirmed_until) AS cancel_announced_after", "            SELECT k.flight_id, max(r.fetched_at) AS cancel_announced_after"),
    "R1 ambiguous hour resolved to the later instant": ("WHEN il_idt_ok(t) THEN t - INTERVAL 3 HOUR", "WHEN il_ist_ok(t) THEN t - INTERVAL 2 HOUR"),
    "R1 no nonexistent flag": ("CREATE MACRO il_nonexistent(t) AS NOT il_idt_ok(t) AND NOT il_ist_ok(t)", "CREATE MACRO il_nonexistent(t) AS false"),
    "R2 duplicates kept": ("        WHERE key_rank = 1\n", "\n"),
    "R2 repeated snapshots kept": ("WHERE NOT repeat AND NOT incomplete AND receipt IN ('receipted', 'legacy'))", "WHERE NOT incomplete AND receipt IN ('receipted', 'legacy'))"),
    "R2 missing total not refused": ("    if no_total:", "    if False:"),
    "R2 incomplete snapshots kept": ("                          count(*) < max(declared_total) AS incomplete", "                          false AS incomplete"),
    "R2 conflict keeps highest id": ("PARTITION BY snapshot_id, {key} ORDER BY row_id)", "PARTITION BY snapshot_id, {key} ORDER BY row_id DESC)"),
    "R3 counters not tracked": ('"est_local", "status", "status_he", "terminal", "counters", "zone",', '"est_local", "status", "status_he", "terminal", "zone",'),
    "R3 unchanged rows emitted": ("WHERE change_kind <> 'change' OR len(changed_fields) > 0", "WHERE true"),
    "R4 window 24h": ("RETIME_WINDOW_HOURS = 12", "RETIME_WINDOW_HOURS = 24"),
    "R4 terminal new status allowed": ("WHERE o.last_status NOT IN ({terminal}) AND n.first_status NOT IN ({terminal})", "WHERE o.last_status NOT IN ({terminal})"),
    "R4 links across gaps": ("          AND epoch(n.first_seen_at - o.last_confirmed_at) <= {GAP_HOURS} * 3600\n", "\n"),
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
    "receipts ignored": ("CASE WHEN st.snapshot_id IS NOT NULL THEN 'receipted'", "CASE WHEN false THEN 'receipted'"),
    "everything legacy": ("WHEN (b.first_receipt IS NULL OR n.fetched_at < b.first_receipt)\n                         AND n.fetched_at < TIMESTAMP '{RECEIPTS_SINCE}' THEN 'legacy'", "WHEN true THEN 'legacy'"),
    "legacy cutover at the newest receipt": ("WHEN (b.first_receipt IS NULL OR n.fetched_at < b.first_receipt)", "WHEN (b.first_receipt IS NULL OR n.fetched_at < b.newest_receipt)"),
    "legacy without the known start of receipts": ("                         AND n.fetched_at < TIMESTAMP '{RECEIPTS_SINCE}' THEN 'legacy'", "                         THEN 'legacy'"),
    "first receipt from stored receipts only": ("min(run_started_at) AS first_receipt", "min(run_started_at) FILTER (WHERE action = 'stored') AS first_receipt"),
    "known orphan only before the newest receipt": ("WHEN n.snapshot_id IN ({orphans}) THEN 'orphan'", "WHEN n.snapshot_id IN ({orphans}) AND n.fetched_at <= b.newest_receipt THEN 'orphan'"),
    "superseded ignores the hash": ("WHEN n.next_sha = n.sha AND n.next_id IN (SELECT snapshot_id FROM st) THEN 'superseded'", "WHEN n.next_id IN (SELECT snapshot_id FROM st) THEN 'superseded'"),
    "superseded without a receipted copy": ("WHEN n.next_sha = n.sha AND n.next_id IN (SELECT snapshot_id FROM st) THEN 'superseded'", "WHEN n.next_sha = n.sha THEN 'superseded'"),
    "superseded never": ("WHEN n.next_sha = n.sha AND n.next_id IN (SELECT snapshot_id FROM st) THEN 'superseded'", "WHEN false THEN 'superseded'"),
    "pending and orphan snapshots kept": ("AND NOT incomplete AND receipt IN ('receipted', 'legacy'))", "AND NOT incomplete)"),
    "repeat check over dropped snapshots": ("WITH c AS (SELECT * FROM snapshot_files WHERE NOT incomplete AND receipt IN ('receipted', 'legacy')),", "WITH c AS (SELECT * FROM snapshot_files WHERE NOT incomplete),"),
    "known orphans ignored": ("WHEN n.snapshot_id IN ({orphans}) THEN 'orphan'", "WHEN false THEN 'orphan'"),
    "pending grace 60 min": ("PENDING_GRACE_MINUTES = 35", "PENDING_GRACE_MINUTES = 60"),
    "pending grace 5 min": ("PENDING_GRACE_MINUTES = 35", "PENDING_GRACE_MINUTES = 5"),
    "newest receipt from stored receipts only": ("max(run_started_at) AS newest_receipt FROM receipts),", "max(run_started_at) FILTER (WHERE action = 'stored') AS newest_receipt FROM receipts),"),
    "stale receipts not refused": ("    if stale:", "    if False:"),
    "unreceipted snapshots not refused": ("    if unreceipted:", "    if False:"),
    "receipt mismatch not refused": ("    if differ:", "    if False:"),
    "receipt mismatch on rows only": ("(file_rows <> receipt_rows OR file_pages <> receipt_pages)", "(file_rows <> receipt_rows)"),
    "receipt without files not refused": ("    if missing:", "    if False:"),
    "unknown receipt version accepted": ("    if odd:", "    if False:"),
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
    "latch message points at the README": (CORE, "(see docs/operations.md, If it's blocked)", '(see README)'),
    "plain 404 not treated as missing state": (STORE, 'in ("NoSuchKey", "404")', 'in ("NoSuchKey",)'),
    "ping sends no body": (HANDLER, "data=message.encode()[:10000]", "data=b''"),
    "ping sends no user agent": (HANDLER, 'headers={"User-Agent": user_agent})', "headers={})"),
    "ping timeout 999": (HANDLER, "urllib.request.urlopen(req, timeout=10).close()", "urllib.request.urlopen(req, timeout=999).close()"),
    "transient failure pings /fail again": (HANDLER, '        log.error("collector failed: %s", err)\n        raise', '        log.error("collector failed: %s", err)\n        pinger(fail_url, str(err))\n        raise'),
    "user agent not checked at startup": (HANDLER, '        core.check_user_agent(env["USER_AGENT"])\n', "\n"),
    'alarm: receipt pattern double-quoted in YAML': (ALARMS, '      FilterPattern: \'"\\"receipt\\": \\"receipts/"\'', '      FilterPattern: "\\"receipt\\": \\"receipts/"'),
    'alarm: receipt pattern misses the key': (ALARMS, '      FilterPattern: \'"\\"receipt\\": \\"receipts/"\'', '      FilterPattern: \'"\\"receipt\\": \\"receipt/"\''),
    'alarm: block pattern in the wrong case': (ALARMS, '      FilterPattern: \'"BLOCKED:"\'', '      FilterPattern: \'"Blocked:"\''),
    'alarm: receipt metric renamed in the filter': (ALARMS, '          MetricName: Receipts\n', '          MetricName: Receipt\n'),
    'alarm: missed refresh compares <=': (ALARMS, '      ComparisonOperator: LessThanThreshold\n', '      ComparisonOperator: LessThanOrEqualToThreshold\n'),
    'alarm: missed refresh ignores silence': (ALARMS, '      TreatMissingData: breaching\n', '      TreatMissingData: notBreaching\n'),
    'alarm: missed refresh after 5 minutes': (ALARMS, '      EvaluationPeriods: 7\n      DatapointsToAlarm: 7\n', '      EvaluationPeriods: 1\n      DatapointsToAlarm: 1\n'),
    'alarm: missed refresh in one-minute slots': (ALARMS, '      Period: 300\n      EvaluationPeriods: 7', '      Period: 60\n      EvaluationPeriods: 7'),
    'alarm: block alarm fires on silence': (ALARMS, '      TreatMissingData: notBreaching\n', '      TreatMissingData: breaching\n'),
    'alarm: no email on OK': (ALARMS, '      AlarmActions:\n        - !Ref AlertTopic\n      OKActions:\n        - !Ref AlertTopic\n\n  BlockedAlarm:', '      AlarmActions:\n        - !Ref AlertTopic\n\n  BlockedAlarm:'),
    'alarm: collector logs as JSON': (ALARMS, '      LoggingConfig:\n        LogGroup: !Ref CollectorLogs\n', '      LoggingConfig:\n        LogGroup: !Ref CollectorLogs\n        LogFormat: JSON\n'),
    'alarm: summary logged compact': (HANDLER_LOGS, '    log.info(json.dumps(summary))\n    pinger(cfg.healthcheck_url, json.dumps(summary))', '    log.info(json.dumps(summary, separators=(",", ":")))\n    pinger(cfg.healthcheck_url, json.dumps(summary))'),
    'alarm: block logged in lower case': (HANDLER_LOGS, 'log.error("BLOCKED: %s", err)', 'log.error("blocked: %s", err)'),
    "alarm: summary's receipt key renamed": (HANDLER_LOGS, 'asdict(outcome) | {"code_sha256": core.CODE_SHA256}', '{("receipt_key" if k == "receipt" else k): v for k, v in asdict(outcome).items()} | {"code_sha256": core.CODE_SHA256}'),
    "user agent pattern dropped": (TEMPLATE, "    AllowedPattern: '.*\\+https?://.*@.*'", "    AllowedPattern: '.*'"),
    "state written before the receipt": (CORE, '    store.put_receipt(receipt_key, _receipt("stored", now, downloaded_at, last_modified, prefix, digest, pages), now)\n    new_state.update(sha256=digest, last_key=keys[0])\n    store.write_state(new_state)\n', '    new_state.update(sha256=digest, last_key=keys[0])\n    store.write_state(new_state)\n    store.put_receipt(receipt_key, _receipt("stored", now, downloaded_at, last_modified, prefix, digest, pages), now)\n'),
    "unchanged run writes no receipt": (CORE, '        store.put_receipt(receipt_key, _receipt("unchanged", now, downloaded_at, last_modified, stored_prefix, digest, pages), now)\n', "\n"),
    "unchanged trusts any last_key": (CORE, 'stored_prefix.endswith(f"Z-{digest[:12]}")', "stored_prefix"),
    "download time from the run start": (CORE, "    downloaded_at = clock()\n", "    downloaded_at = now\n"),
    "receipt key without the hash": (CORE, '{now:%H%M%S}Z-{digest[:12]}.json"', '{now:%H%M%S}Z.json"'),
    "fingerprint ignores file content": (CORE, "hashlib.sha256(path.read_bytes()).digest()", "b''"),
    "run summary without the code fingerprint": (HANDLER, 'asdict(outcome) | {"code_sha256": core.CODE_SHA256}', "asdict(outcome)"),
    "receipt not locked": (STORE, '        self._put_locked(key, body, now, ContentType="application/json")', '        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")'),
    "receipts not writable": (TEMPLATE, '                - !Sub "${ArchiveBucket.Arn}/receipts/*"\n', ""),
    "raw synced before receipts": (SYNC, 'aws s3 sync "s3://$BUCKET/receipts/" data/receipts/ --profile "$PROFILE" --region "$REGION"\naws s3 sync "s3://$BUCKET/raw/" data/raw/ --profile "$PROFILE" --region "$REGION"', 'aws s3 sync "s3://$BUCKET/raw/" data/raw/ --profile "$PROFILE" --region "$REGION"\naws s3 sync "s3://$BUCKET/receipts/" data/receipts/ --profile "$PROFILE" --region "$REGION"'),
    "sync identity not checked": (SYNC, 'if [ "$who" != "$EXPECTED" ]; then', "if false; then"),
    "partial only at the end": (SITE, "partial = first_check > start + BOARD_KEEPS or last_check < end - BOARD_AHEAD", "partial = last_check < end - BOARD_AHEAD"),
    "partial only at the start": (SITE, "partial = first_check > start + BOARD_KEEPS or last_check < end - BOARD_AHEAD", "partial = first_check > start + BOARD_KEEPS"),
    "undated flights not refused": (SITE, "    if undated:", "    if False:"),
    "foreign folder replaced": (SITE, "        if folder.exists() and not (folder / MARKER).exists():", "        if False:"),
    "only the output folder checked": (SITE, "    for folder in (out_dir, *_siblings(out_dir)):", "    for folder in (out_dir,):"),
    "pauses only over six hours": (SITE, 'if (s["gap_before_s"] or 0) > GAP_HOURS * 3600]', 'if (s["gap_before_s"] or 0) > 6 * 3600]'),
    "day by first scheduled time": (SITE, "        by_day.setdefault(fl.day, []).append(fl)", "        by_day.setdefault(fl.rows[0].sched_first.date(), []).append(fl)"),
    "site: methodology page still written": (SITE, '    files["how-it-works.html"] = views.how_it_works_page(ATTRIBUTION, gaps)', '    files["how-it-works.html"] = files["methodology.html"] = views.how_it_works_page(ATTRIBUTION, gaps)'),
    "site: chart without later days": (SITE, '    chart_days = shown + [i for i in infos if i.state == "ahead"]', "    chart_days = shown"),
    "site: unique check skipped": (SITE, "    flights.check_unique(rows)\n", ""),
    "site: since from the UTC date": (SITE, "    since = words.il_time(first_check).date()", "    since = first_check.date()"),
    "site: featured without the censored flags": (SITE, 'censored = {f["flight_id"]: f["cancel_lead_censored"] for f in table}', 'censored = {f["flight_id"]: False for f in table}'),
    "site: headline counted up to the first record": (SITE, "flights.headline_counts(flights_, last_check)", "flights.headline_counts(flights_, first_check)"),
    "search: places ranked before numbers": (SEARCH, "[...exact, ...numbers, ...places]", "[...exact, ...places, ...numbers]"),
    "search: no exact tier": (SEARCH, "    if (entry.n.includes(q)) exact.push(entry);\n    else if", "    if"),
    "search: no cap": (SEARCH, "found.slice(0, LIMIT)", "found"),
    "search: no more line": (SEARCH, "  if (found.more > 0) {", "  if (false) {"),
    "search: list never hidden": (SEARCH, "  list.hidden = items.length === 0;", "  list.hidden = false;"),
    "search: matches anywhere in a key": (SEARCH, "keys.some((key) => key.startsWith(q))", "keys.some((key) => key.includes(q))"),
    "search: query read as a pattern": (SEARCH, "keys.some((key) => key.startsWith(q))", 'keys.some((key) => new RegExp("^" + q).test(key))'),
    "search: keeps spaces": (SEARCH, 'return query.toLowerCase().replace(/\\s+/g, "");', "return query.toLowerCase();"),
    "search: box shown before the data is read": (SEARCH, "    const entries = JSON.parse(data.textContent);", "    box.hidden = false;\n    const entries = JSON.parse(data.textContent);"),
    "tags left in before scanning": (CHECK, '    return re.sub(r"<[^>]*>", " ", text)', "    return text"),
    "text as written not scanned": (CHECK, "versions = (flatten(raw), flatten(strip_tags(raw)))", "versions = (flatten(strip_tags(raw)),)"),
    "tags stripped from pages only": (CHECK, "versions = (flatten(raw), flatten(strip_tags(raw)))", "versions = (flatten(raw), flatten(strip_tags(raw)) if path.suffix == '.html' else '')"),
    "line breaks not collapsed": (CHECK, 'return re.sub(r"\\s+", " ", html.unescape(text))', "return html.unescape(text)"),
    "entities not unescaped": (CHECK, 'return re.sub(r"\\s+", " ", html.unescape(text))', 'return re.sub(r"\\s+", " ", text)'),
    "scan is case-sensitive": (CHECK, "    return plain(text).lower()", "    return plain(text)"),
    "an empty site passes": (CHECK, '    if not any(p.suffix == ".html" for p in files):', "    if False:"),
    "scripts not scanned": (CHECK, 'SCANNED = {".html", ".css", ".js"}', 'SCANNED = {".html"}'),
    "source line not required": (CHECK, 'NOTICES = {"source line": SOURCE_SHORT, "unofficial line": UNOFFICIAL}', 'NOTICES = {"unofficial line": UNOFFICIAL}'),
    "unofficial line not required": (CHECK, 'NOTICES = {"source line": SOURCE_SHORT, "unofficial line": UNOFFICIAL}', 'NOTICES = {"source line": SOURCE_SHORT}'),
    "missing lines do not fail the check": (CHECK, "    return 1 if hits or missing else 0", "    return 1 if hits else 0"),
    "banned phrases do not fail the check": (CHECK, "    return 1 if hits or missing else 0", "    return 1 if missing else 0"),
    "check: pronouns as substrings": (CHECK, 'PRONOUNS = re.compile(r"\\b(?:we|our|us)\\b", re.I)', 'PRONOUNS = re.compile(r"(?:we|our|us)", re.I)'),
    "check: pronouns in one case only": (CHECK, 'PRONOUNS = re.compile(r"\\b(?:we|our|us)\\b", re.I)', 'PRONOUNS = re.compile(r"\\b(?:we|our|us)\\b")'),
    "check: data words as substrings": (CHECK, 'COLLECTION = re.compile(r"\\b(?:board|boards|snapshot|snapshots|stored|observed|receipt|receipts)\\b", re.I)', 'COLLECTION = re.compile(r"(?:board|boards|snapshot|snapshots|stored|observed|receipt|receipts)", re.I)'),
    "check: I matched in any case": (CHECK, 'I_WORD = re.compile(r"\\bI\\b")', 'I_WORD = re.compile(r"\\bI\\b", re.I)'),
    "check: data spans not skipped": (CHECK, """DATA = re.compile(r'<span class="d">[^<]*</span>'""", """DATA = re.compile(r'<span class="NEVER">[^<]*</span>'"""),
    "check: search data not skipped": (CHECK, """r'|<script type="application/json" id="flights-data">[^<]*</script>'""", """r'|<script type="application/json" id="NEVER">[^<]*</script>'"""),
    "check: titles not skipped": (CHECK, "r'|<title>[^<]*</title>')", "r'|<title class=\"NEVER\">[^<]*</title>')"),
    "check: I allowed everywhere": (CHECK, '        hits += ["I"] if I_WORD.search(_without_built_by(text)) else []\n', ""),
    "check: I on how-it-works": (CHECK, '    if name.endswith(".html") and name != EXPLAINER:\n        hits += ["I"] if I_WORD.search(_without_built_by(text)) else []\n', '    if name.endswith(".html"):\n        hits += ["I"] if I_WORD.search(_without_built_by(text)) else []\n    if name.endswith(".html") and name != EXPLAINER:\n'),
    "check: data words on how-it-works": (CHECK, "        hits += _found(COLLECTION, texts)", '    if name.endswith(".html"):\n        hits += _found(COLLECTION, texts)'),
    "check: built-by line not exempt from I": (CHECK, '    return text.replace(built_by, " ") if built_by else text', "    return text"),
    "check: empty built-by line splits every letter": (CHECK, '    return text.replace(built_by, " ") if built_by else text', '    return text.replace(built_by, " ")'),
    "check: scripts read only with tags stripped": (CHECK, 'texts = [text] if name.endswith(".html") else [text, plain(masked)]', "texts = [text]"),
    "check: late phrases allowed": (CHECK, '"took off", "minutes late", "hours late",', '"took off",'),
    "check: placeholder allowed": (CHECK, "        if any(flatten(PLACEHOLDER) in v for v in versions):", "        if False:"),
    "check: attribution required everywhere": (CHECK, "wanted = NOTICES | (EXPLAINER_NOTICES if name == EXPLAINER else {})", "wanted = NOTICES | EXPLAINER_NOTICES"),
    "check: attribution not required on how-it-works": (CHECK, "wanted = NOTICES | (EXPLAINER_NOTICES if name == EXPLAINER else {})", "wanted = NOTICES"),
    "site readable by anyone": (SITE_TEMPLATE, "            Principal:\n              Service: cloudfront.amazonaws.com", '            Principal: "*"'),
    "site policy without the distribution condition": (SITE_TEMPLATE, '            Condition:\n              StringEquals:\n                AWS:SourceArn: !Sub "arn:aws:cloudfront::${AWS::AccountId}:distribution/${SiteDistribution}"\n', ""),
    "global bucket name as origin": (SITE_TEMPLATE, "DomainName: !GetAtt SiteBucket.RegionalDomainName", "DomainName: !GetAtt SiteBucket.DomainName"),
    "site served over http": (SITE_TEMPLATE, "ViewerProtocolPolicy: redirect-to-https", "ViewerProtocolPolicy: allow-all"),
    "site bucket public policies allowed": (SITE_TEMPLATE, "        RestrictPublicBuckets: true", "        RestrictPublicBuckets: false"),
    "origin requests unsigned": (SITE_TEMPLATE, "SigningBehavior: always", "SigningBehavior: never"),
    "publish identity not checked": (PUBLISH, 'if [ "$who" != "$EXPECTED" ]; then', "if false; then"),
    "publish without the build marker": (PUBLISH, 'if [ ! -f "$SITE/.timeline-site" ]; then', "if false; then"),
    "publish without the phrase check": (PUBLISH, 'if ! PYTHONPATH=src "$PYTHON" -m timeline.check "$SITE"; then', "if false; then"),
    "any bucket synced to": (PUBLISH, '  "$BUCKET_PREFIX"?*) ;;', "  *) ;;"),
    "bare bucket prefix accepted": (PUBLISH, '  "$BUCKET_PREFIX"?*) ;;', '  "$BUCKET_PREFIX"*) ;;'),
    "missing distribution accepted": (PUBLISH, 'if [ -z "$distribution" ] || [ "$distribution" = None ]; then', "if false; then"),
    "content type guessed": (PUBLISH, ' --content-type "$2" \\\n', " \\\n"),
    "upload without an allowlist": (PUBLISH, "--delete --exclude '*' --include \"$1\"", '--delete --include "$1"'),
    "invalidation path unquoted": (PUBLISH, "--paths '/*'", "--paths /*"),
    "folder path not guarded against filter characters": (PUBLISH, "  *'['* | *']'* | *'?'* | *'*'*)", "  NEVER-MATCHES)"),
    "browser cache lifetime dropped": (PUBLISH, "--cache-control 'max-age=300' ", ""),
    "site folder read from the repo root": (PUBLISH, 'SITE=$(cd "${SITE_DIR:-$ROOT/site}" 2>/dev/null && pwd)', 'SITE=$(cd "$ROOT" && cd "${SITE_DIR:-site}" 2>/dev/null && pwd)'),
    "script runs from the caller's folder": (PUBLISH, 'cd "$ROOT"\n', ""),
    "default site folder from the caller's folder": (PUBLISH, 'SITE=$(cd "${SITE_DIR:-$ROOT/site}" 2>/dev/null && pwd)', 'SITE=$(cd "${SITE_DIR:-site}" 2>/dev/null && pwd)'),
    "words: warning rules out of order": (WORDS, "    if hi < 0 and not censored:", '    if lo >= 60:\n        return 8, f"at least {hours(_down(lo))}"\n    if hi < 0 and not censored:'),
    "words: censored range rounded down at the top": (WORDS, "    return math.ceil(minutes / 60)", "    return math.floor(minutes / 60)"),
    "words: first sight treated as censored range": (WORDS, "    if hi is None:", "    if False:"),
    "words: around said as less than an hour": (WORDS, '    return 11, "around the scheduled time"', '    return 11, "less than an hour"'),
    "words: NO FINAL UPDATE from local time": (WORDS, "return UPCOMING if sched_utc_final > last_fetch else NO_FINAL_UPDATE", "return UPCOMING if il_time(sched_utc_final).replace(tzinfo=None) > last_fetch else NO_FINAL_UPDATE"),
    "words: equal time is upcoming": (WORDS, "return UPCOMING if sched_utc_final > last_fetch else NO_FINAL_UPDATE", "return UPCOMING if sched_utc_final >= last_fetch else NO_FINAL_UPDATE"),
    "words: headline without thousands separators": (WORDS, "{cancelled:,} of {known:,} flights", "{cancelled} of {known} flights"),
    "words: one_in without halves up": (WORDS, "return math.floor(r + 0.5) if r < 20 else 5 * math.floor(r / 5 + 0.5)", "return round(r) if r < 20 else 5 * round(r / 5)"),
    "words: changed back on a NULL flag": (WORDS, '    if not f["uncanceled"]:', '    if f["uncanceled"] is False:'),
    "words: warning on a departed flight": (WORDS, '    if f["outcome"] != "canceled":\n        return None\n    return _warning_rule(f)[1]', "    return _warning_rule(f)[1]"),
    "words: Israel time from a naive conversion": (WORDS, "return utc_naive.replace(tzinfo=timezone.utc).astimezone(ISRAEL)", "return utc_naive.astimezone(ISRAEL)"),
    "words: dates never shown": (WORDS, 'return f"{local:%H:%M}" if local.date() == page_date else', 'return f"{local:%H:%M}" if True else'),
    "words: gap from the previous line": (WORDS, '        after = o["prev_observed_at"]', '        after = obs[i - 1]["observed_at"]'),
    "words: cancellation given a single time": (WORDS, 'if _cancelled(o) or o["observed_at"] - after', 'if o["observed_at"] - after'),
    "words: Hebrew-only change shown": (WORDS, '    if "status" in changed and not _cancelled(o):', '    if ("status" in changed or "status_he" in changed) and not _cancelled(o):'),
    "words: retime not said": (WORDS, 'changed, retime = o["changed_fields"], o["change_kind"] == "retime"', 'changed, retime = o["changed_fields"], False'),
    "words: endorsement words dropped from the footer": (WORDS, 'UNOFFICIAL = ("Unofficial; not affiliated with or endorsed by the Israel Airports Authority, "\n              "data.gov.il or the State of Israel.")', 'UNOFFICIAL = "Unofficial; not affiliated with the Israel Airports Authority."'),
    "words: earliest record reads as a cancellation time":(WORDS, 'parts = ["already cancelled" if o["status"] == "CANCELED" else _status(o["status"])]', 'parts = [_status(o["status"])]'),
    "words: censored range only above 60 minutes": (WORDS, "    if censored and lo >= 60:", "    if censored and lo > 60:"),
    "words: at least 1 hour only above 60 minutes": (WORDS, "    if lo >= 60:\n        return 8,", "    if lo > 60:\n        return 8,"),
    "words: an hour after said as less than an hour": (WORDS, "        if -lo < 60:", "        if -lo <= 60:"),
    "words: 2 hours after said as about an hour": (WORDS, "        if -hi < 120:", "        if -hi <= 120:"),
    "words: records note on rule 7": (WORDS, "    if 4 <= rule <= 6:", "    if 4 <= rule <= 7:"),
    "flights: today from the UTC date": (FLIGHTS, "    today = words.il_time(last_fetch).date()", "    today = last_fetch.date()"),
    "flights: delayed from any day of the number": (FLIGHTS, 'delayed=any(o["status"] == "DELAYED" for o in own),', 'delayed=any(o["status"] == "DELAYED" for g in flights if (g["airline"], g["flight_no"], g["direction"]) == (f["airline"], f["flight_no"], f["direction"]) for o in by_flight.get(g["flight_id"], [])),'),
    "flights: unknown not counted": (FLIGHTS, "unknown=ls.count(words.UNKNOWN),", "unknown=0,"),
    "flights: featured ignores censoring": (FLIGHTS, "    clean = [r for r in cancelled if censored[r.flight_id] is False]", "    clean = cancelled"),
    "flights: address collision not refused": (FLIGHTS, "        if len(nums) > 1:", "        if False:"),
    "flights: place keys from one row only": (FLIGHTS, "for r in rs for k in place_keys(r.city, r.airport)", "for r in rs[:1] for k in place_keys(r.city, r.airport)"),
    "flights: label from local time": (FLIGHTS, 'words.main_label(f["outcome"], f["sched_utc_final"], last_fetch)', 'words.main_label(f["outcome"], f["sched_local_final"], last_fetch)'),
    "flights: records in input order": (FLIGHTS, 'own = sorted(by_flight.get(f["flight_id"], []), key=lambda o: o["snap_rn"])', 'own = by_flight.get(f["flight_id"], [])'),
    "flights: page date from the first scheduled time": (FLIGHTS, '        day = f["sched_local_final"].date()', '        day = f["sched_local_first"].date()'),
    "flights: address check minds case": (FLIGHTS, "numbers.setdefault(r.page.lower(), {})", "numbers.setdefault(r.page, {})"),
    "flights: recent cancellations unordered or uncapped": (FLIGHTS, "    return _newest_first([fl for fl in flights_ if fl.label == words.CANCELLED], lambda fl: fl.rows[0])[:n]", "    return [fl for fl in flights_ if fl.label == words.CANCELLED]"),
    "flights: featured tie order": (FLIGHTS, "        return sorted(_newest_first(cancelled), key=lambda r: len(r.lines), reverse=True)[0]", "        return sorted(cancelled, key=lambda r: len(r.lines), reverse=True)[0]"),
    "flights: headline counts upcoming flights": (FLIGHTS, "    labels = [fl.label for fl in flights_ if fl.lead.sched_utc_final <= last_fetch]", "    labels = [fl.label for fl in flights_]"),
    "flights: headline leaves out a flight due at the last record": (FLIGHTS, "if fl.lead.sched_utc_final <= last_fetch]", "if fl.lead.sched_utc_final < last_fetch]"),
    "flights: lists by codeshare group": (FLIGHTS, "        out.setdefault(of[r.flight_id].key, []).append(r)", "        out.setdefault((r.day, r.group_id), []).append(r)"),
    "flights: a list labels a flight by its first number": (FLIGHTS, "label=display.label(f, by_id, last_fetch),", "label=members[0].label,"),
    "flights: a cancelled flight's warning from its first number": (FLIGHTS, "lead=next(r for r in members if r.flight_id == c9) if c9 else members[0],", "lead=members[0],"),
    "flights: story from a number's own label": (FLIGHTS, "    cancelled = [fl.lead for fl in flights_ if fl.label == words.CANCELLED]", "    cancelled = [r for fl in flights_ for r in fl.rows if r.label == words.CANCELLED]"),
    "flights: partners tied by airline alone": (FLIGHTS, "and shown[p.flight_id] == shown[r.flight_id])", "and (p.airline == r.airline or shown[p.flight_id] == shown[r.flight_id]))"),
    "flights: partners split by label": (FLIGHTS, "and shown[p.flight_id] == shown[r.flight_id])", "and shown[p.flight_id] == shown[r.flight_id] and p.label == r.label)"),
    "flights: a list's DELAYED from its first number": (FLIGHTS, "delayed=display.delayed(f, delayed_ids),", "delayed=members[0].delayed,"),
    "flights: others name every other number": (FLIGHTS, "        named = tuple(r for r in fl.rows if _OTHERS.get(r.label) == verb)", "        named = tuple(r for r in fl.rows if r.label != words.CANCELLED)"),
    "flights: day counts from numbers": (FLIGHTS, "        labels.setdefault(fl.day, []).append(fl.label)", "        labels.setdefault(fl.day, []).extend(r.label for r in fl.rows)"),
    "views: data not escaped": (VIEWS, """f'<span class="d">{html.escape(str(value))}</span>'""", """f'<span class="d">{value}</span>'"""),
    "views: cancelled row closed": (VIEWS, 'out.append("<details open>" if r.label == words.CANCELLED else "<details>")', 'out.append("<details>")'),
    "views: delay sentence on every row": (VIEWS, """f'<p class="head">{" ".join(head)}</p>']""", """f'<p class="head">{" ".join(head)}</p>', f'<p class="note">{e(words.DELAY_SENTENCE)}</p>']"""),
    "views: Hebrew city without lang": (VIEWS, """who.append(f'<span lang="he" dir="rtl">{d(top.city_he)}</span>')""", """who.append(f'<span>{d(top.city_he)}</span>')"""),
    "views: footer without the short source": (VIEWS, 'f"<p>{e(words.SOURCE_SHORT)} {e(words.UNOFFICIAL)} {e(words.TIMES_NOTE)}</p>\\n"', 'f"<p>{e(words.UNOFFICIAL)} {e(words.TIMES_NOTE)}</p>\\n"'),
    "views: noindex dropped": (VIEWS, """'<meta name="robots" content="noindex">\\n'""", "''"),
    "views: day link without anchor": (VIEWS, """f'<a href="{root}{e(r.page)}#{e(r.anchor)}">""", """f'<a href="{root}{e(r.page)}">"""),
    "views: bare warning beside a label": (VIEWS, """parts.append(f'<span class="warn">{e(words.warning_sentence(r.warning))}</span>')""", """parts.append(f'<span class="warn">{e(r.warning)}</span>')"""),
    "views: headline at zero": (VIEWS, "    if headline:\n", "    if True:\n"),
    "views: search data not escaped": (VIEWS, r'.replace("<", "\\u003c")', ""),
    "views: recent not capped": (VIEWS, "_cancellations_table(recent[:RECENT], \"\")", "_cancellations_table(recent, \"\")"),
    "views: unknown left off the chart": (VIEWS, "        parts = _count_parts(info)\n", '        parts = [p for p in _count_parts(info) if "unknown" not in p]\n'),
    "views: last updated in UTC": (VIEWS, "    updated = words.il_time(last_record)", "    updated = last_record"),
    "views: day list from the chart's days": (VIEWS, "for x in all_days)", "for x in chart_days)"),
    "views: wordmark links to the page's own folder": (VIEWS, """<p class="wordmark"><a href="{root}index.html">""", """<p class="wordmark"><a href="index.html">"""),
    "views: no header band": (VIEWS, """f'<header class="band">\\n{_wordmark(root) if top is None else top}\\n</header>\\n'""", "''"),
    "views: last updated left out of the band": (VIEWS, """                     f'<p class="updated">Last updated {updated.day} {updated:%b %Y, %H:%M}</p>'])""", """                     ])"""),
    "views: cancelled tile shows the known count": (VIEWS, '("listed as cancelled", f"{cancelled:,}", True)', '("listed as cancelled", f"{known:,}", True)'),
    "views: ratio tile rounded its own way": (VIEWS, 'f"1 in {words.one_in(cancelled, known)}"', 'f"1 in {round(known / cancelled)}"'),
    "views: day tiles keep zeros": (VIEWS, "for label, n, red in parts if n or label.startswith(\"flight\")]", "for label, n, red in parts]"),
    "views: day tile says flights for one": (VIEWS, '("flight" if info.total == 1 else "flights", info.total, False)', '("flights", info.total, False)'),
    "views: incomplete not said on the chart": (VIEWS, '("incomplete", info.partial)) if on]', '("incomplete", False)) if on]'),
    "style: pale cancel text": (STYLE, "--cancel-fg: #b3261e;", "--cancel-fg: #e8827a;"),
    "style: dim muted text in the dark": (STYLE, "--muted: #9aa3b2;", "--muted: #5c5c61;"),
    "style: dim band text": (STYLE, "--band-muted: #c5d1ea;", "--band-muted: #5f6f93;"),
    "style: band lede in the page's color": (STYLE, ".band .lede { color: var(--band-muted);", ".band .lede { color: var(--muted);"),
    "style: day-page numbers may wrap": (STYLE, ".flights .nums .d { white-space: pre; }", ".flights .nums .d { white-space: pre-wrap; }"),
    "style: hidden box shown by a display rule": (STYLE, "[hidden] { display: none !important; }", "#search { display: block; }"),
    "style: published double spaces collapsed": (STYLE, ".d { white-space: pre-wrap; }", ".d { }"),
    "style: Hebrew city not isolated": (STYLE, '[dir="rtl"] { unicode-bidi: isolate; }', ""),
    "style: chart text left black": (STYLE, ".chart text { fill: var(--fg); }\n", ""),
    "style: chart text in an unchecked color": (STYLE, ".chart text { fill: var(--fg); }", ".chart text { fill: var(--line); }"),
    "style: chart text given a size": (STYLE, ".chart { display: block;", ".chart { font-size: 16px; display: block;"),
    "style: a label without its color": (STYLE, ".l-delayed { color: var(--delay-fg); background: var(--delay-bg); }", ""),
    "style: a web font": (STYLE, "/* --- page ", "@import url(font.css);\n/* --- page "),
    "style: flight numbers may wrap": (STYLE, ".cancellations td:nth-child(2) .d { white-space: pre; }", ".cancellations td:nth-child(2) .d { white-space: pre-wrap; }"),
    "site: gap sentence from the store, not the last sighting": (LOAD, "SELECT fetched_at, confirmed_until, lag(confirmed_until) OVER (ORDER BY snap_rn) AS prev, gap_before_s", "SELECT fetched_at, confirmed_until, lag(fetched_at) OVER (ORDER BY snap_rn) AS prev, gap_before_s"),
    "site: last updated from the store, not the last sighting": (SITE, 'first_check, last_check = snaps[0]["fetched_at"], snaps[-1]["confirmed_until"]', 'first_check, last_check = snaps[0]["fetched_at"], snaps[-1]["fetched_at"]'),
    "report: gap from the store, not the last sighting": (REPORT, "lag(confirmed_until) OVER (ORDER BY snap_rn) AS prev FROM snapshots", "lag(fetched_at) OVER (ORDER BY snap_rn) AS prev FROM snapshots"),
    # the counting rule's number-level "as of" reading (docs/flight-lookup.md, C6), and the frozen rule's import guard
    "counting: a number's last stretch ends at its last sighting": (COUNTING, 'end = f["last_seen_at"] + timedelta(seconds=1)', 'end = f["last_seen_at"]'),
    "counting: every stretch runs to the last sighting": (COUNTING, 'to_at=nxt["observed_at"] if nxt else end,', "to_at=end,"),
    "counting: the clock from the final scheduled time": (COUNTING, "t = s.sched_utc - timedelta(hours=h)", "t = own[-1].sched_utc - timedelta(hours=h)"),
    "counting: the last passing counts": (COUNTING, "out.setdefault((fid, h), (t, s.status))", "out[(fid, h)] = (t, s.status)"),
    "counting: a passing before the number was listed": (COUNTING, "if s.from_at <= t < s.to_at and not in_hole", "if t < s.to_at and not in_hole"),
    "counting: a hole's edges count as inside it": (COUNTING, "any(a < t < b for a, b in holes_)", "any(a <= t <= b for a, b in holes_)"),
    "counting: a hole at exactly an hour": (COUNTING, 's["gap_before_s"] > GAP_HOURS * 3600', 's["gap_before_s"] >= GAP_HOURS * 3600'),
    "counting: the first list read as following a hole": (COUNTING, 's["gap_before_s"] is not None and ', 's["gap_before_s"] is None or '),
    "counting: the last sighting from the latest store": (COUNTING, 'return snaps[-1]["confirmed_until"]', 'return snaps[-1]["fetched_at"]'),
    # rules C1 to C4: which numbers are one flight, its result, and when it is closed
    "counting: expected time left out of the tie": (COUNTING, 'return r["est_utc_final"], r["terminal_final"], _desks(r)', 'return r["terminal_final"], _desks(r)'),
    "counting: two desk ranges tie": (COUNTING, '    if da != "" and db != "" and da != db:\n', "    if False:\n"),
    "counting: two terminals tie": (COUNTING, '    if a["terminal_final"] != b["terminal_final"]:\n', "    if False:\n"),
    "counting: a row with no scheduled time is read": (COUNTING, '    if unplaced:\n        raise ValueError(f"{len(unplaced)} number', '    if False:\n        raise ValueError(f"{len(unplaced)} number'),
    "counting: an observation with no scheduled time is read": (COUNTING, '    if unplaced:\n        raise ValueError(f"{len(unplaced)} observation', '    if False:\n        raise ValueError(f"{len(unplaced)} observation'),
    "counting: a slot without the direction": (COUNTING, 'slots.setdefault((r["direction"], r["airport"], r["sched_utc_final"]), [])', 'slots.setdefault((r["airport"], r["sched_utc_final"]), [])'),
    "counting: two operated numbers tie by airline": (COUNTING, "return not (_operated(a) and _operated(b)) and (", "return ("),
    "counting: a cancelled number ties to any airline": (COUNTING, ' and (a["airline"] == b["airline"] or (da != "" and da == db))', ""),
    "counting: no chains": (COUNTING, "        if tied(rows[i], rows[j]):\n", "        if tied(rows[find(i)], rows[find(j)]):\n"),
    "counting: no desks counts as the same desks": (COUNTING, '(da != "" and da == db)', "(da == db)"),
    "counting: the fallback leaves every number alone": (COUNTING, "regrouped.setdefault(_shown(r), []).append(r)", 'regrouped.setdefault(r["flight_id"], []).append(r)'),
    "counting: the fallback keeps the numbers that did not operate together": (COUNTING, "return [[r] for r in part if not _operated(r)] + list(regrouped.values())", "return [[r for r in part if not _operated(r)]] + list(regrouped.values())"),
    "counting: no fallback": (COUNTING, "    if len({_shown(r) for r in part if _operated(r)}) < 2:\n", "    if True:\n"),
    "counting: cancelled before operated": (COUNTING, 'result="operated" if outcomes & OPERATED else "cancelled" if "canceled" in outcomes else "unknown",', 'result="cancelled" if "canceled" in outcomes else "operated" if outcomes & OPERATED else "unknown",'),
    "counting: closed at 47 hours": (COUNTING, "CLOSED_AFTER = timedelta(hours=48)", "CLOSED_AFTER = timedelta(hours=47)"),
    "counting: closed by the first scheduled time": (COUNTING, 'closed=first["sched_utc_final"] <= last_sighting_ - CLOSED_AFTER,', 'closed=first["sched_utc_final"] - (first["sched_local_final"] - first["sched_local_first"]) <= last_sighting_ - CLOSED_AFTER,'),
    "counting: grouping airline by string order": (COUNTING, 'return (int(digits.group()) if digits else math.inf, r["airline"])', 'return (r["flight_no"], r["airline"])'),
    "counting: a cancelled passing puts its flight in the row": (COUNTING, 'if status not in (None, "CANCELED"):', "if status is not None:"),
    "counting: a passing with no status puts its flight in the row": (COUNTING, 'if status not in (None, "CANCELED"):', 'if status != "CANCELED":'),
    "counting: open flights in the rate": (COUNTING, 'return f.closed and f.result != "unknown"', 'return f.result != "unknown"'),
    "counting: unknown results in the rate": (COUNTING, 'return f.closed and f.result != "unknown"', "return f.closed"),
    "counting: the row's moment from the latest passing": (COUNTING, "moment[at] = min(t, moment.get(at, t))", "moment[at] = max(t, moment.get(at, t))"),
    "frozen: counting imports words": (FROZEN_GUARD, "from __future__ import annotations\n", "from __future__ import annotations\n\nfrom . import words\n"),
    "frozen: model imports timeline": (("src/model/rules.py", ["tests/test_frozen.py"]), "from __future__ import annotations\n", "from __future__ import annotations\n\nimport timeline.words\n"),
    "frozen: rates imports words": (("src/timeline/rates.py", ["tests/test_frozen.py"]), "from __future__ import annotations\n", "from __future__ import annotations\n\nfrom . import words\n"),
    "frozen: record imports words": (("src/timeline/record.py", ["tests/test_frozen.py"]), "from __future__ import annotations\n", "from __future__ import annotations\n\nfrom . import words\n"),
    # the signs S1 to S4, each read as of its number's checkpoint moment, and what a flight carries
    "record: S1 for arrivals too": (RECORD, 'if r["direction"] == "D" and any(', "if any("),
    "record: S1 window from the departure's final time": (RECORD, "_between(of_airline, sched - INBOUND[1], sched - INBOUND[0])", '_between(of_airline, r["sched_utc_final"] - INBOUND[1], r["sched_utc_final"] - INBOUND[0])'),
    "record: whole ignores a tied number still listed": (RECORD, 'for y in by_slot.get((r["direction"], r["airport"], a.sched_utc), ()))', "for y in ())"),
    "record: a number that left read as cancelled afterwards": (RECORD, "y.from_at <= t < y.to_ever", "y.from_at <= t < y.to_at"),
    "record: counting start an hour off": (RECORD, "datetime(2026, 11, 15, 22)", "datetime(2026, 11, 15, 23)"),
    "record: S2 the earliest before": (RECORD, "whole(max(before, key=lambda a: a.sched_utc)", "whole(min(before, key=lambda a: a.sched_utc)"),
    "record: S3 includes its own slot": (RECORD, '               and (by_id[b.flight_id]["direction"], by_id[b.flight_id]["airport"], b.sched_utc)\n               != (r["direction"], r["airport"], sched)\n', ""),
    "record: S4 late when first seen at the first list": (RECORD, "resumed = {first_fetch, *(end for _, end in holes_)}", "resumed = {*(end for _, end in holes_)}"),
    "record: S4 carried when one number shows it": (RECORD, 'EVERY = frozenset({"S4"})', "EVERY = frozenset()"),
    "record: S1 carried only when all show it": (RECORD, 'EVERY = frozenset({"S4"})', 'EVERY = frozenset({"S4", "S1"})'),
    "record: a number first seen after the moment read": (RECORD, "y.from_at <= t < y.to_ever", "t < y.to_ever"),
    "record: S1 inbound from any airport": (RECORD, 'by_id[a.flight_id]["direction"] == "A" and by_id[a.flight_id]["airport"] == r["airport"]', 'by_id[a.flight_id]["direction"] == "A"'),
    "record: S1 and S3 from any airline": (RECORD, 'cancelled.setdefault(r["airline"], []).append(s)', '[cancelled.setdefault(airline, []).append(s) for airline in {x["airline"] for x in table}]'),
    "record: S2 the same time counts as before": (RECORD, "a.sched_utc < sched)", "a.sched_utc <= sched)"),
    "record: S2 tie broken by the larger flight_id": (RECORD, "key=lambda a: a.flight_id)", "key=lambda a: a.flight_id, reverse=True)"),
    # each read by the time or the slot the list showed at the moment, not the final one, and a missing status
    "record: S3 window from the final time": (RECORD, "for b in _between(of_airline, sched - NEAR, sched + NEAR)):", 'for b in _between(of_airline, r["sched_utc_final"] - NEAR, r["sched_utc_final"] + NEAR)):'),
    "record: S2 before the final time": (RECORD, "a.from_at <= t < a.to_ever and a.sched_utc < sched),", 'a.from_at <= t < a.to_ever and a.sched_utc < r["sched_utc_final"]),'),
    "record: S3's own slot by the final time": (RECORD, '!= (r["direction"], r["airport"], sched)\n', '!= (r["direction"], r["airport"], r["sched_utc_final"])\n'),
    "record: whole looks in the cancelled number's final slot": (RECORD, 'for y in by_slot.get((r["direction"], r["airport"], a.sched_utc), ()))', 'for y in by_slot.get((r["direction"], r["airport"], r["sched_utc_final"]), ()))'),
    "record: S4 by the time shown at the moment": (RECORD, "if first.sched_utc - first.from_at < LATE and", "if sched - first.from_at < LATE and"),
    "record: a tie by the same expected time alone": (RECORD, "return (y.est_utc == a.est_utc and y.desks == a.desks) or airline_y == airline_a or (", "return (y.est_utc == a.est_utc) or airline_y == airline_a or ("),
    "record: whole reads a missing status as listed": (RECORD, "y.status not in (None, CANCELED)\n", "y.status != CANCELED\n"),
    "record: a passing with no status puts its number in the row": (RECORD, "if at_h != h or status in (None, CANCELED):", "if at_h != h or status == CANCELED:"),
    # the sign test: the counted flights, the gate and its guard, what a run reads, and the record's files
    "record: uncounted flights read": (RECORD, "return [c for c in cells_24 if c.flight.first_seen >= start]", "return list(cells_24)"),
    "record: flights after the gate read": (RECORD, "[c for c in counted_ if gate_at is None or c.t + timedelta(hours=SIGN_ROW) <= gate_at]", "list(counted_)"),
    "record: gate at 199": (RECORD, "GATE_CANCELLED, GATE_DAYS, SIGN_ROW = 200, 60, 24", "GATE_CANCELLED, GATE_DAYS, SIGN_ROW = 199, 60, 24"),
    "record: gate without the 60 days": (RECORD, " and at >= start + timedelta(days=GATE_DAYS)", ""),
    "record: gate declared before the row is closed": (RECORD, "return None if any(u + timedelta(hours=SIGN_ROW) <= at for u in unclosed_) else at", "return at"),
    "record: S1's sets with arrivals": (RECORD, 'row = [c for c in read if sign != "S1" or c.flight.key[0] == "D"]', "row = list(read)"),
    "record: a second run replaces the first": (RECORD, 'open(path, "x" if once else "w"', 'open(path, "w"'),
    "record: result keys unsorted": (RECORD, "sort_keys=True", "sort_keys=False"),
    "record: floats written in full": (RECORD, 'return float(f"{value:.12g}")', "return value"),
    "record: the re-test counts from the first start": (RECORD, "retest_start(args.first_upload)", "COUNTING_START"),
    "record: re-test start at the upload": (RECORD, "    return datetime.combine(day, time(), tzinfo=ISRAEL).astimezone(timezone.utc).replace(tzinfo=None)\n", "    return first_upload\n"),
    "record: re-test start from a naive conversion": (RECORD, "first_upload.replace(tzinfo=timezone.utc).astimezone(ISRAEL)", "first_upload.astimezone(ISRAEL)"),
    "record: re-test written over the main result": (RECORD, 'folder / f"retest-{args.retest}"', "folder"),
    "record: first upload without Z accepted": (RECORD, '    if not value.endswith("Z"):\n', "    if False:\n"),
    "record: a lost gate passes": (RECORD, " and not stored_at.exists()", ""),
    "record: a re-test holds every sign": (RECORD, "        result = replace(result, signs={args.retest: result.signs[args.retest]})\n", "        pass\n"),
    # the sign test's remaining frozen behaviours: the unclosed filters, the sign windows, the stop and progress.json
    "record: unclosed counts a closed flight": (RECORD, "and not f.closed and f.first_seen >= start:", "and f.first_seen >= start:"),
    "record: unclosed counts an uncounted flight": (RECORD, "and not f.closed and f.first_seen >= start:", "and not f.closed:"),
    "record: unclosed counts every row": (RECORD, "if h == SIGN_ROW and status not in (None, CANCELED) and not f.closed", "if status not in (None, CANCELED) and not f.closed"),
    "record: unclosed counts a cancelled passing": (RECORD, "if h == SIGN_ROW and status not in (None, CANCELED) and not f.closed", "if h == SIGN_ROW and status is not None and not f.closed"),
    "record: S1 inbound window 1 minute short at the near end": (RECORD, "INBOUND = (timedelta(minutes=30), timedelta(hours=12))", "INBOUND = (timedelta(minutes=31), timedelta(hours=12))"),
    "record: S1 inbound window 1 minute short at the far end": (RECORD, "INBOUND = (timedelta(minutes=30), timedelta(hours=12))", "INBOUND = (timedelta(minutes=30), timedelta(hours=11, minutes=59))"),
    "record: S3 window 1 minute short": (RECORD, "NEAR = timedelta(hours=24) ", "NEAR = timedelta(hours=23, minutes=59) "),
    "record: S3 window 1 minute long": (RECORD, "NEAR = timedelta(hours=24) ", "NEAR = timedelta(hours=24, minutes=1) "),
    "record: S4 window 1 minute short": (RECORD, "LATE = timedelta(hours=48) ", "LATE = timedelta(hours=47, minutes=59) "),
    "record: S4 window 1 minute long": (RECORD, "LATE = timedelta(hours=48) ", "LATE = timedelta(hours=48, minutes=1) "),
    "record: a window leaves out its early end": (RECORD, "ordered[bisect_left(times, lo):", "ordered[bisect_right(times, lo):"),
    "record: a window leaves out its late end": (RECORD, ":bisect_right(times, hi)]", ":bisect_left(times, hi)]"),
    "record: main runs with no counting start": (RECORD, "              \"(docs/flight-lookup-plan.md)\", file=sys.stderr)\n        return 2\n", "              \"(docs/flight-lookup-plan.md)\", file=sys.stderr)\n"),
    "record: progress written once": (RECORD, 'write(result, folder / "progress.json", once=False)', 'write(result, folder / "progress.json", once=True)'),
    # rule C8: the range, the floor and the rounding
    "rates: a range from one airline-and-week group": (RATES, "        if len({(i.airline, week(i.day)) for i in items}) >= 2:", "        if True:"),
    "rates: a range from one day group": (RATES, "        if len({i.day for i in items}) >= 2:", "        if True:"),
    "rates: a range at zero cancelled": (RATES, "if 0 < cancelled < n_all:", "if cancelled < n_all:"),
    "rates: a range when all are cancelled": (RATES, "if 0 < cancelled < n_all:", "if 0 < cancelled:"),
    "rates: the smaller standard error": (RATES, "max(se_aw, se_d)", "min(se_aw, se_d)"),
    "rates: no small-sample factor": (RATES, "math.sqrt(groups / (groups - 1) * squares)", "math.sqrt(squares)"),
    "rates: weeks start on Monday": (RATES, "(day.weekday() + 1) % 7", "day.weekday()"),
    "rates: range on the rate scale": (RATES, "hi = 1 / (1 / (1 + math.exp(-(logit + half))))", "hi = 1 / (r + 2 * max(se_aw, se_d))"),
    "rates: floor at 9": (RATES, "FLOOR_CANCELLED, FLOOR_AIRLINES, FLOOR_DAYS = 10, 5, 5", "FLOOR_CANCELLED, FLOOR_AIRLINES, FLOOR_DAYS = 9, 5, 5"),
    "rates: floor without the airline count": (RATES, " and airlines >= FLOOR_AIRLINES", ""),
    "rates: floor without the day count": (RATES, " and days >= FLOOR_DAYS", ""),
    "rates: floor counts every flight's airline": (RATES, "len({i.airline for i in items if i.k})", "len({i.airline for i in items})"),
    "rates: halves down": (RATES, "math.floor(x / s + 0.5) * s", "math.ceil(x / s - 0.5) * s"),
    "rates: no step of 10": (RATES, "    if x < 1000:\n        return 10\n", ""),
    "rates: ends rounded inward": (RATES, "return math.floor(lo / step(lo)) * step(lo), math.ceil(hi / step(hi)) * step(hi)", "return math.ceil(lo / step(lo)) * step(lo), math.floor(hi / step(hi)) * step(hi)"),
    # a sign's lift and its scores
    "rates: lift range at 2 standard errors": (RATES, "LIFT_SE = 2.5", "LIFT_SE = 2"),
    "rates: a range touching 1 passes": (RATES, "return clears_floor and lower is not None and lower > 1", "return clears_floor and lower is not None and lower >= 1"),
    "rates: lift without the floor": (RATES, "    clears = w.clears_floor\n", "    clears = True\n"),
    "rates: a ratio with no cancelled flight without the sign": (RATES, "    if clears and k0:\n", "    if clears:\n"),
    "rates: split scored with the one rate": (RATES, "rated += [(i, half) for i in side]", "rated += [(i, one) for i in side]"),
    "rates: gain range from the plain standard error": (RATES, "    se = max(found) if None not in found else None\n", "    se = math.sqrt(math.fsum((g - gain) ** 2 for _, g in gains) / (n - 1) / n)\n"),
    "rates: lift passes on the ratio": (RATES, "passes(clears, lo))", "passes(clears, times))"),
    "rates: lift with the smaller standard error": (RATES, "se_log = max(found)", "se_log = min(found)"),
    "rates: gain range from the smaller standard error": (RATES, "    se = max(found) if None not in found else None\n", "    se = min(found) if None not in found else None\n"),
    # the figures check: the code against the figures file's SQL
    "figures: SQL from the wrong section": (FIGURES, "search(doc, heading.end(), stop)", "search(doc, 0, stop)"),
    "figures: a flight difference not reported": (FIGURES, "if a0.get(fid) != code.get(fid)}", "if (fid in a0) != (fid in code)}"),
    "figures: a figure off by one passes": (FIGURES, '        if value == expected:\n            print(f"{name}: {show(value)} ok")\n', '        if all(abs(a - b) <= 1 for a, b in zip(value, expected)):\n            print(f"{name}: {show(value)} ok")\n'),
    "figures: a cell difference not reported": (FIGURES, "if a0.get((h, ids)) != code.get((h, ids))]", "if False]"),
    "figures: cells compared on one side only": (FIGURES, "for h, ids in a0.keys() | code.keys()", "for h, ids in a0.keys() & code.keys()"),
    "figures: a found difference does not fail": (FIGURES, "failed = failed or bool(found)", "failed = failed"),
    "figures: an A25 difference does not fail": (FIGURES, '                  f"{show_signs(expected)}")\n            failed = True\n', '                  f"{show_signs(expected)}")\n'),
    "figures: S1 counted with arrivals": (FIGURES, 'c.h == h and (sign != "S1" or c.flight.key[0] == "D")', "c.h == h"),
    "figures: a sign difference not reported": (FIGURES, "if a0.get((h, numbers)) != code.get((h, numbers)))", "if False)"),
    "figures: the whole `sign` table read": (FIGURES, '"SELECT sign, h, flight_key FROM signcell WHERE present"', '"SELECT sign, h, flight_key FROM sign"'),
    "figures: the last snapshot as first_fetch": (FIGURES, 'snaps[0]["fetched_at"]', 'snaps[-1]["fetched_at"]'),
    "figures: signs compared on one side only": (FIGURES, "for h, numbers in a0.keys() | code.keys()", "for h, numbers in a0.keys() & code.keys()"),
    "figures: a ratio difference not reported": (FIGURES, "if a0b.get((sign, h)) != code.get((sign, h)))", "if False)"),
    "figures: an A29 difference does not fail": (FIGURES, '                  f"{show_a29(name, expected)}")\n            failed = True\n', '                  f"{show_a29(name, expected)}")\n'),
    "figures: an A3 or A17 difference does not fail": (FIGURES, '                  + f", the figures file {expected:,}")\n            failed = True\n', '                  + f", the figures file {expected:,}")\n'),
    "figures: A3's split reversed": (FIGURES, 'by_id[fid]["last_seen_at"] < by_id[fid]["sched_utc_final"]', 'by_id[fid]["last_seen_at"] >= by_id[fid]["sched_utc_final"]'),
    "figures: A3's split counts a number last seen at its time as before": (FIGURES, 'by_id[fid]["last_seen_at"] < by_id[fid]["sched_utc_final"]', 'by_id[fid]["last_seen_at"] <= by_id[fid]["sched_utc_final"]'),
    "figures: A17's after and holds rows swapped": (FIGURES, 'a17 = (s.late_after, s.late_holds, s.late_unplaced, s.late_before)', 'a17 = (s.late_holds, s.late_after, s.late_unplaced, s.late_before)'),
    # rules shown only on pages: C10's label and DELAYED, C9's warning, the count line and the late line
    "display: cancelled label before still listed": (DISPLAY, '    if "open" in outcomes:\n        return UPCOMING if f.key[2] > last_fetch else NO_FINAL_UPDATE  # key[2]: the slot\'s scheduled time\n    if "canceled" in outcomes:\n        return CANCELLED\n', '    if "canceled" in outcomes:\n        return CANCELLED\n    if "open" in outcomes:\n        return UPCOMING if f.key[2] > last_fetch else NO_FINAL_UPDATE  # key[2]: the slot\'s scheduled time\n'),
    "display: still listed before departed": (DISPLAY, '    if outcomes & OPERATED:\n        return DEPARTED if "departed" in outcomes else LANDED\n    if "open" in outcomes:\n        return UPCOMING if f.key[2] > last_fetch else NO_FINAL_UPDATE  # key[2]: the slot\'s scheduled time\n', '    if "open" in outcomes:\n        return UPCOMING if f.key[2] > last_fetch else NO_FINAL_UPDATE  # key[2]: the slot\'s scheduled time\n    if outcomes & OPERATED:\n        return DEPARTED if "departed" in outcomes else LANDED\n'),
    "display: DELAYED from the first number only": (DISPLAY, 'return any(fid in delayed_ids for fid in f.numbers)', 'return f.numbers[0] in delayed_ids'),
    "display: warning from the last cancellation": (DISPLAY, '    first = min((by_id[fid]', '    first = max((by_id[fid]'),
    "display: late line from the last cancelled number": (DISPLAY, 'late = Counter(_late(by_id[warning_number(f, by_id)]) for f in flights_', 'late = Counter(_late(max((by_id[fid] for fid in f.numbers if by_id[fid]["outcome"] == "canceled"), key=lambda r: r["canceled_first_seen_at"])) for f in flights_'),
    "display: censored brackets counted as after": (DISPLAY, '    if r["cancel_lead_censored"]:\n        return "unplaced"\n    if r["cancel_lead_max_min"] < 0:\n        return "after"\n', '    if r["cancel_lead_max_min"] < 0:\n        return "after"\n    if r["cancel_lead_censored"]:\n        return "unplaced"\n'),
    "display: gap and no-final-status counts swapped": (DISPLAY, 'unknown_gap=gap, unknown_no_final=len(unknown) - gap,', 'unknown_gap=len(unknown) - gap, unknown_no_final=gap,'),
    "display: first record from the UTC date": (DISPLAY, 'first_record=words.il_time(snaps[0]["fetched_at"]).date()', 'first_record=snaps[0]["fetched_at"].date()'),
    # the runner itself: only a failing test is a catch, a run past the limit is killed whole and counts as caught
    'runner: any non-zero exit counts as caught': (RUNNER, '    if returncode == ExitCode.TESTS_FAILED:\n        return "CAUGHT"', '    if returncode != ExitCode.OK:\n        return "CAUGHT"'),
    'runner: an error does not fail the check': (RUNNER, '    return 1 if missed or errors else 0\n', '    return 1 if missed else 0\n'),
    'runner: an error shown without its cause': (RUNNER, 'f"failure: {_telling_line(run)}")\n', 'f"failure")\n'),
    "runner: the cause from pytest's first E line": (RUNNER, '    return (exception or error or lines or ["(no output)"])[-1]\n', '    return (exception or error or lines or ["(no output)"])[0]\n'),
    'runner: no time limit given': (RUNNER, '                                  TIME_LIMIT, cwd=ROOT, env=env)\n', '                                  None, cwd=ROOT, env=env)\n'),
    'runner: a time-out counted as missed': (RUNNER, '                timed_out.append(name)\n', '                missed.append(name)\n'),
    'runner: a time-out printed as a plain catch': (RUNNER, '                print(f"TIMEOUT {name}: pytest ran past the {TIME_LIMIT:g} s limit and was killed; counted as caught")\n', '                print(f"CAUGHT {name}")\n'),
    'runner: only pytest killed, not what it started': (RUNNER, '        os.killpg(pid, signal.SIGKILL)\n', '        os.kill(pid, signal.SIGKILL)\n'),
    "runner: pytest run in the check's own session": (RUNNER, 'start_new_session=True,\n', 'start_new_session=False,\n'),
    'runner: bytecode written': (RUNNER, '    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}  # see the docstring: a cached .pyc could run the last break\n', '    env = dict(os.environ)\n'),
    'runner: an interrupt leaves the run going': (RUNNER, '        except BaseException:\n', '        except Exception:\n'),
    'runner: a run that ended in time but left a child counted as a time-out': (RUNNER, '            code = process.poll()\n', '            code = None\n'),
    'runner: a group with nothing left to kill crashes the check': (RUNNER, '    except (ProcessLookupError, PermissionError):\n', '    except ChildProcessError:\n'),
    'runner: pipes read only after the run ends': (RUNNER, '            stdout, stderr = process.communicate(timeout=limit)\n', '            process.wait(timeout=limit)\n            stdout, stderr = process.stdout.read(), process.stderr.read()\n'),
    'runner: cached bytecode kept': (RUNNER, '        cached.unlink()\n', '        pass\n'),
    'runner: the last output read with no limit': (RUNNER, '                stdout, stderr = process.communicate(timeout=drain)  # the rest of its output, its group killed\n', '                stdout, stderr = process.communicate()\n'),
    'runner: a process that left the session holding the pipes crashes the check': (RUNNER, '            except subprocess.TimeoutExpired as late:  # a process that left the session holds the pipes: stop reading\n', '            except ZeroDivisionError as late:\n'),
}

MUTATIONS = {name: (MODEL, old, new) for name, (old, new) in MODEL_MUTATIONS.items()} | COLLECTOR_MUTATIONS


def verdict(returncode: int) -> str:
    """CAUGHT when pytest says a test failed, MISSED when every test passed, ERROR for any other exit."""
    if returncode == ExitCode.TESTS_FAILED:
        return "CAUGHT"
    if returncode == ExitCode.OK:
        return "MISSED"
    return "ERROR"


def _exit_name(returncode: int) -> str:
    try:
        return ExitCode(returncode).name
    except ValueError:  # a signal, or a code pytest does not define
        return "not pytest's"


def _telling_line(run: subprocess.CompletedProcess) -> str:
    """The line of pytest's output that names why it could not run the tests: its last `E ` line (a collection
    error's exception; the `ERROR` line after it names only the file), else its last `ERROR` line (a test file or
    id not found), else its last line."""
    lines = [line for line in (run.stdout + run.stderr).splitlines() if line.strip()]
    exception = [line for line in lines if line.startswith("E ")]
    error = [line for line in lines if line.startswith("ERROR")]
    return (exception or error or lines or ["(no output)"])[-1]


def _write(path: Path, text: str) -> None:
    """Write `text` to `path` and delete its module's cached bytecode (see the docstring)."""
    path.write_text(text)
    for cached in (path.parent / "__pycache__").glob(f"{path.stem}.*.pyc"):
        cached.unlink()


# Seconds to read the rest of a run's output when it ended in time but its pipes stayed open past the limit: its group
# is killed by then, so what is left is already in the pipes, unless a process that left the session still holds them.
DRAIN_SECONDS = 5


def _kill_group(pid: int) -> None:
    """Kill every process in the session run_limited started for `pid`. A group with nothing left to kill is no
    error: only its exited, unreaped first process (macOS answers PermissionError), or nothing at all."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_limited(args: list[str], limit: float, drain: float = DRAIN_SECONDS,
                **popen) -> subprocess.CompletedProcess | None:
    """Run `args` to its end and return its exit code and output; None when it runs past `limit` seconds. It runs
    in a session of its own, so that past the limit, or on a Ctrl-C (which a session of its own does not get from
    the terminal), everything it started (a test's own subprocess, a shell script under test) is killed with it."""
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
                          **popen) as process:
        try:
            stdout, stderr = process.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            # The run may have ended in time, a process it started still holding the pipes: its exit code stands.
            code = process.poll()
            _kill_group(process.pid)
            if code is None:
                process.wait()  # not communicate(): a process that escaped the kill could hold the pipes open
                return None
            try:
                stdout, stderr = process.communicate(timeout=drain)  # the rest of its output, its group killed
            except subprocess.TimeoutExpired as late:  # a process that left the session holds the pipes: stop reading
                stdout, stderr = ((part or b"").decode(errors="replace") for part in (late.stdout, late.stderr))
            return subprocess.CompletedProcess(args, code, stdout, stderr)  # the pipes close as the `with` ends
        except BaseException:
            _kill_group(process.pid)
            process.wait()
            raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def main(wanted: list[str]) -> int:
    """Run every mutation, or with `wanted` only those whose name contains one of its strings."""
    chosen = {name: m for name, m in MUTATIONS.items() if not wanted or any(w in name for w in wanted)}
    if not chosen:
        print(f"No mutation name contains any of {wanted}.")
        return 2
    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}  # see the docstring: a cached .pyc could run the last break
    originals = {}
    missed = []
    errors = []
    timed_out = []
    try:
        for name, ((rel, tests), old, new) in chosen.items():
            path = ROOT / rel
            original = originals.setdefault(path, path.read_text())
            if original.count(old) != 1:
                print(f"STALE  {name}: the text to break occurs {original.count(old)} times in {rel}; update this script")
                missed.append(name)
                continue
            _write(path, original.replace(old, new))
            try:
                run = run_limited([sys.executable, "-m", "pytest", *tests, "-q", "-x", "-p", "no:cacheprovider"],
                                  TIME_LIMIT, cwd=ROOT, env=env)
            finally:
                _write(path, original)
            if run is None:
                print(f"TIMEOUT {name}: pytest ran past the {TIME_LIMIT:g} s limit and was killed; counted as caught")
                timed_out.append(name)
                continue
            outcome = verdict(run.returncode)
            if outcome == "ERROR":
                print(f"ERROR  {name}: pytest exited {run.returncode} ({_exit_name(run.returncode)}), not a test "
                      f"failure: {_telling_line(run)}")
                errors.append(name)
            else:
                print(f"{outcome} {name}")
                if outcome == "MISSED":
                    missed.append(name)
    finally:
        for path, original in originals.items():
            _write(path, original)
    found = (f" Missed: {missed}" if missed else "") + (f" Errors: {errors}" if errors else "")
    print("Files restored." + (found or " Every mutation was caught.")
          + (f" Timed out, counted as caught: {timed_out}" if timed_out else ""))
    return 1 if missed or errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
