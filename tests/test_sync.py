"""scripts/sync.sh, run against a fake `aws` that records its calls instead of touching AWS."""
import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "sync.sh"
OURS = "arn:aws:iam::137953273942:user/doron-admin"


def run_sync(tmp_path, arn):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    fake = bin_dir / "aws"
    fake.write_text(f'#!/bin/sh\necho "$*" >> "{log}"\ncase "$1" in sts) echo "{arn}";; esac\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    done = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return done, calls


def test_checks_the_identity_then_syncs_receipts_before_raw(tmp_path):
    done, calls = run_sync(tmp_path, OURS)
    assert done.returncode == 0, done.stderr
    assert [c.split()[:2] for c in calls] == [["sts", "get-caller-identity"], ["s3", "sync"], ["s3", "sync"]]
    assert "s3://flights-archive-archivebucket-onpwo5ns74tw/receipts/" in calls[1].split()
    assert "s3://flights-archive-archivebucket-onpwo5ns74tw/raw/" in calls[2].split()
    assert all("--profile flights-sam" in c for c in calls)


def test_wrong_identity_syncs_nothing(tmp_path):
    done, calls = run_sync(tmp_path, "arn:aws:iam::111111111111:user/someone-else")
    assert done.returncode != 0 and "137953273942" in done.stderr
    assert [c for c in calls if c.startswith("s3")] == []
