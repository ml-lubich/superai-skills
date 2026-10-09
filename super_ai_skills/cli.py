"""CLI interface for super-ai-skills."""

import os
import sys
import subprocess
import shutil
import click
from rich.console import Console
from rich.table import Table

console = Console()

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILLS_DIR = os.path.join(ROOT_DIR, "skills")
PACKAGES_DIR = os.path.join(ROOT_DIR, "packages")

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    """Universal Super AI Skills & MCP Suite for macOS, Linux, and Cloud."""
    pass

@cli.command("list-skills")
def list_skills():
    """List all available agent skills."""
    if not os.path.exists(SKILLS_DIR):
        console.print("[red]Skills directory not found![/red]")
        return
    table = Table(title="Available AI Agent Skills")
    table.add_column("Skill Name", style="cyan bold")
    table.add_column("Status", style="green")
    table.add_column("Path", style="dim")

    for item in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, item)
        if os.path.isdir(skill_path):
            table.add_row(item, "Ready", skill_path)
    console.print(table)

@cli.command("list-mcp")
def list_mcp():
    """List bundled MCP server packages."""
    if not os.path.exists(PACKAGES_DIR):
        console.print("[red]Packages directory not found![/red]")
        return
    table = Table(title="Bundled MCP Servers & Packages")
    table.add_column("Package Name", style="magenta bold")
    table.add_column("Type", style="yellow")
    table.add_column("Status", style="green")

    for item in sorted(os.listdir(PACKAGES_DIR)):
        pkg_path = os.path.join(PACKAGES_DIR, item)
        if os.path.isdir(pkg_path):
            is_mcp = "MCP Server" if "mcp" in item else "Tool / Submodule"
            table.add_row(item, is_mcp, "Installed / Linked")
    console.print(table)

@cli.command("install-skills")
@click.option("--target", type=click.Choice(["claude", "cursor", "codex", "gemini", "all"]), default="all", help="Target agent client")
def install_skills(target):
    """Link or copy skills to target client directories."""
    home = os.path.expanduser("~")
    destinations = {
        "claude": os.path.join(home, ".claude", "skills"),
        "cursor": os.path.join(home, ".cursor", "skills"),
        "codex": os.path.join(home, ".codex", "skills"),
        "gemini": os.path.join(home, ".gemini", "config", "skills"),
    }
    
    targets = [target] if target != "all" else list(destinations.keys())

    for t in targets:
        dest_dir = destinations[t]
        os.makedirs(dest_dir, exist_ok=True)
        console.print(f"[bold green]Installing skills to {t} ({dest_dir})...[/bold green]")
        for item in sorted(os.listdir(SKILLS_DIR)):
            src = os.path.join(SKILLS_DIR, item)
            dst = os.path.join(dest_dir, item)
            if not os.path.isdir(src):
                continue
            if not os.path.exists(dst):
                try:
                    os.symlink(src, dst)
                    console.print(f"  [cyan]+ Symlinked {item}[/cyan]")
                except OSError:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    console.print(f"  [cyan]+ Copied {item}[/cyan]")
            else:
                console.print(f"  [dim]- Already present: {item}[/dim]")

    console.print("\n[bold green]✓ Skills successfully installed across targets![/bold green]")

@cli.command("setup-dev")
@click.option("--dry-run", "-n", is_flag=True, help="Run nothing; only show what the default add-ons would do")
def setup_dev(dry_run):
    """Run full developer environment bootstrap, then the default add-on tools."""
    from super_ai_skills.env import EnvironmentManager
    if dry_run:
        console.print("[dim]dry-run: base bootstrap skipped[/dim]")
    else:
        EnvironmentManager().bootstrap()
    _run_install_tools("default", dry_run)


def _run_install_tools(tier, dry_run):
    from super_ai_skills.tools import install_tools
    results = install_tools(tier=tier, dry_run=dry_run, out=console.print)
    for name, status in results.items():
        console.print(f"  {name}: {status}")


@cli.command("install-tools")
@click.option("--tier", type=click.Choice(["default", "all"]), default="default", help="default = safe add-ons; all adds optional (print-only for secrets/curl|bash)")
@click.option("--dry-run", "-n", is_flag=True, help="Run nothing, only print")
def install_tools_cmd(tier, dry_run):
    """Install popular CLI/MCP add-ons from tools.toml (skips what is already installed)."""
    _run_install_tools(tier, dry_run)


@cli.command("list-tools")
def list_tools():
    """List add-on tools (tools.toml) and whether each binary is present."""
    from super_ai_skills.tools import load_tools
    table = Table(title="Popular Add-ons")
    for col in ("Name", "Kind", "Tier", "Present", "Note / URL"):
        table.add_column(col)
    for t in load_tools():
        check = t.get("check")
        present = "-" if not check else ("yes" if shutil.which(check) else "no")
        table.add_row(t["name"], t["kind"], t.get("tier", "reference"), present, t.get("url") or t.get("note", ""))
    console.print(table)

@cli.command("doctor")
def doctor():
    """Run health check and environment diagnostics."""
    console.print(f"[bold]Platform:[/bold] {sys.platform}")
    console.print(f"[bold]Python:[/bold] {sys.version.split()[0]}")
    console.print(f"[bold]Root Dir:[/bold] {ROOT_DIR}")
    skills_count = len(os.listdir(SKILLS_DIR)) if os.path.exists(SKILLS_DIR) else 0
    pkgs_count = len(os.listdir(PACKAGES_DIR)) if os.path.exists(PACKAGES_DIR) else 0
    console.print(f"[bold]Skills:[/bold] {skills_count}")
    console.print(f"[bold]Packages:[/bold] {pkgs_count}")
    from super_ai_skills.tools import load_tools
    for t in load_tools():
        if t.get("check"):
            mark = "[green]✓[/green]" if shutil.which(t["check"]) else "[dim]-[/dim]"
            console.print(f"  {mark} {t['name']} ({t['check']})")
    console.print("[bold green]✓ Health check passed.[/bold green]")

def _keys(ctx, param, value):
    from super_ai_skills.init import STEP_KEYS
    keys = [k.strip() for k in (value or "").split(",") if k.strip()]
    bad = [k for k in keys if k not in STEP_KEYS]
    if bad:
        raise click.BadParameter(f"unknown step(s) {', '.join(bad)}; valid: {', '.join(STEP_KEYS)}")
    return keys


@cli.command("init")
@click.option("--yes", "-y", is_flag=True, help="Accept every recommended step, skip optional ones.")
@click.option("--no-input", is_flag=True, help="Like --yes and never prompt (CI).")
@click.option("--only", callback=_keys, help="Comma-separated step keys to run (e.g. ohmyzsh,skills).")
@click.option("--skip", callback=_keys, help="Comma-separated step keys to skip.")
@click.option("--dry-run", "-n", is_flag=True, help="Print every step without running anything.")
@click.option("--bitbucket/--no-bitbucket", default=None, help="Force or skip the Bitbucket CLI (default: auto-detect).")
@click.option("--with-brain-daemon", is_flag=True, help="Also install the brain daemon (macOS); on by default for that step.")
@click.option("--skip-plugins", is_flag=True, help="Same as --skip plugins.")
@click.option("--plugins", "plugins", type=click.Choice(["default", "all"]), default="default", show_default=True,
              help="Plugin tier: default, or all (adds optional ones that need their own accounts).")
def init(yes, no_input, only, skip, dry_run, bitbucket, with_brain_daemon, skip_plugins, plugins):
    """Guided setup wizard: shell, terminal, AI CLIs, plugins, tools, skills, doctor.

    Steps: brew, bb, ai-clis, ohmyzsh, powerlevel10k, zsh-plugins, iterm2, plugins, tools, skills, brain, doctor.
    """
    from super_ai_skills.init import run_init
    results = run_init(dry_run, bitbucket, with_brain_daemon, skip_plugins, plugins, yes, no_input, only, skip)
    if any(r.status == "fail" for r in results):
        sys.exit(1)

def main():
    cli()

if __name__ == "__main__":
    main()
