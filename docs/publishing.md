# Publishing the history timeline (q15)

Grade: portfolio project. Careful where it faces the public (wording, permissions, what the bucket exposes); quick everywhere else: uploads by hand, no custom domain, no automation.

Goal: one HTTPS link to the history site that I can send, for a few cents a month, without touching the collector's stack.

## What might not be obvious

- **Public is copyable.** Taking our copy down takes minutes; copies others make (archive.org, scrapers) can outlive it. The terms reading (`docs/terms.md`) is what makes this acceptable.
- **`noindex` stays on every page** (`docs/site-redesign.md`, "Pages"), so search engines will not list the site; people arrive by the link I share. Dropping it is a one-line change, my call.
- **The site is a snapshot.** It shows the data as of the last upload, until a nightly build exists (q5, q2). The front page says when the data was last recorded ("Last updated …").
- **The address is a random `dxxxx.cloudfront.net` name.** A custom domain is a later, separate decision with its own cost.
- **Pay-as-you-go has no spending cap.** The account's existing "My Monthly Cost Budget" ($5, emails at 85% and 100% of actual, 100% of forecast) is the guard.
- **My name goes on the site.** Every page's footer and the front page carry a built-by line and a link to the code; the line held a placeholder until I wrote it (`BUILT_BY`, `src/timeline/words.py`); the upload check still refuses a site that contains the placeholder.

## Design

### A stack of its own

New template `site-template.yaml`, stack `flights-archive-site`, il-central-1, deployed with `aws cloudformation deploy` (no SAM: there is no code). The collector stack holds the Object Lock archive and the live Lambda; a site change must never put a change set on it.

Resources:

- `SiteBucket`: private; `BucketOwnerEnforced` (origin access control requires it); all four public-access blocks; SSE-S3. No versioning and no Object Lock: the site is rebuilt from the model, so there is nothing to keep.
- `SiteOriginAccessControl`: origin type `s3`, signing `always`, protocol `sigv4`. Access control is the only option here: the older origin access identity does not support buckets in opt-in Regions launched after December 2022, il-central-1 among them (https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).
- `SiteDistribution`: one origin at `!GetAtt SiteBucket.RegionalDomainName` (the global `bucket.s3.amazonaws.com` form returns 400 for buckets in Regions launched after 2019-03-20), with `S3OriginConfig: {OriginAccessIdentity: ""}` and the access control attached; default root object `index.html`; HTTP redirected to HTTPS; GET and HEAD only; managed cache policy CachingOptimized and managed response-headers policy SecurityHeadersPolicy (both by their fixed AWS IDs; the latter sends `nosniff`, so content types must be right); compression on; `PriceClass_100` (North America, Europe, Israel and Türkiye); the default cloudfront.net certificate; no access logs. A missing page returns 403 (there is no list grant), not 404; acceptable for a site that links only to pages it has.
- `SiteBucketPolicy`: `s3:GetObject` on the bucket's objects for the `cloudfront.amazonaws.com` service principal, only when `AWS:SourceArn` is this distribution. No other grant; no `*` principal. A separate resource, which avoids a dependency cycle with the distribution.
- Outputs: bucket name, distribution ID, domain name.

### Code changes

- **Footer** (clause 8 of the terms): `UNOFFICIAL` becomes "Unofficial; not affiliated with or endorsed by the Israel Airports Authority, data.gov.il or the State of Israel." The anti-goal line in `docs/timeline.md` and the test constant follow. Since the redesign (q18) the footer reads `SOURCE_SHORT`, `UNOFFICIAL` and "Times are Israel time.", then "How this works", "Code on GitHub" and the built-by line; the full `ATTRIBUTION` moved to `how-it-works.html` (`docs/site-redesign.md`, "Footer (every page)").
- **One banned-phrase check, at upload**: `src/timeline/check.py` holds the list (moved from `tests/test_timeline_build.py`, which imports it) and `python -m timeline.check site` scans every `.html`, `.css` and `.js` file (the types the upload sends) as written and with tags stripped, a phrase in either counting; entities are unescaped and whitespace collapsed in both, so a phrase in an attribute, split by markup or broken across lines is still caught. It exits non-zero and names file and phrase on a hit.
- **`scripts/publish.sh`**, in this order, uploading nothing if a check fails:
  1. the AWS identity check `scripts/sync.sh` uses;
  2. `site/` must carry the build's `.timeline-site` marker, and its full path must hold no `[`, `]`, `?` or `*`;
  3. the banned-phrase check over `site/`;
  4. bucket and distribution from the stack's outputs; the bucket name must start with `flights-archive-site-sitebucket-` (so never the archive bucket, where a delete would add markers that hide locked snapshots, and never `None` from a missing output), and the distribution ID must be non-empty;
  5. three syncs, one per file type, each an allowlist with its content type set rather than guessed: `--exclude '*' --include '*.html' --content-type 'text/html; charset=utf-8'`, then `*.css` as `text/css; charset=utf-8`, then `*.js` as `text/javascript; charset=utf-8`, each with `--delete` (which, under the filters, removes only stale files of that type) and `Cache-Control: max-age=300`. Nothing else in `site/` (the marker, a `.DS_Store`) is uploaded;
  6. a CloudFront invalidation of the literal `'/*'`.
- **The terms date** (`docs/terms.md`, clause 2) is not a script flag: anyone could copy it from our own doc. I read the date on the live page and state it with each upload's go; a date other than 30/08/2025 stops the upload until the terms are read again.
- **Takedown**: `aws s3 rm s3://<site bucket>/ --recursive`, then invalidate `'/*'`; minutes, and the stack can go later.

### Tests and mutation checks

- `tests/test_site_template.py`: the bucket's four blocks and ownership; no `*` principal anywhere; the policy grants only `s3:GetObject` to the CloudFront service principal under the `AWS:SourceArn` condition on this distribution; the origin's `RegionalDomainName` and empty identity; the access control's signing; HTTPS redirect; GET and HEAD only; default root object; the managed policy IDs.
- `tests/test_publish.py`, against a fake `aws` as `tests/test_sync.py` does: identity first; a wrong account, a missing marker, a banned phrase, the archive bucket's name or a missing output each upload nothing; the happy path runs the three syncs with their includes, content types and `--delete` against the stack's bucket, then invalidates the literal `/*`, all under `--profile flights-sam`.
- `tests/test_timeline_check.py`: a phrase found across a tag, a line break and an entity, in an attribute, in a script past a `<` comparison and inside markup in a script string; a clean site passes; an empty or missing folder fails. The footer's new words are checked on every page of a synthetic build (`tests/test_timeline_build.py`).
- CI lints both templates with `--regions il-central-1` (cfn-lint checks only us-east-1 by default).
- `scripts/mutation_check.py`: an entry for each refusal in `publish.sh`, the tag stripping, the footer words, the policy's `SourceArn` condition, the regional origin and the HTTPS redirect.

### Deploy, then publish (each only when I approve it)

1. Identity check, then `aws cloudformation deploy --template-file site-template.yaml --stack-name flights-archive-site --profile flights-sam --region il-central-1`.
2. `scripts/sync.sh`, model build, timeline build.
3. I read the terms page's update date and give the go with it; `sh scripts/publish.sh`.
4. I open the link and check a day page, a flight and the search.

## Cost (monthly)

- S3 storage at $0.025 per GB-month (AWS price list, il-central-1, published 2026-10-15): well under a cent for the 3.9 MB site of 2026-10-30, about $0.03 near 1 GB.
- S3 requests: every build rewrites every file, so each upload PUTs all of them (961 on 2026-10-30, more as new flight numbers and days appear) plus a few LISTs, at $0.0055 per 1,000 (AWS Price List API, il-central-1, read 2026-10-29; `docs/receipts.md`, "Cost (monthly)"): about half a cent an upload. CloudFront caches the GETs.
- CloudFront: inside the always-free 1 TB and 10 million requests a month; invalidations: the first 1,000 paths a month are free, and `/*` counts as one path (https://aws.amazon.com/cloudfront/pricing/pay-as-you-go, https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/PayingForInvalidation.html).
- Total: under $0.05 a month at up to about nine uploads a month; uploading every day would come to about $0.16. Guard: the account's "My Monthly Cost Budget", $5, emails at 85% and 100% of actual and 100% of forecast (`aws budgets describe-budgets` and `describe-notifications-for-budget`, read 2026-10-29).

## Unverified until the deploy

- Settled 2026-10-30: the stack deploys in il-central-1 (CREATE_COMPLETE, 09:35Z).

## Rejected

- GitHub Pages: free from a public repo, with no account verification, but the site is built on my Mac from the private archive, so every build's pages would have to be committed to the repo, and the repo would have to go public before launch (q17). Rechecked 2026-10-29 after the repo-public decision (q16) and the CloudFront verification wait; I kept CloudFront.
- CloudFront's flat-rate Free plan: no overage charges, but a console opt-in and an eligibility check; revisit if traffic ever costs money.
- S3 static website hosting: needs a public bucket and serves HTTP only.
- Adding the site to `template.yaml`: one deploy would touch both the archive and the site.
- Publishing automatically after each build: needs the nightly build (q5, q2) first.
- A build-time banned-phrase stop beside the upload check: one check, where publication happens, is what the terms record promises.
- A `--terms-date` flag: it proves nothing a reader of `docs/terms.md` could not type.

## Design review (2026-10-29, Opus; my waiver covers all q15 reviews, Fable over its limit)

Accepted, all thirteen: the regional origin and empty identity; the bucket-name guard before `--delete`; cfn-lint for il-central-1; the terms-date flag dropped; content types set, not guessed; an allowlist upload; the 403 noted; `'/*'` quoted; tag-stripped scanning; the footer's test and anti-goal; a takedown command; one scan, not two; the PUT basis. The unverified list was closed against cfn-lint's schema and AWS's pricing and invalidation pages.

## Deviations

- **The phrase check scans `.css` and `.js` as well as `.html`**: the upload sends all three, and a script can put text on the page.
- **CSS and JavaScript also carry `charset=utf-8`**: harmless for today's ASCII files, right if one ever holds Hebrew.
- **An in-process test for the check's entry point**: the subprocess tests prove `python -m timeline.check` works, but coverage cannot see inside them (70% on `check.py` until the in-process test).
- **Code review (2026-10-29, Opus; my waiver covers q15)**, nothing blocking; fixed: the check also reads each file as written, so attribute text and a script's `<` comparison can no longer hide a phrase; `publish.sh` refuses a folder whose path holds `[`, `]`, `?` or `*` (the CLI matches its filters against the full path with fnmatch: a `[ ]` pair makes the allowlist match nothing, and unmatched files upload; `?` and `*` still match themselves and are refused to be safe); `SITE_DIR` is read from where the script was run, and a missing folder stops it; the tests run the script from another folder, so its `cd` is exercised; pages carry `Cache-Control: max-age=300`, so a browser shows an upload within minutes (CloudFront then also keeps them five minutes: a few more S3 GETs, under a cent); `docs/terms.md` no longer says the footer and the real-site scan are still to come.
- **Re-review of those fixes (Opus)**, nothing blocking; fixed: tags are stripped in scripts too, so markup inside a script string cannot hide a phrase (the first fix had narrowed stripping to pages); the default folder (`<repo>/site` with no `SITE_DIR`) has a test run from another folder; the comments now say only a `[ ]` pair breaks the filters.
- **The check also requires the source line and the unofficial line on every page** (my call, 2026-10-29, beyond the reviewed design): `missing_notices` in `src/timeline/check.py` reads both from their constants (then `ATTRIBUTION` and `UNOFFICIAL`), so a site built before the footer change, which still has its marker and no banned phrase, cannot be uploaded. Since the redesign (q18) it wants `SOURCE_SHORT` and `UNOFFICIAL` (`src/timeline/words.py`) on every page and the full `ATTRIBUTION` on `how-it-works.html` (checked when that page is there; the build always writes it), and `scan` refuses the built-by placeholder, so nothing could go out before I wrote that line.
- **The first deploy failed on account verification** (2026-10-29 20:50Z): CloudFront refuses new distributions until AWS Support verifies the account; the stack rolled back cleanly. AWS's answer (2026-10-30): the account needed a valid payment method; once I added one, the record was deleted (a stack in ROLLBACK_COMPLETE cannot be updated) and the redeploy succeeded.
