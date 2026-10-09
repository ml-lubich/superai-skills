"""Install Claude Code plugins from plugins.toml via the `claude plugin` CLI.

Never edits settings.json; only reads it to skip already-enabled plugins.
"""

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

MANIFEST = Path(__file__).resolve().parent.parent / "plugins.toml"
SETTINGS = Path.home() / ".claude" / "settings.json"
KNOWN_MARKETPLACES = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"


@dataclass
class Result:
    name: str
    status: str  # ok | skip | fail | dry-run
    detail: str = ""


def load_manifest(path=MANIFEST):
    with open(path, "rb") as f:
        return tomllib.load(f)


def _run(argv):
    return subprocess.run(argv, capture_output=True, text=True).returncode


def _enabled(settings_path):
    try:
        data = json.loads(Path(settings_path).read_text())
    except FileNotFoundError:
        return set()
    return {k for k, v in data.get("enabledPlugins", {}).items() if v}


def _known_repos(path):
    """Repos of marketplaces Claude already knows (read-only)."""
    try:
        data = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return set()
    return {m.get("source", {}).get("repo") for m in data.values() if isinstance(m, dict)}


def install_plugins(tier="default", dry_run=False, runner=_run,
                    settings_path=SETTINGS, which=shutil.which, known_path=KNOWN_MARKETPLACES):
    """tier: 'default' or 'all' (default + optional). Returns one Result per plugin."""
    manifest = load_manifest()
    excluded = set(manifest["excluded"]["ids"])
    excluded_repos = set(manifest["excluded"].get("repos", []))
    wanted = [p for p in manifest["plugin"]
              if p["id"] not in excluded and p["repo"] not in excluded_repos and (tier == "all" or p["tier"] == "default")]
    if not dry_run and not which("claude"):
        return [Result("claude", "fail", "`claude` CLI not found on PATH; install Claude Code first")]
    enabled = _enabled(settings_path)
    added, results = _known_repos(known_path), []
    for p in wanted:
        if p["id"] in enabled:
            results.append(Result(p["id"], "skip", "already enabled"))
            continue
        steps = []
        if p["repo"] not in added:
            steps.append(["claude", "plugin", "marketplace", "add", p["repo"]])
        steps.append(["claude", "plugin", "install", p["id"]])
        if dry_run:
            results.append(Result(p["id"], "dry-run", "; ".join(" ".join(s) for s in steps)))
            continue
        for s in steps:
            if s[3:4] == ["add"]:
                if runner(s) == 0:
                    added.add(p["repo"])  # a failed add is non-fatal; the install decides
            elif runner(s) != 0:
                results.append(Result(p["id"], "fail", " ".join(s)))
                break
        else:
            results.append(Result(p["id"], "ok"))
    return results
