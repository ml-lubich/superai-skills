import subprocess

import pytest
from click.testing import CliRunner

from super_ai_skills import init as init_mod
from super_ai_skills.cli import cli

STEP_FNS = ["_brew", "_bb", "_ai_clis", "_p10k", "_iterm2", "_plugins", "_tools", "_skills", "_brain", "_doctor"]


@pytest.fixture
def stub_steps(monkeypatch):
    """Replace every real runner; build_steps resolves them at call time, so patch the module."""
    calls = []
    for name in STEP_FNS:
        monkeypatch.setattr(
            init_mod, name,
            lambda dry_run=False, *a, _n=name, **k: calls.append(_n) or init_mod.Result(_n, "ok"),
        )
    monkeypatch.setattr(init_mod, "_call", lambda m, f, d: calls.append(f) or init_mod.Result(f, "ok"))
    monkeypatch.setattr(init_mod, "detect_bitbucket_here", lambda: False)
    return calls


# --- detection (pure) -------------------------------------------------
@pytest.mark.parametrize("remotes,env,cfg,want", [
    (["origin\thttps://bitbucket.org/a/b.git (fetch)"], {}, False, True),
    (["origin\tgit@bitbucket.org:a/b.git (push)"], {}, False, True),
    ([], {"BITBUCKET_TOKEN": "x"}, False, True),
    ([], {"BITBUCKET_URL": "x"}, False, True),
    ([], {"BB_WORKSPACE": "x"}, False, True),
    ([], {}, True, True),
    (["origin\thttps://github.com/a/b.git (fetch)"], {"HOME": "/h"}, False, False),
    ([], {}, False, False),
])
def test_detect_table(remotes, env, cfg, want):
    assert init_mod.detect_bitbucket(remotes, env, cfg) is want


def test_flag_overrides_detection():
    assert init_mod.resolve_bitbucket(True, False) is True
    assert init_mod.resolve_bitbucket(False, True) is False
    assert init_mod.resolve_bitbucket(None, True) is True
    assert init_mod.resolve_bitbucket(None, False) is False


def test_git_urls_handles_gitfile_worktree(tmp_path):
    real = tmp_path / "main" / ".git"
    (real / "worktrees" / "w").mkdir(parents=True)
    (real / "config").write_text('[remote "origin"]\n\turl = git@bitbucket.org:a/b.git\n')
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {real / 'worktrees' / 'w'}\n")
    (real / "worktrees" / "w" / "commondir").write_text("../..\n")
    assert any("bitbucket" in u for u in init_mod._git_urls(wt))


def test_git_urls_handles_submodule_gitfile(tmp_path):
    gd = tmp_path / "super" / ".git" / "modules" / "sub"
    gd.mkdir(parents=True)
    (gd / "config").write_text("[remote \"origin\"]\n\turl = https://bitbucket.org/a/b\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / ".git").write_text(f"gitdir: {gd}\n")
    assert any("bitbucket" in u for u in init_mod._git_urls(sub))


def test_plugins_flag_passed_through(monkeypatch):
    seen = []
    monkeypatch.setattr(init_mod, "run_init", lambda *a, **k: seen.append(a[4]) or [])
    for args, want in ((["--plugins", "all"], "all"), ([], "default")):
        assert CliRunner().invoke(cli, ["init", *args]).exit_code == 0
        assert seen[-1] == want
    assert CliRunner().invoke(cli, ["init", "--plugins", "bogus"]).exit_code != 0


def test_run_init_plugins_tier_reaches_step(monkeypatch):
    seen = []
    monkeypatch.setattr("super_ai_skills.plugins.install_plugins",
                        lambda tier, dry_run: seen.append(tier) or [])
    r = init_mod._plugins(True, "all")
    assert seen == ["all"] and r.status == "dry-run"


# --- CLI ---------------------------------------------------------------
def test_help_flags():
    r = CliRunner()
    for flag in ("-h", "--help"):
        out = r.invoke(cli, ["init", flag])
        assert out.exit_code == 0 and "--dry-run" in out.output
        assert r.invoke(cli, [flag]).exit_code == 0


def test_dry_run_prints_every_step_and_runs_no_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("subprocess used in dry-run")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(init_mod, "_call", lambda m, f, d: init_mod.Result(f, "dry-run"))
    out = CliRunner().invoke(cli, ["init", "--dry-run", "--bitbucket"])
    assert out.exit_code == 0, out.output
    for word in ("brew", "bb", "ai-clis", "plugins", "tools", "skills", "brain", "doctor"):
        assert word in out.output


def test_short_flags(monkeypatch, stub_steps):
    assert CliRunner().invoke(cli, ["init", "-n", "-y", "--no-bitbucket"]).exit_code == 0


def test_no_bitbucket_skips_bb(stub_steps):
    out = CliRunner().invoke(cli, ["init", "-y", "--no-bitbucket"])
    assert out.exit_code == 0
    assert "_bb" not in stub_steps and "_brew" in stub_steps


def test_bitbucket_flag_runs_bb(stub_steps):
    assert CliRunner().invoke(cli, ["init", "-y", "--bitbucket"]).exit_code == 0
    assert "_bb" in stub_steps


def test_skip_plugins(stub_steps):
    CliRunner().invoke(cli, ["init", "-y", "--skip-plugins"])
    assert "_plugins" not in stub_steps


def test_brain_package_always_installed_daemon_only_with_flag(stub_steps, monkeypatch):
    seen = []
    monkeypatch.setattr(init_mod, "_brain", lambda d, daemon=False: seen.append(daemon) or init_mod.Result("brain", "ok"))
    CliRunner().invoke(cli, ["init", "-y"])
    CliRunner().invoke(cli, ["init", "-y", "--with-brain-daemon"])
    assert seen == [False, True]


def test_step_failure_exit_1_but_continues(stub_steps, monkeypatch):
    monkeypatch.setattr(init_mod, "_plugins", lambda *a, **k: init_mod.Result("plugins", "fail", "nope"))
    out = CliRunner().invoke(cli, ["init", "-y"])
    assert out.exit_code == 1
    assert "_doctor" in stub_steps


def test_step_exception_is_a_failure(stub_steps, monkeypatch):
    def raises(*a, **k):
        raise RuntimeError("kaput")
    monkeypatch.setattr(init_mod, "_skills", raises)
    out = CliRunner().invoke(cli, ["init", "-y"])
    assert out.exit_code == 1 and "kaput" in out.output


@pytest.mark.parametrize("statuses,dry,want", [
    (["ok", "skip"], False, "ok"),
    (["skip", "already present"], False, "skip"),
    (["ok", "failed"], False, "fail"),
    ([], False, "ok"),
    (["ok"], True, "dry-run"),
])
def test_aggregate(statuses, dry, want):
    assert init_mod._aggregate("x", statuses, dry).status == want
