"""Microsoft Teams MCP server and CLI."""

import sys
import json
import click
from rich.console import Console
from rich.table import Table
from teams_mcp.client import TeamsClient

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    """Microsoft Teams automation CLI and MCP server."""
    pass


@cli.command("send")
@click.argument("message")
@click.option("--chat-id", "-c", help="Microsoft Graph chat ID (if using Graph API)")
@click.option("--recipient", "-r", help="Recipient or window title filter")
@click.option("-j", "--json", "as_json", is_flag=True, help="Output JSON result")
def send_cmd(message: str, chat_id: str, recipient: str, as_json: bool):
    """Send a message to Microsoft Teams (via AppleScript UI or Graph API)."""
    client = TeamsClient()
    res = client.send_message(message=message, chat_id=chat_id, recipient=recipient)
    if as_json:
        console.print(json.dumps(res))
    else:
        if res.get("status") == "sent":
            console.print(f"[bold green]✓ Message sent to Teams via {res.get('channel')}[/bold green]")
        else:
            console.print(f"[bold red]✗ Failed to send message:[/bold red] {res.get('error')}")


@cli.command("read")
@click.option("--limit", "-l", default=10, type=int, help="Number of messages or chats to retrieve")
@click.option("-j", "--json", "as_json", is_flag=True, help="Output JSON result")
def read_cmd(limit: int, as_json: bool):
    """Read recent messages or chats from Microsoft Teams."""
    client = TeamsClient()
    res = client.read_recent_messages(limit=limit)
    if as_json:
        console.print(json.dumps(res, indent=2))
        return

    table = Table(title="Microsoft Teams Recent Messages / Status")
    table.add_column("Property", style="cyan")
    table.add_column("Details", style="green")

    for item in res:
        if "error" in item:
            table.add_row("Error", item["error"])
        elif "status" in item:
            table.add_row(item.get("status", "info"), item.get("message", ""))
        else:
            table.add_row(item.get("id", "Chat"), item.get("topic", item.get("chatType", "Direct")))

    console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
