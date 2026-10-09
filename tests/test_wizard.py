import pytest
from click.testing import CliRunner

from super_ai_skills import init as init_mod
from super_ai_skills.cli import cli
from super_ai_skills.plugins import Result
from super_ai_skills.wizard import Step, run_wizard, select_steps


def make(calls, fail=(), keys=("a", "b", "c")):
    def mk(k, rec):
        def run(dry):
            calls.append((k, dry))
            if k in fail:
                raise RuntimeError("boom")
            return Result(k, "ok", "did it")
        return Step(k, k.upper(), f"why {k}", rec, rec, run)
    return [mk(k, k != "c") for k in keys]  # c is optional


class Answers:
    def __init__(self, *a):
        self.a, self.asked = list(a), []

    def __call__(self, text, default=False):
        self.asked.append((text, default))
        return self.a.pop(0)


def go(steps, **kw):
    out = []
    res = run_wizard(steps, echo=out.append, **kw)
    return res, "\n".join(out)


def test_prompt_defaults_and_labels():
    calls = []
    p = Answers(True, True, False)
    res, out = go(make(calls), prompt=p)
    assert [d for _, d in p.asked] == [True, True, False]  # [Y/n] recommended, [y/N] optional
    assert "Step 1/3: A (recommended)" in out and "Step 3/3: C (optional)" in out
    assert "why a" in out
    assert [c[0] for c in calls] == ["a", "b"]
    assert [r.status for r in res] == ["ok", "ok", "declined"]


def test_decline_skips_step():
    calls = []
    res, out = go(make(calls), prompt=Answers(False, True, True))
    assert [c[0] for c in calls] == ["b", "c"]
    assert "skipped by you: a" in out


def test_yes_accepts_recommended_skips_optional_no_prompt():
    calls = []
    res, _ = go(make(calls), yes=True, prompt=lambda *a, **k: pytest.fail("prompted"))
    assert [c[0] for c in calls] == ["a", "b"]
    assert res[2].status == "declined"


def test_no_input_same_and_never_prompts():
    calls = []
    go(make(calls), no_input=True, prompt=lambda *a, **k: pytest.fail("prompted"))
    assert [c[0] for c in calls] == ["a", "b"]


def test_only_and_skip():
    calls = []
    go(make(calls), yes=True, only=["b", "a"])
    assert [c[0] for c in calls] == ["a", "b"]  # list order, not --only order
    calls.clear()
    res, out = go(make(calls), yes=True, skip=["a"])
    assert [c[0] for c in calls] == ["b"] and "Step 1/2: B" in out


def test_unknown_key_raises():
    with pytest.raises(ValueError, match="nope"):
        select_steps(make([]), only=["nope"])


def test_dry_run_calls_each_with_dry_true_no_prompt():
    calls = []
    go(make(calls), dry_run=True, prompt=lambda *a, **k: pytest.fail("prompted"))
    assert calls == [("a", True), ("b", True), ("c", True)]


def test_failure_reported_and_continues():
    calls = []
    res, out = go(make(calls, fail={"a"}), yes=True)
    assert [c[0] for c in calls] == ["a", "b"]
    assert res[0].status == "fail" and "boom" in res[0].detail
    assert "failed: a" in out and "done: b" in out


def test_summary_groups_and_hints():
    steps = [
        Step("ohmyzsh", "x", "w", True, True, lambda d: Result("x", "skip", "present")),
        Step("powerlevel10k", "x", "w", True, True, lambda d: Result("x", "ok")),
        Step("iterm2", "x", "w", True, True, lambda d: Result("x", "unsupported", "mac only")),
    ]
    _, out = go(steps, yes=True)
    assert "skipped, already present: ohmyzsh" in out
    assert "not applicable here: iterm2" in out
    assert "restart your shell" in out.lower() and "p10k configure" in out
    assert "open iTerm2" not in out


def test_no_hints_on_dry_run():
    _, out = go(make([], keys=("powerlevel10k",)), dry_run=True)
    assert "Next:" not in out


# --- real step list ---------------------------------------------------
def test_real_step_order_and_flags():
    steps = init_mod.build_steps()
    assert [s.key for s in steps] == init_mod.STEP_KEYS
    assert [s.key for s in steps][-1] == "doctor" and not steps[-1].ask
    brain = next(s for s in steps if s.key == "brain")
    assert brain.recommended and brain.default_yes
    assert all(s.recommended for s in steps)


@pytest.fixture
def fake_modules(monkeypatch):
    import sys
    from types import SimpleNamespace
    calls = []

    def f(name):
        def fn(dry_run=False, **k):
            calls.append((name, dry_run))
            return Result(name, "dry-run" if dry_run else "ok", "")
        return fn
    monkeypatch.setitem(sys.modules, "super_ai_skills.shell_setup", SimpleNamespace(
        install_ohmyzsh=f("omz"), install_powerlevel10k=f("p10k"), install_zsh_plugins=f("plug")))
    monkeypatch.setitem(sys.modules, "super_ai_skills.iterm", SimpleNamespace(
        install_iterm2=f("iterm"), apply_iterm_profile=f("profile")))
    monkeypatch.setattr(init_mod, "detect_bitbucket_here", lambda: False)
    return calls


def test_starship_note_when_p10k_accepted(fake_modules):
    r = init_mod._p10k(False)
    assert r.status == "ok" and "starship" in r.detail and "powerlevel10k" in r.detail


def test_dry_run_wires_shell_and_iterm_with_dry_true(fake_modules, monkeypatch, capsys):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("subprocess"))
    monkeypatch.setattr(init_mod.sys, "platform", "darwin")
    res = init_mod.run_init(dry_run=True, yes=True)
    assert ("omz", True) in fake_modules and ("profile", True) in fake_modules
    assert [r.name for r in res] == [k for k in init_mod.STEP_KEYS if k != "bb"]


def test_iterm_skipped_on_linux(fake_modules, monkeypatch):
    monkeypatch.setattr(init_mod.sys, "platform", "linux")
    r = init_mod._iterm2(False)
    assert r.status == "unsupported" and "macOS" in r.detail
    assert not fake_modules


def test_missing_step_module_is_a_failure_not_a_crash(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "super_ai_skills.shell_setup", None)  # forces ImportError
    res = init_mod.run_init(dry_run=False, yes=True, only=["ohmyzsh"])
    assert res[0].status == "fail"


def test_bb_forced_by_only_and_skip_plugins(fake_modules, monkeypatch):
    res = init_mod.run_init(dry_run=True, only=["bb", "plugins"], skip_plugins=True)
    assert [r.name for r in res] == ["bb"]


# --- CLI -------------------------------------------------------------
def test_cli_flags_and_help():
    r = CliRunner()
    for flag in ("-h", "--help"):
        out = r.invoke(cli, ["init", flag])
        assert out.exit_code == 0
        for opt in ("--yes", "--no-input", "--only", "--skip", "--dry-run", "--bitbucket", "--skip-plugins"):
            assert opt in out.output


def test_cli_unknown_step_is_usage_error():
    out = CliRunner().invoke(cli, ["init", "--only", "nope"])
    assert out.exit_code == 2 and "nope" in out.output


def test_cli_interactive_decline(fake_modules, monkeypatch):
    monkeypatch.setattr(init_mod, "detect_bitbucket_here", lambda: False)
    out = CliRunner().invoke(cli, ["init", "--only", "ohmyzsh,powerlevel10k"], input="n\ny\n")
    assert out.exit_code == 0, out.output
    assert "Install? [Y/n]" in out.output
    assert [c[0] for c in fake_modules] == ["p10k"]
