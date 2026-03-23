"""Codex CLI session provider."""

import re
from sessions.base import CLISession
from history.store import HistoryStore, TopicHistory


class CodexSession(CLISession):
    provider_name = "codex"

    def __init__(self, history_store: HistoryStore, model: str | None = None):
        super().__init__(history_store)
        self.model = model  # None = let Codex pick default (works for ChatGPT subscribers)
        self.cli_path = self._get_cli_path("codex")

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
        cmd = [self.cli_path, "exec", "--skip-git-repo-check", "--ephemeral"]
        if self.model:
            cmd.extend(["-m", self.model])
        cmd.append(prompt)
        return cmd

    def _parse_output(self, stdout: str, stderr: str) -> str:
        """Parse Codex output, stripping ANSI codes and progress noise."""
        # Strip ANSI escape codes
        text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', stdout)
        # Strip carriage returns and progress lines
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Skip progress indicators
            if stripped.startswith(("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")):
                continue
            lines.append(line)
        return "\n".join(lines).strip() or "(no output)"
