---
name: teams
description: Read and write Microsoft Teams messages via AppleScript desktop automation on macOS, or via Microsoft Graph REST API. Use whenever a user asks to send a Teams message, post to a channel, read Teams chat/inbox, check Teams updates, or automate Microsoft Teams actions. Triggers include "send a Teams message", "teams chat", "post to teams", "read teams", "teams notification".
---

# Microsoft Teams Skill (`teams`)

Control and automate **Microsoft Teams** on macOS and across cloud/CLI workflows.

## Capabilities

1. **AppleScript Desktop Automation (macOS)**:
   - Types and sends messages in the open Microsoft Teams client.
   - Requires Teams to be open or logged in.
   - Zero API setup required.

2. **Microsoft Graph REST API**:
   - Background direct reads and sends without touching the UI window.
   - Requires `TEAMS_ACCESS_TOKEN` environment variable.
   - Reads chats via `GET /v1.0/me/chats` and sends via `POST /v1.0/chats/{id}/messages`.

## CLI Usage

```bash
# Send a message to the currently active Teams chat via AppleScript
teams send "Hello from agent!"

# Send to a specific chat via Microsoft Graph API
teams send "Update on pipeline: tests passed" --chat-id "19:...@thread.v2"

# Read recent chats / messages
teams read --limit 5

# Output machine-readable JSON
teams read -j
teams send "Automated build green" -j
```

## Agent Guidelines

- If running locally on macOS without tokens, use desktop automation (`teams send "<message>"`).
- For scheduled or headless agents, export `TEAMS_ACCESS_TOKEN` for direct Graph API access.
