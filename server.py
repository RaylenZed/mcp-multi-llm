"""MCP Multi-LLM Server — Discuss with Codex and Gemini from Claude Code."""

import asyncio
import logging
from fastmcp import FastMCP

from history.store import HistoryStore
from sessions.codex_session import CodexSession
from sessions.gemini_session import GeminiSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize
mcp = FastMCP(
    "multi-llm",
    instructions=(
        "Multi-LLM discussion server. Use these tools to consult with "
        "Codex (OpenAI) and Gemini (Google) for second opinions, code review, "
        "architecture discussions, and collaborative problem-solving. "
        "Each conversation is scoped by a 'topic' to maintain context continuity."
    ),
)

history_store = HistoryStore()
codex = CodexSession(history_store)
gemini = GeminiSession(history_store)


@mcp.tool()
async def discuss_with_codex(message: str, topic: str = "general") -> str:
    """Discuss with Codex (OpenAI o3). Maintains conversation context per topic.

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
    """Ask both Codex and Gemini the same question in parallel, get both perspectives.

    Args:
        message: The question or topic to discuss with both LLMs.
        topic: Conversation topic for context continuity.
    """
    codex_task = codex.send(message, topic)
    gemini_task = gemini.send(message, topic)

    results = await asyncio.gather(codex_task, gemini_task, return_exceptions=True)

    codex_resp = results[0] if not isinstance(results[0], Exception) else f"Error: {results[0]}"
    gemini_resp = results[1] if not isinstance(results[1], Exception) else f"Error: {results[1]}"

    return (
        f"=== Codex (OpenAI) ===\n{codex_resp}\n\n"
        f"=== Gemini (Google) ===\n{gemini_resp}"
    )


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
        provider: Optional - "codex", "gemini", or None for both.
    """
    providers = [provider] if provider else ["codex", "gemini"]
    for p in providers:
        history_store.clear_topic(p, topic)
    return f"Cleared discussion '{topic}' for {', '.join(providers)}."


if __name__ == "__main__":
    mcp.run()
