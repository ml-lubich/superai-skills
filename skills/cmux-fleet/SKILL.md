---
name: cmux-fleet
description: Launch and run a multi-agent build/deploy "fleet" on the cmux run-surface. Use when the user says "do this as a fleet", "fleet via cmux", "spin up agents in cmux panes", "orchestrate agents and loop until done", or wants parallel Claude/Codex/Cursor workers visible as cmux splits. Ported from the cmux-agent-factory + manager-subagent-orchestration Cursor rules.
---

# cmux-fleet

Run a substantive build/deploy as a **manager + worker fleet** on the cmux
run-surface: cmux hosts the panes, coding CLIs (Claude/Codex/Cursor/Gemini) are
the workers, you are the manager who plans, delegates, verifies, and integrates.

## Hard prerequisite — you must be INSIDE cmux

The cmux socket rejects outside processes (`cmux ping` →
`Access denied - only processes started inside cmux can connect`). Fleet
orchestration that drives cmux splits only works from a session launched inside
cmux. Two ways in:

```bash
cmux claude-teams            # Claude Code with agent-teams mode -> splits become cmux panes
cmux omc                     # Oh My Claude Code multi-agent, native cmux panes
```

Both install a private tmux shim so agent-team window/pane ops map to cmux
workspaces/splits. If `cmux ping` works, you're inside and can drive the socket
directly (see the `cmux-cli` and `cmux-workspace` skills). If it's denied, tell
the user to kick the fleet off with one of the commands above — do not fake it.

## Authority map (do not duplicate — extend these)

| Layer | Path |
|-------|------|
| Shared personal skills (source of truth) | `~/.agents/skills/<name>/` → symlinked into `~/.claude/skills`, `~/.cursor/skills`, `~/.codex/skills` |
| Always-on rails | `~/.cursor/rules/*.mdc` |
| cmux workspace/launcher | `~/.config/cmux/cmux.json` (global), `<repo>/.cmux/cmux.json` (project) |
| Cross-session AI TODO | `~/.config/agent-todo/TODO.md` |
| Tool registry (CLI-first) | `~/.config/tool-registry/registry.json` |

## Worker launchers (in a cmux pane, in the repo working dir)

- Claude Code: `claude -- {{prompt}}`
- Claude Autopilot (explicit unsafe only): `claude --dangerously-skip-permissions -- {{prompt}}`
- Codex: `codex -- {{prompt}}` · Cursor: `cursor-agent -- {{prompt}}` · Gemini: `gemini -- {{prompt}}`
- Desktop GUI control: `cua-driver -- {{prompt}}`

Default permission policy: **safe prompts**. Autopilot/skip-permissions only when
the user explicitly asks for it.

## Manager loop (every substantive build)

1. **Plan + split** the mission into independent, self-contained worker tasks
   (goal, exact paths, boundaries, expected output). One writer per file.
2. **Fan out**: one cmux pane per worker for parallel, order-independent tasks;
   chain when B needs A. Give each worker only the tools/files it needs.
   - Scoped, non-focus-stealing pane creation:
     `cmux new-pane --workspace "$CMUX_WORKSPACE_ID" --type terminal --direction right --focus false`
     then `cmux send --surface <s> "cd <repo> && claude -- '<task>'\n"`.
   - Track progress on the sidebar: `cmux set-status fleet running --workspace "$CMUX_WORKSPACE_ID"`.
3. **Keep manager context thin** — read short worker results, don't absorb transcripts.
4. **Verify** each worker's output against the request + repo conventions; run the
   project's real verify (`npm test`, `bun run ci`, a live screenshot) before "done".
5. **Loop** until acceptance criteria pass. Same failure 3× → stop patching, escalate
   (architect) or re-run in a fresh worker/context, never inside the failed transcript.

## Guardrails

- Sensitive/irreversible steps (SSH to shared hosts, deploys, deletes, secrets) stay
  under manager control with evidence — don't hand them to unattended skip-permission
  workers unless the user explicitly approved that host/action.
- Read-only where asked (e.g. Slack): never post.
- Don't invent a second control plane — extend the paths above.

## Worked mission shape: environment-readiness deploy

Fleet tasks (parallel unless noted):
- **deploy** (manager-driven): ship the repo to the target host, build, run each
  env, publish screenshots + report to the web dir, install the nightly job.
- **dashboard**: generate the results page and the config snippet (results URL +
  per-env admin URLs + "what got fixed" notes) for the user to paste.
- **verify**: from the target box, confirm each dependency endpoint is reachable;
  capture per-env state via screenshots.

Note the split: deploy touches remote infrastructure so it stays manager-driven,
while dashboard and verify are order-independent and fan out freely.

Kick off inside cmux:
```bash
cmux omc            # or: cmux claude-teams
# then: "Use the cmux-fleet skill to run the <name> mission."
```
