# Test fixtures

`records.json` holds 38 real rows of the Ben Gurion flight board. Source: Israel Airports Authority, data.gov.il dataset `flydata`, resource `e83f763b-b7d7-479e-b172-ae981ddc6de5`, as captured on 2026-10-27 at 09:09 UTC by a public snapshot. The tests wrap these rows in a CKAN `datastore_search` reply. Once the collector has stored its first real reply, replace this file with rows from it so the fixture matches the live envelope byte for byte.

`blocked.html` is a made-up firewall page. It isn't a copy of data.gov.il's real block page, which we haven't seen.
