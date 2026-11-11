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
# The longest one mutation's pytest run may take. Measured 2026-11-11 on the development Mac, unmutated: the
# slowest target tests are tests/test_model.py with tests/test_model_receipts.py, 7.7 to 11.3 s (12.9 s at most in
# a full mutation run); every other target set ran in 6.8 s at most (tests/test_publish.py), but for one 12.5 s run
# of tests/test_mutation_check.py (about 5.5 s as a rule). 120 s is about ten times the slowest: room for a slower
# CI runner and for a break that slows its tests without hanging them.
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
    "day by first scheduled time": (SITE, "        by_day.setdefault(fl[0].day, []).append(fl)", "        by_day.setdefault(fl[0].sched_first.date(), []).append(fl)"),
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
    "flights: group split ignores the label": (FLIGHTS, "    return r.day, r.group_id, r.label, r.delayed, r.warning", "    return r.day, r.group_id, r.delayed, r.warning"),
    "flights: unknown not counted": (FLIGHTS, "unknown=ls.count(words.UNKNOWN),", "unknown=0,"),
    "flights: featured ignores censoring": (FLIGHTS, "    clean = [r for r in cancelled if censored[r.flight_id] is False]", "    clean = cancelled"),
    "flights: address collision not refused": (FLIGHTS, "        if len(nums) > 1:", "        if False:"),
    "flights: place keys from one row only": (FLIGHTS, "for r in rs for k in place_keys(r.city, r.airport)", "for r in rs[:1] for k in place_keys(r.city, r.airport)"),
    "flights: label from local time": (FLIGHTS, 'words.main_label(f["outcome"], f["sched_utc_final"], last_fetch)', 'words.main_label(f["outcome"], f["sched_local_final"], last_fetch)'),
    "flights: records in input order": (FLIGHTS, 'own = sorted(by_flight.get(f["flight_id"], []), key=lambda o: o["snap_rn"])', 'own = by_flight.get(f["flight_id"], [])'),
    "flights: page date from the first scheduled time": (FLIGHTS, '        day = f["sched_local_final"].date()', '        day = f["sched_local_first"].date()'),
    "flights: address check minds case": (FLIGHTS, "numbers.setdefault(r.page.lower(), {})", "numbers.setdefault(r.page, {})"),
    "flights: split ignores delayed": (FLIGHTS, "    return r.day, r.group_id, r.label, r.delayed, r.warning", "    return r.day, r.group_id, r.label, r.warning"),
    "flights: split ignores the warning": (FLIGHTS, "    return r.day, r.group_id, r.label, r.delayed, r.warning", "    return r.day, r.group_id, r.label, r.delayed"),
    "flights: recent cancellations unordered or uncapped": (FLIGHTS, "    return _newest_first([fl for fl in flights_ if fl[0].label == words.CANCELLED], lambda fl: fl[0])[:n]", "    return [fl for fl in flights_ if fl[0].label == words.CANCELLED]"),
    "flights: featured tie order": (FLIGHTS, "        return sorted(_newest_first(cancelled), key=lambda r: len(r.lines), reverse=True)[0]", "        return sorted(cancelled, key=lambda r: len(r.lines), reverse=True)[0]"),
    "flights: headline counts upcoming flights": (FLIGHTS, "    labels = [fl[0].label for fl in flights_ if fl[0].sched_utc_final <= last_fetch]", "    labels = [fl[0].label for fl in flights_]"),
    "flights: headline leaves out a flight due at the last record": (FLIGHTS, "if fl[0].sched_utc_final <= last_fetch]", "if fl[0].sched_utc_final < last_fetch]"),
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
    "site: gap sentence from the store, not the last sighting": (SITE, "SELECT fetched_at, confirmed_until, lag(confirmed_until) OVER (ORDER BY snap_rn) AS prev, gap_before_s", "SELECT fetched_at, confirmed_until, lag(fetched_at) OVER (ORDER BY snap_rn) AS prev, gap_before_s"),
    "site: last updated from the store, not the last sighting": (SITE, 'first_check, last_check = snaps[0]["fetched_at"], snaps[-1]["confirmed_until"]', 'first_check, last_check = snaps[0]["fetched_at"], snaps[-1]["fetched_at"]'),
    "report: gap from the store, not the last sighting": (REPORT, "lag(confirmed_until) OVER (ORDER BY snap_rn) AS prev FROM snapshots", "lag(fetched_at) OVER (ORDER BY snap_rn) AS prev FROM snapshots"),
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


def _kill_group(pid: int) -> None:
    """Kill every process in the session run_limited started for `pid`. A group with nothing left to kill is no
    error: only its exited, unreaped first process (macOS answers PermissionError), or nothing at all."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_limited(args: list[str], limit: float, **popen) -> subprocess.CompletedProcess | None:
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
            stdout, stderr = process.communicate()  # the rest of its output, the group that held the pipes killed
            return subprocess.CompletedProcess(args, code, stdout, stderr)
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
