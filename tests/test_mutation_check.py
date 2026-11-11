"""The mutation check's runner (`scripts/mutation_check.py`): what counts as caught, and its time limit.

A mutation is caught only when pytest says a test failed (exit 1). Any other exit means pytest could not run the tests
as asked: a test file or id that no longer exists (4), a module that no longer imports (2), no tests collected (5), or
pytest killed by a signal. That proves nothing about the rule, so it is an ERROR, not a catch, and it fails the check.
A run past the time limit is killed with everything it started and counts as caught: a break that makes a test hang
is one the tests noticed (without the limit, the check itself would hang on it). The runs write no bytecode: a cached
.pyc could run the last mutation's code. `main` is driven first with a fake `run_limited` whose answer the mutated file
sets, over a file of the test's own, so no real mutation runs; the last tests run real processes and real pytest, with
a time limit of a second where one is hit.
"""
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "mutation_check.py"
HANG = "hang"


def load():
    spec = importlib.util.spec_from_file_location("mutation_check_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check():
    return load()


@pytest.mark.parametrize("code, verdict", [(0, "MISSED"), (1, "CAUGHT"), (2, "ERROR"), (3, "ERROR"), (4, "ERROR"),
                                           (5, "ERROR"), (6, "ERROR"), (-9, "ERROR")])
def test_only_a_test_failure_counts_as_caught(check, code, verdict):
    assert check.verdict(code) == verdict


def fake_run(rule: Path, seen: list):
    """A stand-in for run_limited: the mutated `rule` file holds pytest's exit code, or `hang` for a run past the
    limit (run_limited's None). `seen` records each run's file and the limit it was given."""
    def run(args, limit, **kwargs):
        text = rule.read_text()
        seen.append((text, limit))
        value = text.split("=")[1].strip()
        if value == HANG:
            return None
        return subprocess.CompletedProcess(args, int(value), stdout="1 failed\n", stderr="ERROR: not found\n")
    return run


def mutations(**codes):
    return {name: (("rule.py", ["tests/test_rule.py"]), "LIMIT = 0", f"LIMIT = {code}") for name, code in codes.items()}


@pytest.fixture
def rule(check, tmp_path, monkeypatch):
    path = tmp_path / "rule.py"
    path.write_text("LIMIT = 0\n")
    monkeypatch.setattr(check, "ROOT", tmp_path)
    return path


def test_main_reports_each_mutation_by_how_its_run_ended_and_restores_the_file(check, rule, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1, hung=HANG, missed=0, renamed=4, unimportable=2,
                                                      killed=-9))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, seen))
    assert check.main([]) == 1
    # each run sees its own break (the one after a time-out too), and each runs under the limit
    assert seen == [(f"LIMIT = {code}\n", check.TIME_LIMIT) for code in (1, HANG, 0, 4, 2, -9)]
    assert rule.read_text() == "LIMIT = 0\n"
    assert capsys.readouterr().out.splitlines() == [
        "CAUGHT caught",
        f"TIMEOUT hung: pytest ran past the {check.TIME_LIMIT:g} s limit and was killed; counted as caught",
        "MISSED missed",
        "ERROR  renamed: pytest exited 4 (USAGE_ERROR), not a test failure: ERROR: not found",
        "ERROR  unimportable: pytest exited 2 (INTERRUPTED), not a test failure: ERROR: not found",
        # a pytest killed by a signal (the out-of-memory killer's -9) exits with a code pytest does not define
        "ERROR  killed: pytest exited -9 (not pytest's), not a test failure: ERROR: not found",
        "Files restored. Missed: ['missed'] Errors: ['renamed', 'unimportable', 'killed']"
        " Timed out, counted as caught: ['hung']",
    ]


def test_an_error_alone_fails_the_check(check, rule, monkeypatch, capsys):
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1, renamed=4))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, []))
    assert check.main([]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "Files restored. Errors: ['renamed']"


def test_every_mutation_caught_passes(check, rule, monkeypatch, capsys):
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=1, second=1))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, []))
    assert check.main([]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Files restored. Every mutation was caught."


def test_a_time_out_counts_as_caught(check, rule, monkeypatch, capsys):
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=1, hung=HANG))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, []))
    assert check.main([]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == ("Files restored. Every mutation was caught."
                                                        " Timed out, counted as caught: ['hung']")


def test_main_runs_pytest_in_the_repo_writing_no_bytecode(check, rule, monkeypatch):
    """Python trusts a cached .pyc whose source has the same size and the same whole-second mtime, so with bytecode
    written, a same-size break made within a second of the last one could run the last one's code, and be judged by
    its result. The variable is cleared here first: the check sets it for the runs it makes, this test among them."""
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    given = []

    def run(args, limit, **popen):
        given.append(popen)
        return subprocess.CompletedProcess(args, 1, "", "")
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1))
    monkeypatch.setattr(check, "run_limited", run)
    check.main([])
    assert given == [{"cwd": check.ROOT, "env": os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}}]


# What pytest 9.2.0 prints with the check's flags (-q -x -p no:cacheprovider), measured 2026-11-11 (paths shortened).
NO_TESTS_RAN = "\nno tests ran in 0.02s\n"
MODULE_NOT_FOUND = ("tests/test_rule.py:1: in <module>\n    import rule\nE   ModuleNotFoundError: No module named 'rule'\n"
                    "=========================== short test summary info ============================\n"
                    "ERROR tests/test_rule.py\n!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                    "!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n1 error in 0.09s\n")
SYNTAX_ERROR = ("tests/test_rule.py:2: in <module>\n    import rule\n"
                'E     File "/tmp/rule.py", line 1\nE       LIMIT = = 0\nE               ^\nE   SyntaxError: invalid syntax\n'
                "=========================== short test summary info ============================\n"
                "ERROR tests/test_rule.py\n!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n"
                "1 error in 0.12s\n")


@pytest.mark.parametrize("stdout, stderr, shown", [
    (NO_TESTS_RAN, "ERROR: not found: /tmp/tests/test_rule.py::test_gone\n(no match in any of [<Module test_rule.py>])\n",
     "ERROR: not found: /tmp/tests/test_rule.py::test_gone"),  # a test id that no longer exists (4)
    (NO_TESTS_RAN, "ERROR: file or directory not found: tests/test_gone.py\n",
     "ERROR: file or directory not found: tests/test_gone.py"),  # a test file that no longer exists (4)
    (MODULE_NOT_FOUND, "", "E   ModuleNotFoundError: No module named 'rule'"),  # a module that does not import (2)
    (SYNTAX_ERROR, "", "E   SyntaxError: invalid syntax"),  # several E lines: the last names the exception (2)
    (NO_TESTS_RAN, "", "no tests ran in 0.02s"),  # no tests collected (5): nothing names a cause, so the last line
    ("", "", "(no output)"),  # a pytest killed before it printed anything
])
def test_an_error_shows_the_line_that_names_its_cause(check, stdout, stderr, shown):
    """The cause is pytest's last `E ` line (a collection error's exception; the `ERROR` line after it names only the
    file), else its last `ERROR` line (a test file or id not found), else its last line."""
    assert check._telling_line(subprocess.CompletedProcess([], 4, stdout=stdout, stderr=stderr)) == shown


# Real processes from here on.

def test_a_run_within_the_limit_returns_its_exit_code_and_output(check):
    run = check.run_limited([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"],
                            30)
    assert (run.returncode, run.stdout, run.stderr) == (3, "out\n", "err\n")


# A process that starts one of its own (as a test that runs a shell script does), writes that one's pid, and hangs.
HANGS_WITH_A_CHILD = ("import subprocess, sys, time\n"
                      "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
                      "open(sys.argv[1], 'w').write(str(child.pid))\n"
                      "time.sleep(20)\n")


def gone(pid: int, within: float = 5.0) -> bool:
    """True once no process `pid` is left; a killed process whose parent died is reaped by init, not at once."""
    end = time.monotonic() + within
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def test_a_run_past_the_limit_is_killed_with_everything_it_started(check, tmp_path):
    pidfile = tmp_path / "child.pid"
    started = time.monotonic()
    assert check.run_limited([sys.executable, "-c", HANGS_WITH_A_CHILD, str(pidfile)], 1.0) is None
    assert time.monotonic() - started < 10  # the limit, not the 20 s it would hang
    child = int(pidfile.read_text())
    try:
        assert gone(child)
    finally:
        try:
            os.kill(child, signal.SIGKILL)  # leave nothing running, whatever the outcome
        except ProcessLookupError:
            pass


def real_rule(tmp_path: Path) -> None:
    """A rule and a test of it, as the repo would have them."""
    (tmp_path / "rule.py").write_text("LIMIT = 0\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_rule.py").write_text("import rule\n\n\ndef test_limit():\n    assert rule.LIMIT == 0\n")


def test_main_over_real_pytest_tells_a_failing_test_from_a_run_that_proves_nothing(check, tmp_path, monkeypatch, capsys):
    """A stale test id (4) and a break that stops the module importing (2) were counted as caught before; real pytest,
    run as the check runs it, shows each for what it is, and writes no bytecode (the variable cleared here first, as
    the check sets it for the runs it makes, this test among them)."""
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    real_rule(tmp_path)
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", {
        "fails": (("rule.py", ["tests/test_rule.py"]), "LIMIT = 0", "LIMIT = 1"),
        "renamed": (("rule.py", ["tests/test_rule.py::test_gone"]), "LIMIT = 0", "LIMIT = 1"),
        "unimportable": (("rule.py", ["tests/test_rule.py"]), "LIMIT = 0", "LIMIT = = 0"),
    })
    assert check.main([]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "CAUGHT fails"
    assert lines[1].startswith("ERROR  renamed: pytest exited 4 (USAGE_ERROR), not a test failure: ERROR: not found: ")
    assert lines[2] == "ERROR  unimportable: pytest exited 2 (INTERRUPTED), not a test failure: E   SyntaxError: invalid syntax"
    assert lines[3] == "Files restored. Errors: ['renamed', 'unimportable']"
    assert (tmp_path / "rule.py").read_text() == "LIMIT = 0\n"
    assert not list(tmp_path.rglob("__pycache__"))  # no bytecode written, of the rule or of its test


def test_main_over_real_pytest_stops_a_hung_run_at_the_limit(check, tmp_path, monkeypatch, capsys):
    real_rule(tmp_path)
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "TIME_LIMIT", 1)
    monkeypatch.setattr(check, "MUTATIONS", {
        "hangs": (("rule.py", ["tests/test_rule.py"]), "LIMIT = 0", "import time\ntime.sleep(20)\nLIMIT = 0"),
    })
    started = time.monotonic()
    assert check.main([]) == 0
    assert time.monotonic() - started < 15  # the limit, not the 20 s it would hang
    assert capsys.readouterr().out.splitlines() == [
        "TIMEOUT hangs: pytest ran past the 1 s limit and was killed; counted as caught",
        "Files restored. Every mutation was caught. Timed out, counted as caught: ['hangs']",
    ]
    assert (tmp_path / "rule.py").read_text() == "LIMIT = 0\n"
