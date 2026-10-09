---
name: spec-fleet
description: Fan out subagents. ALWAYS invoke for any complex or multi-part task (3+ disjoint work packages, multi-file feature, refactor, bug sweep, build-out): spec first, Opus lead over 3-5 managers, each with a tech lead, engineers and Haiku scouts, Claude Teams / message bus, non-blocking voting and tie-breaks up the chain, TDD at engineer level. Skip only one-liners, single commands, simple questions.
---

# spec-fleet — fan out subagents: lead → managers → tech leads → engineers → scouts

**Always invoke** for complex/multi-part work (the user wants this every time). **Skip:** one-liners, single commands, Q&A, heavy-shared-context edits.
**Fan out subagents:** split into disjoint packages and launch managers (and their trees) in parallel in ONE message; never one agent for the whole job. Announce "Using spec-fleet". Plan with the ponytail ladder (cheapest thing that works, no speculative packages).
**Before launch and at review apply `fleet-guards`** (is multi-agent worth it, topology, failure-mode guards). **Track every package/task on `fleet-board`** (`~/.claude/skills/fleet-board/board.sh`): agents claim tasks, hold file leases, close with evidence.

## Chain of command (like a human org)
| Role | Model | Does | Never |
|------|-------|------|-------|
| Lead (office) | Opus | architecture, spec, contracts, assigns, breaks MANAGER ties, final verdict | write feature code |
| Managers (3–5) | Opus hard / Sonnet else | own ONE package + its tests' acceptance, break TECH-LEAD ties, escalate what they can't | touch other packages |
| Tech leads (1 per manager, Sonnet) | Sonnet | split the package, review engineers' diffs, break ENGINEER ties, enforce TDD | exceed package files |
| Engineers | Sonnet | write the failing test first, implement, run tests | decide cross-cutting design |
| Scouts | Haiku / cheap Sonnet | search, recon, renames, boilerplate for engineers/tech leads | design |
Team size follows the plan, never padded. Use Claude Teams (OMC `/team`, named agents + `SendMessage`) so peers talk directly.

## Procedure
1. **Prep:** `git fetch`, ahead/behind + `git status`. Dirty/behind → writers use detached worktrees off `origin/main`, land via `git push origin HEAD:main` (rebase, never force). Read owning `docs/` + `tasks/README.md`.
2. **Spec first:** lead writes `.omc/fleet/<run>/spec.md`: goal, non-goals, design, packages with disjoint files (one writer each), failing tests first, per-package acceptance, contracts, overlap with running agents. Report ≤40 lines to the user as work starts.
3. **Persist:** append the design to the owning `docs/` file; unfinished packages → `tasks/T-NNN-*.md` (planning-with-files style: spec/progress/findings). Nothing lives only in chat.
4. **Shared context + bus** in `.omc/fleet/<run>/`: `spec.md`, `contracts.md`, `findings.md`, `bus.jsonl` (append-only `{ts,from,to,kind:question|proposal|vote|decision|blocker|done,text}`; handoffs use the fleet-guards envelope), `board/` (fleet-board: one task file per package/sub-task, atomic claim, file leases, WIP limit, deps, evidence-required done; no ad-hoc status files). Lead creates tasks from the spec; every agent `claim`s before working. Read before starting; append when you decide or need something.
5. **Launch** managers in one message, `run_in_background: true`; each prompt self-contained (goal, spec path, package files, contracts, bus path, effort level, tier rules, output format, boundaries). Managers spawn their tech lead/engineers/scouts in parallel.
6. **TDD at the engineer level:** every engineer writes the failing test first (shown red), then minimal code, pass^3 on new/changed tests, coverage ≥80% on changed files. The tech lead checks red→green evidence before accepting; the manager only confirms acceptance criteria; no one edits tests that grade them after red.
7. **Voting & tie-breaks — never block, never stall:**
   - Decide at the LOWEST level that can; escalate only what it can't. Sub-agents never tie-break above their own tree.
   - Conflict between engineers → tech lead decides. Between tech leads → manager. Between managers (or anything cross-package/architectural) → Opus lead. Major/irreversible/outward-facing or something agents can't solve → lead surfaces to the user ONCE, batched.
   - Votes run in PARALLEL with the work: post `proposal` on the bus, voters (odd number, 3 or 5) reply `vote` within one pass; majority wins, no second round. If voting would stall (even split, no quorum, silent voter), the next level up decides immediately — a vote can never deadlock.
   - Proceed on the best-guess default while escalated, behind the smallest reversible change; reconcile when the decision lands. No permission-waiting on bureaucracy.
8. **Token discipline:** state effort ("quick"/"deep") in every prompt; point at specific files; noisy output → file, tail/grep; reports ≤12 lines (result, paths, evidence, risks; bulk evidence to files); cheapest adequate tier; nobody re-derives what spec.md says. Several reports arriving together: number them `[k/N]` and answer every one, not just the last; a report not yet received is pending, never done.
9. **Integrate & review:** lead reads reports, resolves contract conflicts via the bus, runs the repo gate ONCE (one suite at a time machine-wide). Fresh-context reviewer panel (odd: 3 or 5; diverse tiers/prompts, vote independently before comparing - fleet-guards §3) grades against spec acceptance using executed evidence, correctness gaps only (rubric: one verdict per acceptance item with reason; any claim without executed evidence = VETO/reject; prefer one reviewer on another model family, e.g. codex/gemini); fix → re-review. Authoring and review never share a context.
10. **Close:** evidence (test output, SHAs, screenshots for UI); docs updated in the same change; board tasks `done` with evidence and `board.sh index` run; lead can explain the diff in plain words (5-line human summary); stop everything you started.

## Rules
One writer per file. Chain only when B needs A's output. Commit to `main` with explicit paths, no branches/PRs; follow repo attribution rules. Never `pkill`; kill only your own PIDs. Same failure 3× → stop, fresh architect context.

## Use OMC specialist agents (subagent_type) when they fit
Prefer the oh-my-claudecode agents over generic ones: `oh-my-claudecode:executor` (Sonnet engineer), `:test-engineer` (TDD/red tests, flaky hardening), `:debugger` (root cause), `:explore` (Haiku-class scout), `:planner` / `:architect` / `:analyst` (lead-level design, Opus), `:code-reviewer` / `:security-reviewer` / `:critic` / `:verifier` (fresh-context review panel; vary the types), `:designer` (UI), `:git-master` (commits/rebases), `:writer` (docs). Fall back to `general-purpose` only when none fits. Tiers still apply (cheapest adequate model).

## Delegation contract (default, standing rule 2026-10-03)
- **A manager never writes the code.** It designs a dynamic workflow for its package: spawns senior engineers (Sonnet) who code AND may delegate to cheaper coders and Haiku scouts, then a fresh-context reviewer grades against the acceptance criteria. Every manager can spawn subagents: use agent types that carry the Agent tool (`general-purpose`, `claude`).
- Launch with plain Agent calls. OMC mode skills (`/autopilot`, `/ralph`, `/team`, `/ultrawork`) must not wrap or override this tree; they run their own orchestration and conflict with it.
- One manager per independent unit (e.g. one per site repo), each in its own detached worktree off `origin/main`. The top-level manager keeps pushes, deploys, secrets and any global-auth switch (Vercel login is machine-global: deploy serially per account).
- Every manager prompt: goal, exact paths, boundaries, effort level, round cap (max 2 fix rounds, same failure 3x = stop and report), report format (<=8 lines, real numbers).
