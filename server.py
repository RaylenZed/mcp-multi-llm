"""MCP Multi-LLM Server — Any agent as host, others as consultants."""

import asyncio
import logging
from fastmcp import FastMCP

from history.store import HistoryStore
from sessions.base import BaseSession
from sessions.claude_session import ClaudeSession
from sessions.codex_session import CodexSession
from sessions.gemini_session import GeminiSession
from sessions.openai_compat_session import OpenAICompatSession
from sessions.provider_config import load_custom_providers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "multi-llm",
    instructions=(
        "Multi-LLM discussion server. Use these tools to consult with "
        "Claude (Anthropic), Codex (OpenAI), Gemini (Google), and any custom providers "
        "for second opinions, code review, architecture discussions, and collaborative "
        "problem-solving. Each conversation is scoped by a 'topic' to maintain context "
        "continuity. Use list_available_providers first to see which consultants are available."
    ),
)

history_store = HistoryStore()
claude = ClaudeSession(history_store)
codex = CodexSession(history_store)
gemini = GeminiSession(history_store)

_all_providers: dict[str, BaseSession] = {"claude": claude, "codex": codex, "gemini": gemini}


# --- Load custom providers from config ---
def _make_discuss_tool(session: BaseSession):
    """Create a typed discuss tool function for a custom provider."""
    provider_name = session.provider_name

    async def discuss(message: str, topic: str = "general") -> str:
        return await session.send(message, topic)

    discuss.__name__ = f"discuss_with_{provider_name}"
    discuss.__qualname__ = f"discuss_with_{provider_name}"
    discuss.__doc__ = (
        f"Discuss with {provider_name}. Maintains conversation context per topic.\n\n"
        f"Args:\n"
        f"    message: What to ask or discuss.\n"
        f"    topic: Conversation topic for context continuity (e.g. 'auth-refactor', 'api-design')."
    )
    return discuss


for _cfg in load_custom_providers():
    _session = OpenAICompatSession(
        history_store=history_store,
        name=_cfg.name,
        base_url=_cfg.base_url,
        model=_cfg.model,
        api_key=_cfg.api_key,
    )
    _all_providers[_cfg.name] = _session
    mcp.tool()(_make_discuss_tool(_session))
    logger.info(f"[server] Registered custom provider: {_cfg.name}")


# --- Built-in tools ---

@mcp.tool()
async def list_available_providers() -> str:
    """List which LLM providers are available for consultation."""
    available = [name for name, s in _all_providers.items() if s.available]
    unavailable = [name for name, s in _all_providers.items() if not s.available]
    lines = []
    if available:
        lines.append("Available: " + ", ".join(available))
    if unavailable:
        lines.append("Not installed: " + ", ".join(unavailable) +
                     " (check installation or configuration and restart the server)")
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
        return "No providers available. Install at least one CLI (claude, codex, gemini) or add custom providers."

    tasks = {name: s.send(message, topic) for name, s in active.items()}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    sections = []
    for name, result in zip(tasks.keys(), results):
        resp = result if not isinstance(result, Exception) else f"Error: {result}"
        sections.append(f"=== {name} ===\n{resp}")

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
        provider: Optional — provider name, or None to clear for all providers.
    """
    providers = [provider] if provider else list(_all_providers.keys())
    for p in providers:
        history_store.clear_topic(p, topic)
    return f"Cleared discussion '{topic}' for {', '.join(providers)}."


if __name__ == "__main__":
    mcp.run()
