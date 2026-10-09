"""Install the open-brain agent (`brain` CLI); optionally set up its launchd job."""

import platform
import shutil
import subprocess

from super_ai_skills.plugins import Result

BRAIN_URL = "git+https://github.com/ml-lubich/open-brain"


def _run(argv):
    return subprocess.run(argv, stderr=subprocess.PIPE, text=True)


def _tool_list():
    return subprocess.run(["uv", "tool", "list"], capture_output=True, text=True).stdout


def install(dry_run=False, daemon=False, runner=_run, which=shutil.which,
            system=platform.system(), tool_list=_tool_list):
    run_daemon = daemon and system == "Darwin"
    steps = [["uv", "tool", "install", BRAIN_URL]]
    if run_daemon:
        steps += [["brain", "init"], ["brain", "install"]]
    if dry_run:
        return Result("brain", "dry-run", "; ".join(" ".join(s) for s in steps))
    if not which("uv"):
        return Result("brain", "fail", "`uv` not found on PATH; install uv first")
    if which("brain"):
        if "open-brain" not in tool_list():
            return Result("brain", "skip", "a different `brain` executable is already on PATH; "
                          "remove it or install open-brain manually")
        steps = steps[1:]  # ours is already installed; only the daemon steps remain
    for s in steps:
        res = runner(s)
        if res.returncode != 0:
            tail = " | ".join((res.stderr or "").strip().splitlines()[-5:])
            if s == ["brain", "init"] and "from_address" in tail:
                return Result("brain", "skip", "set from_address in ~/.config/brain/config.toml, "
                              "then rerun with --with-brain-daemon")
            return Result("brain", "fail", f"{' '.join(s)}: {tail}" if tail else " ".join(s))
    if run_daemon:
        return Result("brain", "ok", "brain daemon set up")
    if daemon:
        return Result("brain", "ok", "brain installed; daemon skipped (launchd is macOS only)")
    return Result("brain", "ok", "brain installed")
