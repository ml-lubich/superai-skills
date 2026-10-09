"""install.sh: syntax, dry-run, call order, idempotency, no personal strings."""

import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "install.sh")

STUB = '#!/bin/sh\necho "$(basename "$0") $*" >> "$STUB_LOG"\n'
GIT_STUB = (
    STUB
    + 'if [ "$1" = clone ]; then for a; do d=$a; done; mkdir -p "$d/.git"; fi\n'
)


@pytest.fixture
def env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in (("uv", STUB), ("git", GIT_STUB), ("superai-skills", STUB)):
        p = bindir / name
        p.write_text(body)
        p.chmod(0o755)
    log = tmp_path / "calls.log"
    log.touch()
    e = {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "SUPERAI_HOME": str(tmp_path / "home" / "dev" / "superai-skills"),
        "STUB_LOG": str(log),
        "SUPERAI_TTY": str(tmp_path / "fake-tty"),
    }
    (tmp_path / "fake-tty").write_text("")
    return e, log


def run(e, *args):
    return subprocess.run(
        ["sh", SCRIPT, *args], env=e, capture_output=True, text=True, timeout=30
    )


def calls(log):
    return log.read_text().splitlines()


def test_syntax_ok():
    assert subprocess.run(["sh", "-n", SCRIPT]).returncode == 0


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck not installed")
def test_shellcheck_clean():
    assert subprocess.run(["shellcheck", "-s", "sh", SCRIPT]).returncode == 0


def test_dry_run_prints_steps_runs_nothing(env):
    e, log = env
    r = run(e, "--dry-run")
    assert r.returncode == 0, r.stderr
    for step in ("clone", "uv tool install", "superai-skills init"):
        assert step in r.stdout
    assert calls(log) == []
    assert not os.path.exists(e["SUPERAI_HOME"])


def test_call_order_fresh_then_idempotent(env):
    e, log = env
    r = run(e, "--bitbucket")
    assert r.returncode == 0, r.stderr
    c = calls(log)
    assert c[0].startswith("git clone --recurse-submodules")
    assert c[1].startswith("uv tool install --editable")
    assert c[2] == "superai-skills init --bitbucket"
    log.write_text("")
    r = run(e)
    assert r.returncode == 0, r.stderr
    c = calls(log)
    assert not any(x.startswith("git clone") for x in c)
    assert any("pull" in x for x in c)
    assert any("submodule update" in x for x in c)
    assert c[-1] == "superai-skills init"


def test_no_tty_runs_init_no_input(env):
    e, log = env
    e["SUPERAI_TTY"] = "/nonexistent/tty"
    r = run(e, "--only", "skills")
    assert r.returncode == 0, r.stderr
    assert calls(log)[-1] == "superai-skills init --only skills --no-input"


def test_dry_run_passes_flags_in_plan(env):
    e, log = env
    r = run(e, "--dry-run", "--yes")
    assert "superai-skills init --dry-run --yes" in r.stdout
    assert calls(log) == []


def test_no_personal_strings():
    deny = os.environ.get("SUPERAI_DENYLIST", "/Users/mlubich/dev/.open-brain-denylist.txt")
    if not os.path.exists(deny):
        pytest.skip("denylist file not present")
    words = [w.strip() for w in open(deny).read().splitlines() if w.strip()]
    # the clone URL of this (already public) repo is the one allowed handle hit
    text = open(SCRIPT).read().replace("ml-lubich/superai-skills", "")
    assert not re.search("|".join(re.escape(w) for w in words), text, re.I)


def test_local_bin_on_path_when_uv_preinstalled(env, tmp_path):
    """uv already on PATH elsewhere, ~/.local/bin absent from PATH: init must still resolve."""
    e, log = env
    home = tmp_path / "home"
    lb = home / ".local" / "bin"
    lb.mkdir(parents=True)
    # tool install drops superai-skills into ~/.local/bin; remove it from the PATH stub dir
    src = tmp_path / "bin" / "superai-skills"
    shutil.move(str(src), str(lb / "superai-skills"))
    r = run(e)
    assert r.returncode == 0, r.stderr
    assert calls(log)[-1] == "superai-skills init"
    assert "update-shell" in r.stdout
