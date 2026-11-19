"""scripts/deploy_nightly.sh, run against a fake `aws` and a fake `sam` that record their calls instead of touching
AWS (docs/nightly-model.md, section 5: "Two ways a deploy could reach the collector, both closed by the deploy
script"). Each fake appends its name, the folder it ran in and its arguments, tab-separated, to a log."""
import os
import select
import shutil
import signal
import stat
import subprocess
import termios
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "deploy_nightly.sh"
MODEL_STACK = (ROOT / "model-stack").resolve()
OURS = "arn:aws:iam::137953273942:user/doron-admin"
ADDRESS = "https://hc-ping.com/abc"
PROMPT = "healthchecks.io ping address for the model check:"
IDENTITY = ["aws", "sts", "get-caller-identity", "--profile", "flights-sam", "--query", "Arn", "--output", "text"]
BUILD = ["sam", "build", "--template-file", "template.yaml", "--build-dir", ".aws-sam/build"]


def deploy(state):
    return ["sam", "deploy", "--template-file", ".aws-sam/build/template.yaml", "--stack-name", "flights-archive-model",
            "--profile", "flights-sam", "--region", "il-central-1", "--capabilities", "CAPABILITY_IAM", "--resolve-s3",
            "--confirm-changeset", "--parameter-overrides",
            "ArchiveBucketName=flights-archive-archivebucket-onpwo5ns74tw", f"HealthcheckUrl={ADDRESS}",
            f"ScheduleState={state}"]


def fakes(tmp_path, arn=OURS):
    """A fake `aws` and `sam` in tmp_path/bin; returns the environment that puts them first and the log's path. At a
    terminal, the fake `sam` also notes in tmp_path/echo.log whether the terminal echoes what is typed."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    echo_log = tmp_path / "echo.log"
    echoes = (f"if [ -t 0 ]; then if stty -a | tr ' ' '\\n' | grep -qx echo; then echo on; else echo off; fi"
              f" >> '{echo_log}'; fi\n")
    for name, answer in [("aws", f'case "$1" in sts) echo "{arn}";; esac\n'), ("sam", echoes)]:
        fake = bin_dir / name
        fake.write_text("#!/bin/sh\n"
                        f"printf '%s\\t' {name} \"$(pwd -P)\" \"$@\" >> '{log}'; echo >> '{log}'\n" + answer)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}"), log


def read_calls(log):
    """Each call as (folder it ran in, [name, *arguments])."""
    if not log.exists():
        return []
    calls = []
    for line in log.read_text().splitlines():
        name, folder, *arguments = line.split("\t")[:-1]
        calls.append((Path(folder).resolve(), [name, *arguments]))
    return calls


def run_deploy(tmp_path, *arguments, arn=OURS, typed=ADDRESS + "\n", cwd=ROOT, script=SCRIPT):
    """The script as the owner runs it, from the repository root unless told otherwise, the address on stdin."""
    env, log = fakes(tmp_path, arn)
    done = subprocess.run(["sh", str(script), *arguments], env=env, input=typed, capture_output=True, text=True,
                          cwd=cwd, timeout=60)
    return done, read_calls(log)


def test_checks_then_builds_then_deploys(tmp_path):
    done, calls = run_deploy(tmp_path)
    assert done.returncode == 0, done.stderr
    assert [call for _, call in calls] == [IDENTITY, BUILD, deploy("DISABLED")]
    assert [folder for folder, call in calls if call[0] == "sam"] == [MODEL_STACK, MODEL_STACK]
    assert PROMPT in done.stderr


def test_enabled_reaches_the_schedule_state(tmp_path):
    done, calls = run_deploy(tmp_path, "ENABLED")
    assert done.returncode == 0, done.stderr
    assert [call for _, call in calls] == [IDENTITY, BUILD, deploy("ENABLED")]


def test_another_account_deploys_nothing(tmp_path):
    done, calls = run_deploy(tmp_path, arn="arn:aws:iam::999999999999:user/someone")
    assert done.returncode == 1 and done.stderr.rstrip().endswith("nothing deployed")
    assert [call for _, call in calls] == [IDENTITY]


@pytest.mark.parametrize("arguments", [["enabled"], ["--stack-name", "flights-archive"], ["ENABLED", "extra"]])
def test_an_unknown_argument_deploys_nothing(tmp_path, arguments):
    done, calls = run_deploy(tmp_path, *arguments)
    assert done.returncode == 1 and done.stderr.rstrip().endswith("nothing deployed")
    assert calls == []


def test_a_samconfig_naming_another_stack_deploys_nothing(tmp_path):
    """The folder's samconfig.toml is what a sam command typed there follows: one aimed at the collector's stack is
    refused before anything runs, wherever the script's copy sits."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "model-stack").mkdir()
    shutil.copy(SCRIPT, repo / "scripts" / "deploy_nightly.sh")
    (repo / "model-stack" / "samconfig.toml").write_text(
        (ROOT / "model-stack" / "samconfig.toml").read_text().replace(
            'stack_name = "flights-archive-model"', 'stack_name = "flights-archive"'))
    done, calls = run_deploy(tmp_path, script=repo / "scripts" / "deploy_nightly.sh")
    assert done.returncode == 1 and done.stderr.rstrip().endswith("nothing deployed")
    assert calls == []


@pytest.mark.parametrize("typed", ["\n", "", "https://healthchecks.io/projects/x\n"],
                         ids=["an empty line", "no line at all", "the project's page"])
def test_a_wrong_address_deploys_nothing(tmp_path, typed):
    done, calls = run_deploy(tmp_path, typed=typed)
    assert done.returncode == 1 and done.stderr.rstrip().endswith("nothing deployed")
    assert [call for _, call in calls] == [IDENTITY]
    if typed.strip():
        assert typed.strip() not in done.stdout + done.stderr


def test_the_address_is_never_printed(tmp_path):
    done, calls = run_deploy(tmp_path)
    assert done.returncode == 0, done.stderr
    assert ADDRESS not in done.stdout and ADDRESS not in done.stderr
    assert "hc-ping.com/abc" not in done.stdout + done.stderr


def test_it_runs_from_anywhere(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    done, calls = run_deploy(tmp_path, cwd=elsewhere)
    assert done.returncode == 0, done.stderr
    assert [(folder, call[:2]) for folder, call in calls if call[0] == "sam"] == [
        (MODEL_STACK, ["sam", "build"]), (MODEL_STACK, ["sam", "deploy"])]


# At a terminal. The tests above give the address on a pipe, where nothing is ever echoed; at the owner's terminal the
# echo is the one place it could show. These run the script with a pseudo-terminal as its standard input.

def echo_on(fd):
    return bool(termios.tcgetattr(fd)[3] & termios.ECHO)


def wait_for(stream, text, seconds=20):
    """Read `stream` until `text` has appeared; what was read so far."""
    seen = b""
    deadline = time.monotonic() + seconds
    while text.encode() not in seen:
        left = deadline - time.monotonic()
        assert left > 0, f"no {text!r} within {seconds} s: {seen!r}"
        ready, _, _ = select.select([stream], [], [], left)
        if ready:
            chunk = os.read(stream.fileno(), 4096)
            assert chunk, f"the script closed its output before {text!r}: {seen!r}"
            seen += chunk
    return seen


def drained(fd):
    """What the terminal has sent back so far: its echo."""
    out = b""
    while select.select([fd], [], [], 0.2)[0]:
        try:
            chunk = os.read(fd, 4096)
        except OSError:  # Linux answers EIO once nothing holds the other end
            break
        if not chunk:
            break
        out += chunk
    return out


def run_at_a_terminal(tmp_path, interrupt=False):
    env, log = fakes(tmp_path)
    terminal, script_end = os.openpty()
    try:
        assert echo_on(script_end)  # a new terminal echoes: without the script's stty, the address would show
        with subprocess.Popen(["sh", str(SCRIPT)], stdin=script_end, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=env, cwd=ROOT) as process:
            try:
                wait_for(process.stderr, PROMPT)
                if interrupt:
                    process.send_signal(signal.SIGINT)
                else:
                    os.write(terminal, (ADDRESS + "\n").encode())
                process.wait(timeout=30)
                echoed = drained(terminal)
                restored = echo_on(script_end)
            finally:
                if process.poll() is None:
                    process.kill()
        return process.returncode, echoed, restored, read_calls(log)
    finally:
        os.close(terminal)
        os.close(script_end)


def test_at_a_terminal_the_address_is_not_echoed_and_echo_comes_back(tmp_path):
    code, echoed, restored, calls = run_at_a_terminal(tmp_path)
    assert code == 0
    assert b"hc-ping.com" not in echoed
    assert restored
    assert [call for _, call in calls] == [IDENTITY, BUILD, deploy("DISABLED")]
    # back on before sam runs: sam deploy asks for a keypress before it applies the change set
    assert (tmp_path / "echo.log").read_text().split() == ["on", "on"]


def test_an_interrupt_at_the_prompt_turns_echo_back_on_and_deploys_nothing(tmp_path):
    code, _, restored, calls = run_at_a_terminal(tmp_path, interrupt=True)
    assert code != 0
    assert restored
    assert [call for _, call in calls] == [IDENTITY]
