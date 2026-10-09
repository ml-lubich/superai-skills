"""plugins.py: manifest, exclusions, skip-if-enabled, exact argv, missing claude."""

import json
import re

from super_ai_skills import plugins

DEFAULTS = {
    "oh-my-claudecode@omc",
    "superpowers@superpowers-marketplace",
    "ponytail@ponytail",
    "context7@context7-marketplace",
    "chrome-devtools-mcp@chrome-devtools-plugins",
    "claude-mem@thedotmack",
    "frontend-design@claude-plugins-official",
}
OPTIONAL = {
    "vercel@claude-plugins-official",
    "sentry@claude-plugins-official",
    "sentry-cli@claude-plugins-official",
    "slack@claude-plugins-official",
    "claude-tiers@claude-tiers",
}


class Recorder:
    def __init__(self, rc=0):
        self.calls = []
        self.rc = rc

    def __call__(self, argv):
        self.calls.append(argv)
        return self.rc


def settings(tmp_path, enabled):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"enabledPlugins": {k: True for k in enabled}}))
    return p


def run(tmp_path, tier="default", enabled=(), dry_run=False, rc=0, which=lambda _: "/bin/claude",
        known=None, runner=None):
    r = runner or Recorder(rc)
    res = plugins.install_plugins(
        tier=tier, dry_run=dry_run, runner=r,
        settings_path=settings(tmp_path, enabled), which=which,
        known_path=tmp_path / "known_marketplaces.json" if known is None else known,
    )
    return r, res


def test_manifest_tiers():
    ms = plugins.load_manifest()
    assert {p["id"] for p in ms["plugin"] if p["tier"] == "default"} == DEFAULTS
    assert {p["id"] for p in ms["plugin"] if p["tier"] == "optional"} == OPTIONAL


def test_excluded_never_in_manifest_or_installed(tmp_path):
    ms = plugins.load_manifest()
    ids = {p["id"] for p in ms["plugin"]}
    repos = {p["repo"] for p in ms["plugin"]}
    assert not ids & set(ms["excluded"]["ids"])
    assert not repos & set(ms["excluded"]["repos"])
    r, _ = run(tmp_path, tier="all")
    flat = " ".join(" ".join(c) for c in r.calls)
    assert "scroll-craft" not in flat and "swift-lsp" not in flat and "ecc" not in flat.split()


def test_default_tier_excludes_optional(tmp_path):
    r, _ = run(tmp_path)
    flat = " ".join(" ".join(c) for c in r.calls)
    assert "vercel@" not in flat and "claude-tiers" not in flat


def test_all_tier_includes_optional(tmp_path):
    r, res = run(tmp_path, tier="all")
    assert len(res) == len(DEFAULTS | OPTIONAL)


def test_exact_argv(tmp_path):
    r, res = run(tmp_path)
    assert ["claude", "plugin", "marketplace", "add", "Yeachan-Heo/oh-my-claudecode"] in r.calls
    assert ["claude", "plugin", "install", "oh-my-claudecode@omc"] in r.calls
    assert all(x.status == "ok" for x in res)


def test_marketplace_added_once_per_repo(tmp_path):
    r, _ = run(tmp_path)
    adds = [c for c in r.calls if c[2:4] == ["marketplace", "add"]]
    assert len(adds) == len({c[4] for c in adds})


def test_already_enabled_skipped(tmp_path):
    r, res = run(tmp_path, enabled=["ponytail@ponytail"])
    assert ["claude", "plugin", "install", "ponytail@ponytail"] not in r.calls
    assert not any("DietrichGebert/ponytail" in c for c in r.calls)
    assert [x.status for x in res if x.name == "ponytail@ponytail"] == ["skip"]


def test_missing_settings_file_is_fine(tmp_path):
    r = Recorder()
    plugins.install_plugins(runner=r, settings_path=tmp_path / "nope.json", which=lambda _: "/bin/claude")
    assert r.calls


def test_dry_run_runs_nothing(tmp_path):
    r, res = run(tmp_path, dry_run=True)
    assert r.calls == []
    assert len(res) == len(DEFAULTS)
    assert all(x.status == "dry-run" for x in res)


def test_missing_claude_clear_fail(tmp_path):
    r, res = run(tmp_path, which=lambda _: None)
    assert r.calls == []
    assert len(res) == 1 and res[0].status == "fail" and "claude" in res[0].detail


def test_install_failure_reported(tmp_path):
    _, res = run(tmp_path, rc=1)
    assert all(x.status == "fail" for x in res)


def _plugins():
    return plugins.load_manifest()["plugin"]


def test_ids_well_formed_and_unique():
    ids = [p["id"] for p in _plugins()]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9._-]+@[a-z0-9._-]+", i) for i in ids)


def test_repos_owner_name_and_tiers_valid():
    for p in _plugins():
        assert re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", p["repo"]), p
        assert p["tier"] in ("default", "optional"), p


def test_ecc_never_installable():
    ms = plugins.load_manifest()
    assert "ecc@ecc" in ms["excluded"]["ids"]
    bad = re.compile(r"(^|[^a-z0-9])ecc([^a-z0-9]|$)|everything-claude-code", re.I)
    for p in ms["plugin"]:
        assert not bad.search(p["id"]) and not bad.search(p["repo"]), p


def test_omc_is_default():
    assert {p["id"]: p["tier"] for p in _plugins()}["oh-my-claudecode@omc"] == "default"


def test_single_superpowers_entry():
    assert [p["id"] for p in _plugins() if p["id"].startswith("superpowers@")] == [
        "superpowers@superpowers-marketplace"
    ]


def test_superpowers_repo_is_the_marketplace():
    assert {p["id"]: p["repo"] for p in _plugins()}["superpowers@superpowers-marketplace"] == (
        "obra/superpowers-marketplace"
    )


def test_plugins_module_has_tomli_fallback():
    import pathlib
    src = pathlib.Path(plugins.__file__).read_text()
    assert "import tomli as tomllib" in src and "sys.version_info" in src


def test_known_marketplace_add_skipped(tmp_path):
    k = tmp_path / "known_marketplaces.json"
    k.write_text(json.dumps({"omc": {"source": {"repo": "Yeachan-Heo/oh-my-claudecode"}}}))
    r, res = run(tmp_path, known=k)
    assert ["claude", "plugin", "marketplace", "add", "Yeachan-Heo/oh-my-claudecode"] not in r.calls
    assert ["claude", "plugin", "install", "oh-my-claudecode@omc"] in r.calls
    assert all(x.status == "ok" for x in res)


def test_failed_marketplace_add_is_nonfatal(tmp_path):
    class R(Recorder):
        def __call__(self, argv):
            super().__call__(argv)
            return 1 if argv[2:4] == ["marketplace", "add"] else 0
    r, res = run(tmp_path, runner=R())
    assert ["claude", "plugin", "install", "oh-my-claudecode@omc"] in r.calls
    assert all(x.status == "ok" for x in res)


def test_excluded_repo_never_installed(tmp_path, monkeypatch):
    ms = plugins.load_manifest()
    ms["plugin"].append({"id": "evil@scroll", "repo": ms["excluded"]["repos"][0], "tier": "default"})
    monkeypatch.setattr(plugins, "load_manifest", lambda: ms)
    r, res = run(tmp_path)
    assert "evil@scroll" not in " ".join(" ".join(c) for c in r.calls)
    assert "evil@scroll" not in {x.name for x in res}
