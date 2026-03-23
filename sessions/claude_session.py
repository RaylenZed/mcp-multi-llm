"""Claude Code CLI session provider."""

import re
from sessions.base import CLISession
from history.store import HistoryStore, TopicHistory


class ClaudeSession(CLISession):
    provider_name = "claude"

    def __init__(self, history_store: HistoryStore, model: str = "sonnet"):
        super().__init__(history_store)
        self.model = model
        self.cli_path = self._get_cli_path("claude")

    def _build_prompt_with_context(self, message: str, history: TopicHistory) -> str:
        """Build a prompt that includes conversation history for context continuity."""
        if len(history.messages) <= 1:
            return message

        context = history.format_for_prompt(max_messages=10)
        return (
            f"Previous conversation context:\n{context}\n\n"
            f"Current question/request:\n{message}"
        )

    def _build_command(self, message: str, history: TopicHistory) -> list[str]:
        prompt = self._build_prompt_with_context(message, history)
        return [
            self.cli_path,
            "-p", prompt,
            "--model", self.model,
            "--no-session-persistence",
            "--permission-mode", "bypassPermissions",
            "--bare",
        ]

    def _parse_output(self, stdout: str, stderr: str) -> str:
        """Parse Claude CLI output, stripping ANSI codes."""
        text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', stdout)
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")):
                continue
            lines.append(line)
        return "\n".join(lines).strip() or "(no output)"
