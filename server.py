"""MCP Multi-LLM Server — Any agent as host, others as consultants."""

import asyncio
import atexit
import logging
import os
from fastmcp import FastMCP

from history.store import HistoryStore
from sessions.base import BaseSession
from sessions.claude_session import ClaudeSession
from sessions.codex_session import CodexSession
from sessions.openai_compat_session import OpenAICompatSession
from sessions.anthropic_compat_session import AnthropicCompatSession
from sessions.provider_config import load_custom_providers, load_builtin_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "multi-llm",
    instructions=(
        "Multi-LLM discussion server. Use these tools to consult with "
        "Claude (Anthropic), Codex (OpenAI), and any custom providers (Gemini, MiniMax, etc.) "
        "for second opinions, code review, architecture discussions, and collaborative "
        "problem-solving. Each conversation is scoped by a 'topic' to maintain context "
        "continuity. Use list_available_providers first to see which consultants are available."
    ),
)

history_store = HistoryStore()

# --- Built-in providers: Claude and Codex ---
# Mode is "cli" by default; set to "api" in ~/.mcp-multi-llm/settings.json to use HTTP API instead.
_builtin_settings = load_builtin_settings()

_claude_cfg = _builtin_settings.get("claude")
if _claude_cfg and _claude_cfg.mode == "api":
    _api_key = _claude_cfg.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    claude: BaseSession = AnthropicCompatSession(
        history_store=history_store,
        name="claude",
        base_url=_claude_cfg.base_url or "https://api.anthropic.com",
        model=_claude_cfg.model or "claude-opus-4-6",
        api_key=_api_key,
    )
    if not _api_key:
        claude.available = False
        logger.warning("[claude] mode=api but ANTHROPIC_API_KEY not set — provider disabled.")
    logger.info("[claude] mode=api")
else:
    claude = ClaudeSession(history_store)

_codex_cfg = _builtin_settings.get("codex")
if _codex_cfg and _codex_cfg.mode == "api":
    _api_key = _codex_cfg.api_key or os.environ.get("OPENAI_API_KEY", "")
    codex: BaseSession = OpenAICompatSession(
        history_store=history_store,
        name="codex",
        base_url=_codex_cfg.base_url or "https://api.openai.com/v1",
        model=_codex_cfg.model or "gpt-4o",
        api_key=_api_key,
    )
    if not _api_key:
        codex.available = False
        logger.warning("[codex] mode=api but OPENAI_API_KEY not set — provider disabled.")
    logger.info("[codex] mode=api")
else:
    codex = CodexSession(history_store)

_all_providers: dict[str, BaseSession] = {"claude": claude, "codex": codex}


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
    if _cfg.protocol == "anthropic":
        _session = AnthropicCompatSession(
            history_store=history_store,
            name=_cfg.name,
            base_url=_cfg.base_url,
            model=_cfg.model,
            api_key=_cfg.api_key,
        )
    else:
        _session = OpenAICompatSession(
            history_store=history_store,
            name=_cfg.name,
            base_url=_cfg.base_url,
            model=_cfg.model,
            api_key=_cfg.api_key,
            extra_body=_cfg.extra_body,
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
    """Discuss with Claude (Anthropic). Maintains conversation context per topic.

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
async def group_discuss(message: str, topic: str = "general") -> str:
    """Ask all available LLMs the same question in parallel. Skips providers not installed.

    Args:
        message: The question or topic to discuss with all available LLMs.
        topic: Conversation topic for context continuity.
    """
    active = {name: s for name, s in _all_providers.items() if s.available}
    if not active:
        return "No providers available. Install at least one CLI (claude, codex) or add custom providers."

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


def _shutdown_api_sessions():
    """Close httpx clients for API-based sessions on process exit."""
    loop = asyncio.new_event_loop()
    for session in _all_providers.values():
        if hasattr(session, "aclose"):
            try:
                loop.run_until_complete(session.aclose())
            except Exception:
                pass
    loop.close()


atexit.register(_shutdown_api_sessions)


if __name__ == "__main__":
    mcp.run()
