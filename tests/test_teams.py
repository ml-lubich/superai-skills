"""Tests for Microsoft Teams client and CLI."""

from unittest.mock import patch, MagicMock
from teams_mcp.client import TeamsClient
from click.testing import CliRunner
from teams_mcp.cli import cli


def test_teams_client_applescript_not_running():
    client = TeamsClient()
    with patch.object(client, "_run_osascript", return_value="ERROR: Microsoft Teams process not running"):
        res = client.send_via_applescript("Hello")
        assert res["status"] == "error"
        assert "not running" in res["error"]


def test_teams_client_applescript_success():
    client = TeamsClient()
    with patch.object(client, "_run_osascript", return_value="SUCCESS"):
        res = client.send_via_applescript("Hello", chat_title="Dev Team")
        assert res["status"] == "sent"
        assert res["channel"] == "applescript"
        assert res["chat"] == "Dev Team"


def test_teams_client_graph_api_fallback_no_token():
    client = TeamsClient(token=None)
    with patch.object(client, "send_via_applescript", return_value={"status": "sent", "channel": "applescript"}):
        res = client.send_message("Testing fallback")
        assert res["status"] == "sent"
        assert res["channel"] == "applescript"


def test_teams_client_read_messages_info_when_no_token():
    client = TeamsClient(token=None)
    res = client.read_recent_messages(limit=5)
    assert len(res) == 1
    assert res[0]["status"] == "info"
    assert "Desktop UI integration active" in res[0]["message"]


def test_teams_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Microsoft Teams" in result.output

    result_short = runner.invoke(cli, ["-h"])
    assert result_short.exit_code == 0


def test_teams_cli_read():
    runner = CliRunner()
    result = runner.invoke(cli, ["read", "-j"])
    assert result.exit_code == 0
    assert "Desktop UI integration active" in result.output
