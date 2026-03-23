"""Gemini CLI session provider."""

import json
import re
from sessions.base import CLISession
from history.store import HistoryStore, TopicHistory


class GeminiSession(CLISession):
    provider_name = "gemini"

    def __init__(self, history_store: HistoryStore, model: str | None = None, yolo: bool = True):
        super().__init__(history_store)
        self.model = model
        self.yolo = yolo
        self.cli_path = self._get_cli_path("gemini")

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
        cmd = [self.cli_path, "-p", prompt]
        if self.model:
            cmd.extend(["-m", self.model])
        if self.yolo:
            cmd.append("--yolo")
        # Use text output for easier parsing
        cmd.extend(["-o", "text"])
        return cmd

    def _parse_output(self, stdout: str, stderr: str) -> str:
        """Parse Gemini output."""
        # Strip ANSI escape codes
        text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', stdout)
        # Clean up
        lines = []
        for line in text.splitlines():
            # Skip empty spinner/progress lines
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")):
                continue
            lines.append(line)
        return "\n".join(lines).strip() or "(no output)"
