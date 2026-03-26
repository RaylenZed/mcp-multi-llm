"""Base session manager for LLM CLI providers."""

import asyncio
import logging
import os
import shutil
from abc import ABC, abstractmethod
from history.store import HistoryStore, TopicHistory

logger = logging.getLogger(__name__)


class BaseSession(ABC):
    """Abstract contract for all LLM session providers."""

    provider_name: str = "base"

    def __init__(self, history_store: HistoryStore):
        self.history_store = history_store
        self.available = True

    @abstractmethod
    async def send(self, message: str, topic: str, timeout: int = 300) -> str:
        """Send a message and return a response."""
        ...


class CLISession(BaseSession):
    """Base class for LLM providers that use a CLI subprocess."""

    @abstractmethod
    def _build_command(self, message: str, history: TopicHistory) -> list[str]:
        """Build the CLI command to execute."""
        ...

    @abstractmethod
    def _parse_output(self, stdout: str, stderr: str) -> str:
        """Parse CLI output into clean response text."""
        ...

    def _get_cli_path(self, name: str) -> str | None:
        """Find CLI executable. Returns None and disables provider if not found."""
        path = shutil.which(name)
        if path is None:
            self.available = False
            logger.warning(f"[{self.provider_name}] CLI '{name}' not found in PATH — provider disabled.")
        return path

    async def send(self, message: str, topic: str, timeout: int = 300) -> str:
        """Send a message and get a response, maintaining conversation context."""
        if not self.available:
            return f"[{self.provider_name} unavailable — CLI not installed or not in PATH]"

        history = self.history_store.get_or_create(self.provider_name, topic)
        history.add("user", message)

        cmd = self._build_command(message, history)
        logger.info(f"[{self.provider_name}] Executing: {' '.join(str(c) for c in cmd[:3])}...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),  # explicitly pass full environment
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Always log stderr so failures are diagnosable
            if stderr.strip():
                logger.warning(f"[{self.provider_name}] stderr: {stderr.strip()}")

            if proc.returncode != 0:
                error_msg = f"[{self.provider_name}] Process exited with code {proc.returncode}"
                logger.error(error_msg)
                if stdout.strip():
                    response = self._parse_output(stdout, stderr)
                else:
                    response = f"Error: {error_msg}\nstderr: {stderr.strip()}"
            else:
                response = self._parse_output(stdout, stderr)

            history.add("assistant", response)
            self.history_store.save(self.provider_name, topic)
            return response

        except asyncio.TimeoutError:
            history.add("assistant", "[TIMEOUT]")
            self.history_store.save(self.provider_name, topic)
            return f"Error: {self.provider_name} did not respond within {timeout}s"
        except Exception as e:
            logger.exception(f"[{self.provider_name}] Unexpected error")
            return f"Error: {e}"
