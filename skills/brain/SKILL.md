---
name: brain
description: The always-on drafts-only inbox agent (open-brain, `brain` CLI). Use when the user asks about the persistent/background agent, the "brain", auto-drafts, the approval queue, the daily briefing, why a draft did or didn't get created, or when adding a new channel or changing what the background agent watches. Triggers include "brain", "the daemon", "the always-on thing", "why didn't it draft", "approve that", "what's queued", "the briefing".
---

# brain: the persistent drafts-only agent

Claude Code hooks are session-lifecycle only. They cannot fire on incoming mail,
so the heartbeat lives in the OS scheduler (launchd on macOS) and Claude is the
worker it wakes up. Install: `superai-skills init` installs the `brain` CLI;
`superai-skills init --with-brain-daemon` also sets up the scheduled job.

```
scheduler job: brain (every 10 min)
  `- brain tick
       |- snapshot of the watched channels -> ~/.config/brain/context.md
       |- fingerprint vs ~/.config/brain/state
       |    unchanged -> exit, no Claude invoked, no tokens spent
       `- changed -> claude -p (headless, restricted tools)
            |- EMAIL     -> unsent draft in the mail app
            |- IMSG / WA -> proposal line appended to ~/.config/brain/queue.jsonl
            `- notify: desktop notification

scheduler job: brain-watchdog (every 5 min)
  `- brain watchdog -> stale heartbeat? job unloaded? headless child hung?
       non-destructive recovery ladder, circuit breaker after 3 attempts/6h

scheduler job: brain-digest (daily)
  `- brain digest -> short briefing
```

## Commands

| Command | Does |
|---|---|
| `brain init` | Write `~/.config/brain/config.toml`. Refuses until `from_address` is set; edit the file, rerun. |
| `brain install` / `uninstall` | Manage the scheduler jobs. Idempotent. |
| `brain tick` | One poll cycle. What the scheduler runs. Safe to run by hand. `--dry` builds the snapshot without invoking Claude; `--force` invokes it regardless. |
| `brain reply` | Scheduled drafting pass for mail. Drafts only. `--dry` previews. |
| `brain queue` | Show pending message proposals, numbered. |
| `brain approve N` | Print proposal N so you can send it yourself, then remove it from the queue. Sends nothing. |
| `brain drop N` | Discard proposal N. |
| `brain digest` | Generate the briefing now. |
| `brain status` | Last tick, queue depth, scheduler state. |
| `brain log [n]` | Tail the activity log. |
| `brain doctor` | Per-channel health. Non-zero exit if broken. |
| `brain channels` | What is discovered and how each is approved. |
| `brain watchdog` | Recover a stalled agent. `--check` reports only, `--reset` clears the breaker. |
| `brain health` | Whole-system table: jobs, heartbeat, breaker, channels. |

## Resilience

`brain watchdog` runs on its own timer, offset from the tick so one wedged
process cannot take both down. Its ladder, all non-destructive:

1. hung headless child -> SIGTERM, SIGKILL after a grace period
2. job missing -> reload
3. heartbeat stale (more than 3 missed cycles) -> kick one tick
4. breaker open (3 attempts in 6h) -> stop acting, alert only

The kill is surgical: it only signals a PID a tick itself recorded in
`tick.pid`, re-verified as a live headless `claude -p`. Interactive Claude
sessions are never a target. Keep the test guarding this passing.

## The safety model: do not weaken this

- The agent is drafts-only. The headless run uses `--allowedTools` limited to
  reads, edits, and creating mail drafts. Every send and autodraft command is in
  `--disallowedTools`. Headless Claude cannot send anything.
- Email approval is the mail app itself: drafts sit unsent, sync to your phone,
  and you press send. No custom approval UI exists or should be built.
- Message (iMessage/WhatsApp) proposals sit in the queue. `brain approve N`
  prints the text for you to send yourself; it does not send.
- If asked to let it auto-send, say no and explain this boundary. The
  drafts-only guarantee is the design, and a test fails if any code path gains
  a way to send.

## Files

| Path | Is |
|---|---|
| `~/.config/brain/config.toml` | Settings (`from_address`, accounts, channels). |
| `~/.config/brain/queue.jsonl` | Pending proposals, one JSON object per line. |
| `~/.config/brain/context.md` | Latest snapshot the agent reads. |
| `~/.config/brain/state` | Last fingerprint, the token-saving gate. |
| `~/.config/brain/brain.log` | Activity log. |

## Debugging

- Nothing happening: `brain status`, and if the jobs are missing, `brain install`.
- A channel gone quiet: `brain doctor` names the reason.
- Ticking but never drafting: `brain log 40`. "no change, skipping claude" every
  cycle means the fingerprint is stuck; check `~/.config/brain/context.md` has
  content and the channel CLIs are not erroring inside the snapshot.
- Scheduler jobs get a minimal PATH. Any binary a channel shells out to must be
  on the PATH the service definition states.
- On macOS, missing Full Disk Access is the usual cause when a channel goes silent.

## Extending it

New channel: add one module under the package's `channels/` directory
subclassing `Channel`. Discovery is automatic, with no registry to edit. Channels
have no `send` method by design. Then reinstall the tool and run `brain doctor`.
Do not add a database, a web dashboard, or a queue daemon: mail drafts plus one
JSONL file is the design, and it is deliberate.
