# Test fixtures

`records.json` holds 38 real rows of the Ben Gurion flight board. Source: Israel Airports Authority, data.gov.il dataset `flydata`, resource `e83f763b-b7d7-479e-b172-ae981ddc6de5`, as captured on 2026-10-27 at 09:09 UTC by a public snapshot. The tests wrap these rows in a CKAN `datastore_search` reply whose envelope keys (`include_total`, `records_format`, `_links`, `total_was_estimated`, `fields` and the rest) mirror the reply the collector archived on 2026-10-29; see `ckan()` in `tests/conftest.py`. The rows themselves are the same shape as the archived ones.

`blocked.html` is a made-up firewall page. It isn't a copy of data.gov.il's real block page, which we haven't seen.

`rules_record_v1.py` is `src/model/rules.py` as tag `record-v1` holds it, byte for byte (`git show record-v1:src/model/rules.py`): the model's rules frozen with the record, kept here as the reference the current build is compared with (`scripts/tagged_check.py`, `docs/lighter-build.md`, "The frozen record"). Its SHA-256 is pinned in `scripts/tagged_check.py` (`TAGGED_SHA256`), which refuses a copy with any other hash, and in `tests/test_tagged_check.py`.
