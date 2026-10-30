"""Break each rule on purpose and confirm a test fails. Run from the repo root:

    .venv/bin/python scripts/mutation_check.py              # every mutation
    .venv/bin/python scripts/mutation_check.py "words: "    # only those whose name contains one of the arguments

Each mutation names the file it breaks and the test files that must catch it. It edits source files
in place while it runs: run nothing else from this checkout until it finishes. Files are restored
afterwards. Exit code 1 if any mutation goes unnoticed.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ("src/model/rules.py", ["tests/test_model.py", "tests/test_model_receipts.py"])
CORE = ("src/collector/core.py", ["tests/test_core.py", "tests/test_http.py"])
HANDLER = ("src/collector/handler.py", ["tests/test_handler.py"])
STORE = ("src/collector/store.py", ["tests/test_store.py"])
TEMPLATE = ("template.yaml", ["tests/test_template.py"])
SYNC = ("scripts/sync.sh", ["tests/test_sync.py"])
PAGES = ("src/timeline/pages.py", ["tests/test_timeline_pages.py", "tests/test_timeline_build.py"])
WORDS = ("src/timeline/words.py", ["tests/test_timeline_words.py"])
FLIGHTS = ("src/timeline/flights.py", ["tests/test_timeline_flights.py"])
SITE = ("src/timeline/build.py", ["tests/test_timeline_build.py"])
SEARCH = ("src/timeline/static/search.js", ["tests/test_timeline_build.py"])
CHECK = ("src/timeline/check.py", ["tests/test_timeline_check.py", "tests/test_publish.py"])
SITE_TEMPLATE = ("site-template.yaml", ["tests/test_site_template.py"])
PUBLISH = ("scripts/publish.sh", ["tests/test_publish.py"])

# name -> (file, text as it stands, the broken replacement) ; model entries use MODEL below
MODEL_MUTATIONS = {
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
    "plain 404 not treated as missing state": (STORE, 'in ("NoSuchKey", "404")', 'in ("NoSuchKey",)'),
    "ping sends no body": (HANDLER, "data=message.encode()[:10000]", "data=b''"),
    "ping sends no user agent": (HANDLER, 'headers={"User-Agent": user_agent})', "headers={})"),
    "ping timeout 999": (HANDLER, "urllib.request.urlopen(req, timeout=10).close()", "urllib.request.urlopen(req, timeout=999).close()"),
    "transient failure pings /fail again": (HANDLER, '        log.error("collector failed: %s", err)\n        raise', '        log.error("collector failed: %s", err)\n        pinger(fail_url, str(err))\n        raise'),
    "user agent not checked at startup": (HANDLER, '        core.check_user_agent(env["USER_AGENT"])\n', "\n"),
    "alarm on one window": (TEMPLATE, "      EvaluationPeriods: 2\n      DatapointsToAlarm: 2", "      EvaluationPeriods: 1\n      DatapointsToAlarm: 1"),
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
    "Israel time from a naive conversion": (PAGES, "return utc_naive.replace(tzinfo=timezone.utc).astimezone(ISRAEL)", "return utc_naive.astimezone(ISRAEL)"),
    "dates never shown": (PAGES, 'return f"{local:%H:%M}" if local.date() == page_date else', 'return f"{local:%H:%M}" if True else'),
    "search keys keep leading zeros only": (PAGES, "keys = [code + number, code + bare, number, bare,", "keys = [code + number, code + number, number, number,"),
    "bare number not a search key": (PAGES, "keys = [code + number, code + bare, number, bare,", "keys = [code + number, code + bare,"),
    "anchor without the date": (PAGES, 'f"{airline}{flight_no}-{direction}-{sched_local_first:%Y%m%d-%H%M}-{airport}"', 'f"{airline}{flight_no}-{direction}-{sched_local_first:%H%M}-{airport}"'),
    "anchor from the final scheduled time": (PAGES, 'f["direction"], f["sched_local_first"], f["airport"])}" \'', 'f["direction"], f["sched_local_final"], f["airport"])}" \''),
    "lead time rounded to nearest": (PAGES, 'return f"at least {int(low // 60)} h before its scheduled time"', 'return f"at least {round(low / 60)} h before its scheduled time"'),
    "after from the late end of the bracket": (PAGES, "    if high < 0:", "    if low < 0:"),
    "less than an hour from the early end": (PAGES, 'return "less than an hour before its scheduled time" if high < 60 else', 'return "less than an hour before its scheduled time" if low < 60 else'),
    "around never said": (PAGES, '    return "around its scheduled time"', '    return "before its scheduled time"'),
    "censored told with a lead": (PAGES, '    elif f["cancel_lead_censored"]:', "    elif False:"),
    "cancelled again not said": (PAGES, 'return f"Board showed CANCELED again (last seen {last})." if f["uncanceled"] else None', "return None"),
    "retimed label dropped": (PAGES, 'what = ("retimed: " if obs["change_kind"] == "retime" else "") + "<br>".join(lines)', 'what = "<br>".join(lines)'),
    "every change shown as between": (PAGES, "    if prev is not None and (seen - prev).total_seconds() > gap_hours * 3600:", "    if prev is not None and (seen - prev).total_seconds() > 0:"),
    "index never says partial": (PAGES, '<td>{"partial" if d["partial"] else ""}</td>', "<td></td>"),
    "footer last seen from first sighting": (PAGES, """f'{e(fmt_utc(f["last_seen_at"], page_date))}. Seen on""", """f'{e(fmt_utc(f["first_seen_at"], page_date))}. Seen on"""),
    "first sighting not singled out": (PAGES, '    if f["canceled_at_first_sight"]:', "    if False:"),
    "later status not mentioned": (PAGES, '    if f["uncanceled"]:', "    if False:"),
    "long pause not shown as between": (PAGES, "    if prev is not None and (seen - prev).total_seconds() > gap_hours * 3600:", "    if False:"),
    "old value read from the new row": (PAGES, 'lines = [f"{label}: {_value(c, prev, page_date)} →', 'lines = [f"{label}: {_value(c, obs, page_date)} →'),
    "first row not labelled": (PAGES, 'what = "first seen by us: " +', 'what = "first listed: " +'),
    "Hebrew not marked right to left": (PAGES, """return f'<span lang="he" dir="rtl">{e(value)}</span>' if value else \"\"""", """return f'<span>{e(value)}</span>' if value else \"\""""),
    "board text not escaped": (PAGES, 'return html.escape("" if value is None else str(value))', 'return "" if value is None else str(value)'),
    "noindex dropped": (PAGES, """        '<meta name="robots" content="noindex">\\n'\n""", ""),
    "unofficial line dropped": (PAGES, 'f"<footer><p>{e(attribution)}</p><p>{e(UNOFFICIAL)}</p></footer>\\n"', 'f"<footer><p>{e(attribution)}</p></footer>\\n"'),
    "codeshare partners not listed": (PAGES, "    if partners:", "    if False:"),
    "same-number listings not noted": (PAGES, "    for o in same_number:", "    for o in ():"),
    "pauses left off day pages": (PAGES, '    head += [f"<p>{e(gap_sentence(a, b, day))}</p>" for a, b in gaps]\n', ""),
    "partial only at the end": (SITE, "partial = first_check > start + BOARD_KEEPS or last_check < end - BOARD_AHEAD", "partial = last_check < end - BOARD_AHEAD"),
    "partial only at the start": (SITE, "partial = first_check > start + BOARD_KEEPS or last_check < end - BOARD_AHEAD", "partial = first_check > start + BOARD_KEEPS"),
    "undated flights not refused": (SITE, "    if undated:", "    if False:"),
    "anchor clash not refused": (SITE, "        if len(set(anchors)) != len(anchors):", "        if False:"),
    "foreign folder replaced": (SITE, "        if folder.exists() and not (folder / MARKER).exists():", "        if False:"),
    "only the output folder checked": (SITE, "    for folder in (out_dir, *_siblings(out_dir)):", "    for folder in (out_dir,):"),
    "every pause on every day page": (SITE, "day_gaps = [(a, b) for a, b in gaps if a < window[1] and b > window[0]]", "day_gaps = gaps"),
    "pauses only over six hours": (SITE, 'if (s["gap_before_s"] or 0) > GAP_HOURS * 3600]', 'if (s["gap_before_s"] or 0) > 6 * 3600]'),
    "day by first scheduled time": (SITE, 'by_day.setdefault(f["sched_local_final"].date(), []).append(f)', 'by_day.setdefault(f["sched_local_first"].date(), []).append(f)'),
    "search matches anywhere in a key": (SEARCH, 'keys.split(" ").some((key) => key.startsWith(q))', "keys.includes(q)"),
    "search keeps spaces": (SEARCH, 'return query.toLowerCase().replace(/\\s+/g, "");', "return query.toLowerCase();"),
    "endorsement words dropped from the footer": (PAGES, 'UNOFFICIAL = ("Unofficial; not affiliated with or endorsed by the Israel Airports Authority, "\n              "data.gov.il or the State of Israel.")', 'UNOFFICIAL = "Unofficial; not affiliated with the Israel Airports Authority."'),
    "tags left in before scanning": (CHECK, '    return re.sub(r"<[^>]*>", " ", text)', "    return text"),
    "text as written not scanned": (CHECK, "versions = (flatten(raw), flatten(strip_tags(raw)))", "versions = (flatten(strip_tags(raw)),)"),
    "tags stripped from pages only": (CHECK, "versions = (flatten(raw), flatten(strip_tags(raw)))", "versions = (flatten(raw), flatten(strip_tags(raw)) if path.suffix == '.html' else '')"),
    "line breaks not collapsed": (CHECK, 'return re.sub(r"\\s+", " ", html.unescape(text)).lower()', "return html.unescape(text).lower()"),
    "entities not unescaped": (CHECK, 'return re.sub(r"\\s+", " ", html.unescape(text)).lower()', 'return re.sub(r"\\s+", " ", text).lower()'),
    "scan is case-sensitive": (CHECK, 'return re.sub(r"\\s+", " ", html.unescape(text)).lower()', 'return re.sub(r"\\s+", " ", html.unescape(text))'),
    "an empty site passes": (CHECK, '    if not any(p.suffix == ".html" for p in files):', "    if False:"),
    "scripts not scanned": (CHECK, 'SCANNED = {".html", ".css", ".js"}', 'SCANNED = {".html"}'),
    "source line not required": (CHECK, 'NOTICES = {"source line": ATTRIBUTION, "unofficial line": UNOFFICIAL}', 'NOTICES = {"unofficial line": UNOFFICIAL}'),
    "unofficial line not required": (CHECK, 'NOTICES = {"source line": ATTRIBUTION, "unofficial line": UNOFFICIAL}', 'NOTICES = {"source line": ATTRIBUTION}'),
    "missing lines do not fail the check": (CHECK, "    return 1 if hits or missing else 0", "    return 1 if hits else 0"),
    "banned phrases do not fail the check": (CHECK, "    return 1 if hits or missing else 0", "    return 1 if missing else 0"),
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
    "words: one_in without halves up": (WORDS, "return math.floor(r + 0.5) if r < 20 else 5 * math.floor(r / 5 + 0.5)", "return round(r) if r < 20 else 5 * round(r / 5)"),
    "words: changed back on a NULL flag": (WORDS, '    if not f["uncanceled"]:', '    if f["uncanceled"] is False:'),
    "words: warning on a departed flight": (WORDS, '    if f["outcome"] != "canceled":\n        return None\n    return _warning_rule(f)[1]', "    return _warning_rule(f)[1]"),
    "words: Israel time from a naive conversion": (WORDS, "return utc_naive.replace(tzinfo=timezone.utc).astimezone(ISRAEL)", "return utc_naive.astimezone(ISRAEL)"),
    "words: dates never shown": (WORDS, 'return f"{local:%H:%M}" if local.date() == page_date else', 'return f"{local:%H:%M}" if True else'),
    "words: gap from the previous line": (WORDS, '        after = o["prev_observed_at"]', '        after = obs[i - 1]["observed_at"]'),
    "words: cancellation given a single time": (WORDS, 'if _cancelled(o) or o["observed_at"] - after', 'if o["observed_at"] - after'),
    "words: Hebrew-only change shown": (WORDS, '    if "status" in changed and not _cancelled(o):', '    if ("status" in changed or "status_he" in changed) and not _cancelled(o):'),
    "words: retime not said": (WORDS, 'changed, retime = o["changed_fields"], o["change_kind"] == "retime"', 'changed, retime = o["changed_fields"], False'),
    "words: earliest record reads as a cancellation time": (WORDS, 'parts = ["already cancelled" if o["status"] == "CANCELED" else _status(o["status"])]', 'parts = [_status(o["status"])]'),
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
}

MUTATIONS = {name: (MODEL, old, new) for name, (old, new) in MODEL_MUTATIONS.items()} | COLLECTOR_MUTATIONS


def main(wanted: list[str]) -> int:
    """Run every mutation, or with `wanted` only those whose name contains one of its strings."""
    chosen = {name: m for name, m in MUTATIONS.items() if not wanted or any(w in name for w in wanted)}
    if not chosen:
        print(f"No mutation name contains any of {wanted}.")
        return 2
    originals = {}
    missed = []
    try:
        for name, ((rel, tests), old, new) in chosen.items():
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
    sys.exit(main(sys.argv[1:]))
