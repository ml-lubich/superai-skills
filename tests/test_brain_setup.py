from types import SimpleNamespace

from super_ai_skills import brain_setup
from super_ai_skills.brain_setup import install, BRAIN_URL

UV = ["uv", "tool", "install", BRAIN_URL]


def _rec(rc=0):
    calls = []

    def run(argv):
        calls.append(argv)
        return SimpleNamespace(returncode=rc, stderr="")
    return run, calls


def _which(found=True, brain=False):
    return lambda name: f"/bin/{name}" if found and (name != "brain" or brain) else None


def _owned(listing="open-brain v0.1\n- brain\n"):
    return lambda: listing


def test_default_installs_tool_only():
    run, calls = _rec()
    r = install(runner=run, which=_which(), system="Darwin", tool_list=_owned())
    assert (r.status, calls) == ("ok", [UV])


def test_daemon_runs_init_then_install_on_macos():
    run, calls = _rec()
    r = install(daemon=True, runner=run, which=_which(), system="Darwin", tool_list=_owned())
    assert r.status == "ok" and calls == [UV, ["brain", "init"], ["brain", "install"]]


def test_daemon_on_linux_installs_package_and_skips_only_daemon():
    run, calls = _rec()
    r = install(daemon=True, runner=run, which=_which(), system="Linux", tool_list=_owned())
    assert r.status == "ok" and "macOS" in r.detail and calls == [UV]


def test_linux_without_daemon_still_installs():
    run, calls = _rec()
    assert install(runner=run, which=_which(), system="Linux", tool_list=_owned()).status == "ok"
    assert calls == [UV]


def test_init_failure_missing_from_address_is_skip():
    calls = []

    def run(argv):
        calls.append(argv)
        if argv == ["brain", "init"]:
            return SimpleNamespace(returncode=1, stderr="error: from_address is not set")
        return SimpleNamespace(returncode=0, stderr="")
    r = install(daemon=True, runner=run, which=_which(), system="Darwin", tool_list=_owned())
    assert r.status == "skip" and "config.toml" in r.detail and "from_address" in r.detail
    assert ["brain", "install"] not in calls


def test_init_other_failure_is_fail_with_stderr_tail():
    def run(argv):
        if argv == ["brain", "init"]:
            return SimpleNamespace(returncode=2, stderr="x\n" * 50 + "disk exploded")
        return SimpleNamespace(returncode=0, stderr="")
    r = install(daemon=True, runner=run, which=_which(), system="Darwin", tool_list=_owned())
    assert r.status == "fail" and "disk exploded" in r.detail


def test_foreign_brain_on_path_skips_without_force():
    run, calls = _rec()
    r = install(runner=run, which=_which(brain=True), system="Darwin",
                tool_list=_owned("other-tool v1\n"))
    assert r.status == "skip" and "brain" in r.detail and calls == []


def test_own_brain_already_installed_skips_package_step_only():
    run, calls = _rec()
    r = install(daemon=True, runner=run, which=_which(brain=True), system="Darwin",
                tool_list=_owned())
    assert r.status == "ok" and calls == [["brain", "init"], ["brain", "install"]]


def test_never_forces():
    run, calls = _rec()
    install(daemon=True, runner=run, which=_which(), system="Darwin", tool_list=_owned())
    assert all("--force" not in c for c in calls)


def test_dry_run_runs_nothing():
    run, calls = _rec()
    r = install(dry_run=True, daemon=True, runner=run, which=_which(False), system="Darwin")
    assert r.status == "dry-run" and calls == []
    assert BRAIN_URL in r.detail and "brain init" in r.detail and "brain install" in r.detail


def test_missing_uv_fails():
    run, calls = _rec()
    r = install(runner=run, which=_which(False), system="Darwin", tool_list=_owned())
    assert r.status == "fail" and "uv" in r.detail and calls == []


def test_failed_step_fails_and_stops():
    run, calls = _rec(rc=1)
    r = install(daemon=True, runner=run, which=_which(), system="Darwin", tool_list=_owned())
    assert r.status == "fail" and calls == [UV]


def test_url_is_open_brain():
    assert BRAIN_URL == "git+https://github.com/ml-lubich/open-brain"
    assert brain_setup.Result is not None
