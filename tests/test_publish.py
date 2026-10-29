"""scripts/publish.sh, run against a fake `aws` that records its calls instead of touching AWS (docs/publishing.md)."""
import os
import stat
import subprocess
import sys
from pathlib import Path

import shutil

import pytest

from model.report import ATTRIBUTION
from timeline.pages import UNOFFICIAL

SCRIPT = Path(__file__).parent.parent / "scripts" / "publish.sh"
OURS = "arn:aws:iam::137953273942:user/doron-admin"
SITE_BUCKET = "flights-archive-site-sitebucket-abc123"
ARCHIVE_BUCKET = "flights-archive-archivebucket-onpwo5ns74tw"
AWS_FLAGS = ["--profile", "flights-sam", "--region", "il-central-1"]


def make_site(tmp_path, page="<p>First observed CANCELED on the public board</p>", marker=True, name="site"):
    site = tmp_path / name
    (site / "day").mkdir(parents=True)
    footer = f"<footer><p>{ATTRIBUTION}</p><p>{UNOFFICIAL}</p></footer>"
    (site / "index.html").write_text("<p>index</p>" + footer)
    (site / "day" / "2026-10-28.html").write_text(page + footer)
    (site / "style.css").write_text("p{}")
    (site / "search.js").write_text("// search")
    (site / ".DS_Store").write_text("finder")
    if marker:
        (site / ".timeline-site").write_text("Made by timeline.build; replaced whole on every build.\n")
    return site


def run_publish(tmp_path, site, arn=OURS, bucket=SITE_BUCKET, distribution="E2EXAMPLE", cwd=None, script=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    fake = bin_dir / "aws"
    fake.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\t' \"$@\" >> '{log}'; echo >> '{log}'\n"
        'case "$*" in\n'
        f'  sts*) echo "{arn}";;\n'
        f'  *SiteBucketName*) echo "{bucket}";;\n'
        f'  *SiteDistributionId*) echo "{distribution}";;\n'
        '  *SiteDomainName*) echo "d111111abcdef8.cloudfront.net";;\n'
        "esac\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", PYTHON=sys.executable)
    env.pop("SITE_DIR", None)
    if site is not None:
        env["SITE_DIR"] = str(site)
    done = subprocess.run(["sh", str(script or SCRIPT)], env=env, capture_output=True, text=True, cwd=cwd or tmp_path)
    calls = [line.rstrip("\t").split("\t") for line in log.read_text().splitlines()] if log.exists() else []
    return done, calls


def writes(calls):
    return [c for c in calls if c[:2] in (["s3", "sync"], ["cloudfront", "create-invalidation"]) or c[0] == "s3"]


def test_checks_then_uploads_each_type_with_its_content_type_then_invalidates(tmp_path):
    site = make_site(tmp_path)
    done, calls = run_publish(tmp_path, site)
    assert done.returncode == 0, done.stderr
    assert [c[:2] for c in calls] == [["sts", "get-caller-identity"], ["cloudformation", "describe-stacks"],
                                      ["cloudformation", "describe-stacks"], ["s3", "sync"], ["s3", "sync"],
                                      ["s3", "sync"], ["cloudfront", "create-invalidation"],
                                      ["cloudformation", "describe-stacks"]]
    syncs = [c for c in calls if c[:2] == ["s3", "sync"]]
    for call, (pattern, ctype) in zip(syncs, [("*.html", "text/html; charset=utf-8"), ("*.css", "text/css; charset=utf-8"),
                                              ("*.js", "text/javascript; charset=utf-8")]):
        assert call == ["s3", "sync", f"{site}/", f"s3://{SITE_BUCKET}/", "--delete", "--exclude", "*",
                        "--include", pattern, "--content-type", ctype, "--cache-control", "max-age=300", *AWS_FLAGS]
    invalidation = calls[6]
    assert invalidation[invalidation.index("--distribution-id") + 1] == "E2EXAMPLE"
    assert invalidation[invalidation.index("--paths") + 1] == "/*"  # literal: unquoted, sh expands it to /bin /etc ...
    assert all("--profile" in c and c[c.index("--profile") + 1] == "flights-sam" for c in calls)
    assert "https://d111111abcdef8.cloudfront.net/" in done.stdout


def test_another_account_uploads_nothing(tmp_path):
    done, calls = run_publish(tmp_path, make_site(tmp_path), arn="arn:aws:iam::999999999999:user/someone")
    assert done.returncode != 0 and "nothing uploaded" in done.stderr
    assert [c[:2] for c in calls] == [["sts", "get-caller-identity"]]


def test_a_folder_without_the_build_marker_uploads_nothing(tmp_path):
    done, calls = run_publish(tmp_path, make_site(tmp_path, marker=False))
    assert done.returncode != 0 and "marker" in done.stderr
    assert writes(calls) == [] and [c[0] for c in calls] == ["sts"]


def test_a_banned_phrase_uploads_nothing(tmp_path):
    done, calls = run_publish(tmp_path, make_site(tmp_path, page="<p>cancelled <b>at</b> 10:00</p>"))
    assert done.returncode != 0 and "cancelled at" in done.stderr
    assert writes(calls) == [] and [c[0] for c in calls] == ["sts"]


@pytest.mark.parametrize("bucket", [ARCHIVE_BUCKET, "None", "", "flights-archive-site-sitebucket-"])
def test_only_a_site_bucket_is_ever_synced_to(tmp_path, bucket):
    done, calls = run_publish(tmp_path, make_site(tmp_path), bucket=bucket)
    assert done.returncode != 0 and "nothing uploaded" in done.stderr
    assert writes(calls) == []


@pytest.mark.parametrize("distribution", ["None", ""])
def test_a_missing_distribution_uploads_nothing(tmp_path, distribution):
    done, calls = run_publish(tmp_path, make_site(tmp_path), distribution=distribution)
    assert done.returncode != 0 and "nothing uploaded" in done.stderr
    assert writes(calls) == []


def test_a_relative_site_folder_is_read_from_where_the_script_was_run(tmp_path):
    site = make_site(tmp_path)
    done, calls = run_publish(tmp_path, "site", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    assert [c[2] for c in calls if c[:2] == ["s3", "sync"]] == [f"{site}/"] * 3


def test_a_missing_site_folder_uploads_nothing(tmp_path):
    done, calls = run_publish(tmp_path, tmp_path / "nowhere")
    assert done.returncode != 0 and "nothing uploaded" in done.stderr
    assert calls == []


@pytest.mark.parametrize("name", ["site [v2]", "site?", "site*"])
def test_a_folder_path_the_upload_filters_would_misread_uploads_nothing(tmp_path, name):
    # aws s3 sync matches --exclude/--include against the full local path with fnmatch: a [ ] pair makes
    # the allowlist match nothing, and unmatched files are uploaded; ? and * are refused to be safe.
    done, calls = run_publish(tmp_path, make_site(tmp_path, name=name))
    assert done.returncode != 0 and "nothing uploaded" in done.stderr
    assert writes(calls) == []


def test_without_site_dir_the_repo_site_folder_is_used_wherever_the_script_is_run_from(tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / "publish.sh")
    (repo / "src").symlink_to(SCRIPT.parent.parent / "src")
    site = make_site(repo)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    done, calls = run_publish(tmp_path, None, cwd=elsewhere, script=repo / "scripts" / "publish.sh")
    assert done.returncode == 0, done.stderr
    assert [c[2] for c in calls if c[:2] == ["s3", "sync"]] == [f"{site}/"] * 3
