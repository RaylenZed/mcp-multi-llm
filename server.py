"""MCP Multi-LLM Server — Any agent as host, others as consultants."""

import asyncio
import logging
from fastmcp import FastMCP

from history.store import HistoryStore
from sessions.claude_session import ClaudeSession
from sessions.codex_session import CodexSession
from sessions.gemini_session import GeminiSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "multi-llm",
    instructions=(
        "Multi-LLM discussion server. Use these tools to consult with "
        "Claude (Anthropic), Codex (OpenAI), and Gemini (Google) for second opinions, "
        "code review, architecture discussions, and collaborative problem-solving. "
        "Each conversation is scoped by a 'topic' to maintain context continuity. "
        "Use list_available_providers first to see which consultants are installed."
    ),
)

history_store = HistoryStore()
claude = ClaudeSession(history_store)
codex = CodexSession(history_store)
gemini = GeminiSession(history_store)

_all_providers = {"claude": claude, "codex": codex, "gemini": gemini}


@mcp.tool()
async def list_available_providers() -> str:
    """List which LLM CLI providers are installed and available for consultation."""
    available = [name for name, s in _all_providers.items() if s.available]
    unavailable = [name for name, s in _all_providers.items() if not s.available]
    lines = []
    if available:
        lines.append("Available: " + ", ".join(available))
    if unavailable:
        lines.append("Not installed: " + ", ".join(unavailable) +
                     " (install their CLI and restart the server)")
    return "\n".join(lines) or "No providers available."


@mcp.tool()
async def discuss_with_claude(message: str, topic: str = "general") -> str:
    """Discuss with Claude (Anthropic Sonnet). Maintains conversation context per topic.

    Args:
        message: What to ask or discuss with Claude.
        topic: Conversation topic for context continuity (e.g. "auth-refactor", "api-design").
    """
    return await claude.send(message, topic)


@mcp.tool()
async def discuss_with_codex(message: str, topic: str = "general") -> str:
    """Discuss with Codex (OpenAI). Maintains conversation context per topic.

    Args:
        message: What to ask or discuss with Codex.
        topic: Conversation topic for context continuity (e.g. "auth-refactor", "api-design").
    """
    return await codex.send(message, topic)


@mcp.tool()
async def discuss_with_gemini(message: str, topic: str = "general") -> str:
    """Discuss with Gemini (Google). Maintains conversation context per topic.

    Args:
        message: What to ask or discuss with Gemini.
        topic: Conversation topic for context continuity (e.g. "auth-refactor", "api-design").
    """
    return await gemini.send(message, topic)


@mcp.tool()
async def group_discuss(message: str, topic: str = "general") -> str:
    """Ask all available LLMs the same question in parallel. Skips providers not installed.

    Args:
        message: The question or topic to discuss with all available LLMs.
        topic: Conversation topic for context continuity.
    """
    active = {name: s for name, s in _all_providers.items() if s.available}
    if not active:
        return "No providers available. Install at least one CLI (claude, codex, gemini)."

    tasks = {name: s.send(message, topic) for name, s in active.items()}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    sections = []
    for name, result in zip(tasks.keys(), results):
        label = {"claude": "Claude (Anthropic)", "codex": "Codex (OpenAI)", "gemini": "Gemini (Google)"}.get(name, name)
        resp = result if not isinstance(result, Exception) else f"Error: {result}"
        sections.append(f"=== {label} ===\n{resp}")

    return "\n\n".join(sections)


@mcp.tool()
async def list_discussions() -> str:
    """List all active discussion topics across providers."""
    topics = history_store.list_topics()
    if not topics:
        return "No active discussions."
    return "Active discussions:\n" + "\n".join(f"  - {t}" for t in topics)


@mcp.tool()
async def clear_discussion(topic: str, provider: str | None = None) -> str:
    """Clear conversation history for a topic.

    Args:
        topic: The topic to clear.
        provider: Optional - "claude", "codex", "gemini", or None for all.
    """
    providers = [provider] if provider else list(_all_providers.keys())
    for p in providers:
        history_store.clear_topic(p, topic)
    return f"Cleared discussion '{topic}' for {', '.join(providers)}."


if __name__ == "__main__":
    mcp.run()
