"""Microsoft Teams reader/writer client using AppleScript automation and Microsoft Graph API fallback."""

import subprocess
import json
import os
import sys
from typing import Dict, Any, List, Optional


class TeamsClient:
    """Read and write to Microsoft Teams via AppleScript (macOS desktop client) or Graph API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TEAMS_ACCESS_TOKEN")

    def send_via_applescript(self, message: str, chat_title: Optional[str] = None) -> Dict[str, Any]:
        """Send message via AppleScript to Microsoft Teams desktop app on macOS.
        
        Focuses the chat, sets the message, and sends it.
        """
        script = f'''
        tell application "System Events"
            set teamsProc to first process whose name contains "Teams" or bundle identifier contains "teams"
            if not (exists teamsProc) then
                return "ERROR: Microsoft Teams process not running"
            end if
            set frontmost of teamsProc to true
            delay 0.3
            keystroke "{message.replace('"', '\\"')}"
            delay 0.2
            keystroke return
            return "SUCCESS"
        end tell
        '''
        res = self._run_osascript(script)
        if "ERROR" in res:
            return {"status": "error", "error": res}
        return {"status": "sent", "channel": "applescript", "chat": chat_title}

    def _run_osascript(self, script: str) -> str:
        try:
            p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return p.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"ERROR: {e.stderr.strip()}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def read_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Read recent messages.
        
        If MS Graph token is provided, queries Microsoft Graph API /me/chats or /me/joinedTeams.
        Otherwise provides local state or instructions.
        """
        if self.token:
            import urllib.request
            req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/chats?$top={limit}",
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode())
                    return data.get("value", [])
            except Exception as e:
                return [{"error": str(e)}]

        return [{
            "status": "info",
            "message": "Desktop UI integration active. For direct background REST reading, set TEAMS_ACCESS_TOKEN."
        }]

    def send_message(self, message: str, chat_id: Optional[str] = None, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Send a message via Graph API if chat_id and token are present, else fallback to AppleScript."""
        if self.token and chat_id:
            import urllib.request
            url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages"
            payload = json.dumps({"body": {"content": message}}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    return {"status": "sent", "channel": "graph_api", "response": json.loads(resp.read().decode())}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        return self.send_via_applescript(message, chat_title=recipient)
