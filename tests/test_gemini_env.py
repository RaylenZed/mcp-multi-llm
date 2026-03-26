"""Test that CLISession passes the full environment to subprocesses."""
import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from history.store import HistoryStore
from sessions.base import CLISession


class _EchoSession(CLISession):
    """Minimal concrete CLISession that echoes env var MY_TEST_VAR."""
    provider_name = "echo"

    def __init__(self, history_store):
        super().__init__(history_store)
        self.available = True
        self.cli_path = "env"  # always exists

    def _build_command(self, message, history):
        return ["env"]  # prints all env vars

    def _parse_output(self, stdout, stderr):
        return stdout


@pytest.mark.asyncio
async def test_cli_session_passes_full_env():
    """CLISession must pass os.environ to the subprocess."""
    os.environ["MY_TEST_VAR"] = "hello_from_test"
    store = HistoryStore()
    session = _EchoSession(store)
    result = await session.send("ping", "test-topic")
    assert "MY_TEST_VAR=hello_from_test" in result, (
        f"Expected env var in subprocess output, got:\n{result}"
    )
