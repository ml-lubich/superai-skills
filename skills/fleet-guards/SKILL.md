---
name: fleet-guards
description: Guards for multi-agent work from AI Agents in Depth ch.10 - decide if multi-agent is worth it, pick shared vs isolated context and topology (manager / peer proposer-reviewer / decentralized handoff), then apply guards against the six failure modes (file conflicts, cascading errors, homogeneous convergence, buck-passing, runaway loops, comprehension debt). Use before launching any fleet/subagents/team and when reviewing their output. Triggers - "should this be multi-agent", "which topology", "agents disagree", "agents looping", "review panel", "handoff", "mutual check", "verify the workers", "A2A".
---

# fleet-guards — apply before launch and at review

Section numbers refer to AI Agents in Depth, ch.10. Digest: `~/.claude/reference/ai-agents-in-depth-ch10.md`. Pair with `fleet-board` (task tracking) and `spec-fleet` (org chart). "Own:" marks rules that are mine, not the book's.

## 0. Is multi-agent worth it? (§10.2)
Single test: **does the extra agent bring information the first one couldn't get while producing its answer?**
- Yes -> test execution, rendered screenshots, tool/fact checks, a different data source, parallel coverage of an open search space. Use multiple agents.
- No -> same model re-reading or debating the same text. At equal compute it matches a single agent; self-review without new evidence can make things *worse* (§10.4.3.2). Use one agent.
- Cost: multi-agent research ran ~15x the tokens of chat; token spend explained ~80% of the gain. Gain must beat that.
- Own: also go multi-agent when the context would overflow (isolation keeps each context lean, §10.4.4 translation case) or the work splits into disjoint file sets.

## 1. Shared vs isolated context (§10.1.1, §10.3)
- **Shared** (next agent inherits the whole trajectory): zero loss, but context bloat and role inertia. Use for short role switches; carry the role as a loaded Skill (keeps prompt cache) unless the role needs a hard tool/permission boundary, then a separate agent with restricted tools.
- **Isolated** (default for fleets): exchange via tool params (typed, small), shared files (big/persistent, use fleet-board), or a bus (async). Pass **paths, not contents**.

## 2. Topology (§10.1.2, §10.4.3-5)
| Pattern | Use when | Watch |
|---|---|---|
| Peer, 2-3 agents (proposer-reviewer) | one artifact to improve, external evidence available | needs a real verifier + round cap |
| Manager (orchestrator-workers) | many subtasks, dependencies, dynamic scheduling | manager = bottleneck: give it the strongest model + best prompt (Plan-and-Act); keep only a file index in its context |
| Manager-written workflow | fan-out shape known up front | write the graph as code (Workflow `pipeline/parallel/agent`), runtime executes, agents return schema'd conclusions |
| Decentralized handoff | roles decide who's next; avoid manager single point of failure | cycles: carry `visited` + budget, reject repeats |
Parallel manager: settle on **first verified** success, not first claimed; settle once (lock), then cancel the rest and wait for acks (§10.4.4).

## 3. Guards per failure mode (§10.5)
MAST taxonomy: design flaws, inter-agent misalignment, missing verification. Agent faults are usually Byzantine (plausible but wrong), so require independent evidence.
1. **Concurrent writes (§10.5.1):** exclusive file leases via fleet-board; parallel coders in separate worktrees, merge once at the end; cross-file semantic contracts in `contracts.md`, checked at integration. Own: never `git add -A` in a shared tree.
2. **Cascading errors (§10.5.2):** every handoff is lossy. Before building on upstream output, re-check the *raw evidence* (run the test, open the file), ignore the upstream reasoning. Handoffs carry evidence (envelope below), not conclusions alone.
3. **Homogeneous convergence (§10.5.3):** 18 of 30 identical agents picked the same branch name. Reviewers must differ: model tier, prompt/role, visible evidence or tools. Vote **independently first, compare after** (no shared draft before voting). Namespace shared resources (`<run>-<agent>-*` branch/file names), cap concurrency.
4. **Passing the buck (§10.5.4):** exactly one accountable owner per task (board `owner`); objective priorities, resource ownership and permissions fixed before launch; repeated cross-blame or a deadlock after 2 rounds -> lead decides, or one batched question to the human.
5. **Runaway loops (§10.5.5):** every loop has max rounds (own default 3 review rounds), a token/step budget sized to task difficulty (§10.2 budget-awareness: explore early, narrow late), a spawn cap, cancellation that cascades to children (§10.4.2), and a stop rule: same failure 3x -> stop, fresh context/architect.
6. **Comprehension debt (§10.5.6):** the lead must be able to explain the diff in plain words before accepting; after each integration post a <=10-line human summary (what changed, why, what to look at). "You can outsource thinking, not understanding."
Also premature termination (§10.4.3.1): partial work, giving up after one failed path, false success. "Done" is a claim until a verifier proves it.

## 4. Mutual-check / iterative-improvement loop (§10.4.3.2)
```
candidate = proposer(task, constraints)
loop up to MAX_ROUNDS while budget:
  evidence = execute_or_render(candidate)        # tests, screenshot, tool check - NEW information
  review   = reviewer(candidate, evidence)       # fresh context, different tier/prompt, sees evidence not proposer's story
  if review.pass: publish(candidate, evidence, review); stop
  candidate = proposer.repair(candidate, review.findings)   # findings = exact fix + what must be true after
escalate_or_reject(review)
```
Reviewer cannot edit tests, the evidence collector or the gate. Proposer cannot approve itself. Only verified results advance the board (LoopX: "the model may propose done, it cannot approve its own done").

## 5. Handoff envelope (A2A-style, §10.4.2, §10.4.5, §10.4.6)
Write as JSON in the task's `## Notes`, or a line in `bus.jsonl`:
```json
{"task_id":"T-007","from":"eng-a","to":"reviewer-1","type":"task_assigned|status_update|result|needs_input|terminate",
 "state":"submitted|in_progress|needs_input|completed|failed",
 "goal":"...","acceptance":["..."],"constraints":["..."],"accepted_facts":["..."],
 "artifacts":["src/parser.py","logs/T-007-pytest.txt"],"evidence":"12 passed x3; sha abc123",
 "remaining_budget":{"rounds":2,"tokens":40000},"visited":["lead","eng-a"]}
```
Recipient rejects if `to` is already in `visited` (cycle) or budget <= 0 (escalate). Opaque: share tasks and artifacts, never private reasoning or full trajectories.

## Pre-launch checklist
[ ] §0 test passed (new info or disjoint work)  [ ] topology chosen + why  [ ] every task: one owner, disjoint files, acceptance  [ ] reviewers diverse + independent  [ ] round/budget/spawn caps set  [ ] lead can explain the plan in 5 lines
