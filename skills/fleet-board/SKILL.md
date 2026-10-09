---
name: fleet-board
description: Local Jira for agent fleets - a plain-file task board in .omc/fleet/<run>/board/ where agents create tasks, atomically claim them, hold exclusive file leases, write handoff notes and close with evidence. Use whenever 2+ agents/subagents work one job (spec-fleet, /team, /autopilot, parallel workers), or the user says "task board", "local jira", "claim a task", "who owns this file", "agents stepping on each other", "overlapping work", "track packages".
---

# fleet-board — the local task board (plain files, no deps)

Why: without shared context, agents coordinate through the file system (the "shared workspace", AI Agents in Depth §10.4.1) and need a control plane for status (§10.4.2). Two agents writing one file is failure mode one (§10.5.1). This board is the shared workspace + progress file + lease table in one folder.

Script: `~/.claude/skills/fleet-board/board.sh` (bash + awk; tested with 5-6 concurrent claimers, exactly one wins).

## Layout
```
.omc/fleet/<run>/board/
  tasks/T-NNN-slug.md     one task per file (frontmatter below + ## Notes + ## Log)
  locks/T-NNN.claim/      claim lock (mkdir = atomic; exists => taken)
  locks/files/<path>/     exclusive write lease per file; ./owner = "T-NNN agent"
  ids/N/                  atomic id allocation
  board.md                generated index - never hand-edit
```
Frontmatter: `id, title, status (todo|claimed|doing|review|done|blocked), owner, tier (haiku|sonnet|opus), depends_on (T-001,T-002), files (exclusive write set, comma list), acceptance, created, updated`.

## Commands (run from repo root, or set `BOARD=`/`RUN=`)
```bash
b=~/.claude/skills/fleet-board/board.sh; export RUN=<run>
$b new "Parser module" -t sonnet -f src/parser.py,tests/test_parser.py -a "pytest tests/test_parser.py green x3"
$b new "CLI wiring" -d T-001 -f src/cli.py -a "cli -h exits 0"
$b claim T-001 eng-a          # fails if: not todo, deps not done, WIP limit, already claimed, any file leased
$b set   T-001 eng-a doing    # doing|review|blocked [note]; owner only
$b note  T-001 eng-a "handoff: parse(str)->AST, raises ParseError"
$b done  T-001 eng-a "pytest 12 passed x3; sha abc123"   # refuses without evidence; frees leases
$b release T-001 eng-a        # give up -> todo, leases freed
$b list; $b index             # table to stdout | regenerate board.md
```
The atomic step is `mkdir locks/T-NNN.claim` - the OS guarantees one winner. Same trick for each file lease; if any lease fails the claim rolls back. Do not replace with "check status then write" (that races).

## Protocol
1. **Lead/manager creates tasks** from the spec: one task = one owner = a disjoint `files` set. Two tasks need the same file -> merge them, or chain with `-d`. No big overlapping tasks: if a task's files overlap another open task, split or serialize before launch.
2. **Agents claim, never get assigned silently.** Prompt each worker with: board path, its task id (or "claim the next todo whose deps are done"), its tier, effort level. Worker runs `claim` first; non-zero exit = stop and report, do not work unclaimed.
3. **Write only leased files.** Need a file you don't hold? `note` the owner's task (or `set ... blocked "<why>"`) and stop. Scratch goes in your own scratchpad, never the shared tree (§10.4.1 area I vs II).
4. **WIP limit:** `WIP_LIMIT` (default 1) open tasks per agent. Finish or release before claiming more.
5. **Dependencies:** `claim` refuses until every `depends_on` task is `done`. Order = the dependency graph, not launch order.
6. **Handoff notes, not transcripts:** `note` = what the next agent needs (interfaces, decisions, file paths), the handoff package of §10.4.5: task, confirmed facts, artifact paths. Never paste trajectories.
7. **Definition of done:** acceptance met + evidence string (test tail, SHA, screenshot path, curl output). `review` when a reviewer must grade it; the reviewer (different agent) runs `done` or `set ... doing "<findings>"` back to the owner. The author never approves its own task (fleet-guards).
8. **Status for managers = read the board** (`list`, `board.md`, task `## Log`), not polling agents. A task whose `updated` is stale for N minutes = stuck: message the owner, then `release` on its behalf (`owner` check: run as that owner) and re-assign (§10.4.2 stuck detection).
9. **Semantic conflicts** (A renumbers figures while B cites old numbers) are not caught by leases (§10.5.1): the lead records cross-file contracts in `.omc/fleet/<run>/contracts.md` and the integrator checks them.
10. **Close out:** `index` at the end; all tasks `done` or explicitly `blocked` with a reason; unfinished work -> repo `tasks/T-*.md`.

Own additions (not from the book): mkdir-lock claims, WIP limit, the evidence-required `done`. Upgrade path: per-task heartbeat file if stale-claim detection by `updated` proves too coarse.
