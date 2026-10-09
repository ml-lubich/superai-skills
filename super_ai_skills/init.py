"""`superai-skills init`: one idempotent command that sets up the whole workstation."""

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional

from rich.console import Console

from super_ai_skills.plugins import Result
from super_ai_skills.wizard import Step, run_wizard

console = Console()

ROOT_DIR = Path(__file__).resolve().parent.parent


# --- Bitbucket detection ---------------------------------------------------
def detect_bitbucket(remotes: List[str], env: Mapping[str, str], bb_config_exists: bool) -> bool:
    """Pure: true if any remote mentions bitbucket, a BITBUCKET_*/BB_* env is set, or ~/.config/bb exists."""
    if any("bitbucket" in r.lower() for r in remotes):
        return True
    if any(k.startswith(("BITBUCKET_", "BB_")) for k in env):
        return True
    return bb_config_exists


def resolve_bitbucket(flag: Optional[bool], detected: bool) -> bool:
    return detected if flag is None else flag


def _git_urls(repo: Path) -> List[str]:
    # Read .git/config directly: no subprocess, so --dry-run stays side-effect free.
    # .git may be a file ("gitdir: ...") in worktrees and submodules.
    git = repo / ".git"
    try:
        if git.is_file():
            git = (repo / git.read_text().split(":", 1)[1].strip()).resolve()
            if (git / "commondir").is_file():
                git = (git / (git / "commondir").read_text().strip()).resolve()
        lines = (git / "config").read_text().splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip().startswith("url")]


def detect_bitbucket_here() -> bool:
    home = Path.home()
    repos = [Path.cwd()]
    dev = home / "dev"
    if dev.is_dir():
        repos += [p for p in sorted(dev.iterdir()) if p.is_dir()]
    remotes = [u for r in repos for u in _git_urls(r)]
    return detect_bitbucket(remotes, os.environ, (home / ".config" / "bb").exists())


# --- Step runners (each takes dry_run, returns Result) -------------------------
def _aggregate(name: str, statuses: Iterable[str], dry_run: bool, detail: str = "") -> Result:
    """ok/failed/already-present roll-up. statuses use plugins.Result words or tools.py words."""
    sts = list(statuses)
    if dry_run:
        return Result(name, "dry-run", detail)
    if any(x in ("fail", "failed") for x in sts):
        return Result(name, "fail", detail)
    if sts and all(x in ("skip", "already present") for x in sts):
        return Result(name, "skip", "already present")
    return Result(name, "ok", detail)


def _brew(dry_run: bool) -> Result:
    if dry_run:
        return Result("brew", "dry-run", "would install uv, brew/apt dev tools, Python, uv tools")
    from super_ai_skills.env import EnvironmentManager
    em = EnvironmentManager()
    em.ensure_uv()
    if em.is_mac:
        em.setup_macos()
    elif em.is_linux:
        em.setup_linux()
    em.setup_python()
    em.setup_uv_tools()
    failed = [n for n, st in em._summary.items() if st == "failed"]
    return Result("brew", "fail" if failed else "ok", ", ".join(failed))


def _ai_clis(dry_run: bool) -> Result:
    from super_ai_skills.env import EnvironmentManager
    if all(shutil.which(c) for c, _ in EnvironmentManager.AI_CLIS):
        return Result("ai-clis", "skip", "already present")
    if dry_run:
        return Result("ai-clis", "dry-run", "would install claude, gemini, codex")
    em = EnvironmentManager()
    em.setup_ai_clis()
    failed = [n for n, st in em._summary.items() if st == "failed"]
    return Result("ai-clis", "fail" if failed else "ok", ", ".join(failed))


def _bb(dry_run: bool) -> Result:
    if shutil.which("bb"):
        return Result("bb", "skip", "already present")
    if dry_run:
        return Result("bb", "dry-run", "would uv tool install packages/bitbucket-cli")
    subprocess.run(["uv", "tool", "install", str(ROOT_DIR / "packages" / "bitbucket-cli")], check=True)
    return Result("bb", "ok")


def _call(module: str, fn: str, dry_run: bool) -> Result:
    # Lazy: shell_setup / iterm are owned by other modules and imported only when the step runs.
    return getattr(importlib.import_module(f"super_ai_skills.{module}"), fn)(dry_run=dry_run)


STARSHIP_NOTE = "starship stays off in .zshrc: powerlevel10k owns the prompt"


def _p10k(dry_run: bool) -> Result:
    r = _call("shell_setup", "install_powerlevel10k", dry_run)
    if r.status in ("ok", "skip", "dry-run"):
        r = Result(r.name, r.status, f"{r.detail}; {STARSHIP_NOTE}".lstrip("; "))
    return r


def _iterm2(dry_run: bool) -> Result:
    if sys.platform != "darwin":
        return Result("iterm2", "unsupported", "iTerm2 is macOS-only; skipped on this platform")
    app = _call("iterm", "install_iterm2", dry_run)
    prof = _call("iterm", "apply_iterm_profile", dry_run)
    detail = "; ".join(d for d in (app.detail, prof.detail) if d)
    return _aggregate("iterm2", [app.status, prof.status], dry_run, detail)


def _plugins(dry_run: bool, tier: str = "default") -> Result:
    from super_ai_skills import plugins
    res = plugins.install_plugins(tier, dry_run)
    bad = "; ".join(f"{r.name}: {r.detail}" for r in res if r.status == "fail")
    return _aggregate("plugins", [r.status for r in res], dry_run, bad)


def _tools(dry_run: bool) -> Result:
    from super_ai_skills.tools import install_tools
    res = install_tools("default", dry_run, out=console.print)
    bad = ", ".join(n for n, st in res.items() if st == "failed")
    return _aggregate("tools", res.values(), dry_run, bad)


def _skills(dry_run: bool) -> Result:
    if dry_run:
        return Result("skills", "dry-run", "would link skills into claude, cursor, codex, gemini")
    from super_ai_skills.cli import install_skills
    install_skills.callback("all")
    return Result("skills", "ok")


def _brain(dry_run: bool, daemon: bool = False) -> Result:
    try:
        from super_ai_skills import brain_setup
    except ImportError:
        return Result("brain", "unsupported", "brain_setup is not part of this checkout")
    r = brain_setup.install(dry_run, daemon)
    return Result("brain", getattr(r, "status", "ok"), str(getattr(r, "detail", "")))


def _doctor(dry_run: bool) -> Result:
    if dry_run:
        return Result("doctor", "dry-run", "would run health check")
    from super_ai_skills.cli import doctor
    doctor.callback()
    return Result("doctor", "ok")


STEP_KEYS = ["brew", "bb", "ai-clis", "ohmyzsh", "powerlevel10k", "zsh-plugins",
             "iterm2", "plugins", "tools", "skills", "brain", "doctor"]


def build_steps(with_brain_daemon: bool = False, plugins: str = "default") -> List[Step]:
    steps = [
        Step("brew", "Dev tools", "Installs uv, Homebrew/apt packages (git, gh, jq, ripgrep, fzf...) and Python.",
             True, True, _brew),
        Step("bb", "Bitbucket CLI", "Installs the `bb` Bitbucket command-line client (skipped unless detected/forced).",
             True, True, _bb),
        Step("ai-clis", "AI CLIs", "Installs the claude, gemini and codex command-line agents.",
             True, True, _ai_clis),
        Step("ohmyzsh", "oh-my-zsh", "Installs the oh-my-zsh zsh framework. Your login shell is not changed.",
             True, True, lambda d: _call("shell_setup", "install_ohmyzsh", d)),
        Step("powerlevel10k", "powerlevel10k prompt",
             "Installs the powerlevel10k theme plus the MesloLGS Nerd Font it needs.",
             True, True, _p10k),
        Step("zsh-plugins", "zsh plugins", "Adds zsh-autosuggestions and zsh-syntax-highlighting.",
             True, True, lambda d: _call("shell_setup", "install_zsh_plugins", d)),
        Step("iterm2", "iTerm2 + profile", "Installs iTerm2 (macOS) and a profile using the Nerd Font.",
             True, True, _iterm2),
        Step("plugins", "Claude Code plugins", "Installs the default set of Claude Code plugins.",
             True, True, lambda d: _plugins(d, plugins)),
        Step("tools", "CLI/MCP add-ons", "Installs the default add-ons from tools.toml (skips what you have).",
             True, True, _tools),
        Step("skills", "Agent skills", "Links the bundled skills into Claude, Cursor, Codex and Gemini.",
             True, True, _skills),
        Step("brain", "Brain agent", "Installs the open-brain `brain` CLI; its launchd daemon only with --with-brain-daemon.",
             True, True, lambda d: _brain(d, with_brain_daemon)),
        Step("doctor", "Health check", "Verifies what is installed.", True, True, _doctor, ask=False),
    ]
    return steps


def run_init(dry_run: bool = False, bitbucket: Optional[bool] = None, with_brain_daemon: bool = False,
             skip_plugins: bool = False, plugins: str = "default", yes: bool = False, no_input: bool = False,
             only: Optional[List[str]] = None, skip: Optional[List[str]] = None,
             **wizard_kw) -> List[Result]:
    use_bb = resolve_bitbucket(bitbucket, detect_bitbucket_here() if bitbucket is None else False)
    skip = list(skip or []) + (["plugins"] if skip_plugins else [])
    if not use_bb and "bb" not in (only or []):
        skip.append("bb")
    return run_wizard(build_steps(with_brain_daemon, plugins), yes=yes, no_input=no_input,
                      only=only, skip=skip, dry_run=dry_run, **wizard_kw)
