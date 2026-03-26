# Gemini Fix + Custom OpenAI-Compatible Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Gemini CLI invocation (pass full env vars, capture stderr for diagnosis) and add support for custom OpenAI-compatible providers (DeepSeek, Qianwen, etc.) via a JSON config file with dynamic MCP tool registration.

**Architecture:** Split `CLISession` base into `BaseSession` (abstract contract) → `CLISession` (subprocess) and `APISession` (httpx). Load `~/.mcp-multi-llm/custom_providers.json` at startup, create `OpenAICompatSession` instances, and dynamically register individual `discuss_with_<name>` tools via FastMCP.

**Tech Stack:** Python 3.13, FastMCP, httpx 0.28.1, asyncio, pytest

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `sessions/base.py` | Add `BaseSession` abstract, fix env passthrough in `CLISession`, always log stderr |
| Create | `sessions/api_session.py` | `APISession` base using httpx for OpenAI-compatible HTTP calls |
| Create | `sessions/openai_compat_session.py` | `OpenAICompatSession` — wraps `APISession` with config-driven provider details |
| Create | `sessions/provider_config.py` | Load and validate `~/.mcp-multi-llm/custom_providers.json` |
| Modify | `server.py` | Load custom providers, register dynamic tools, update `group_discuss` / `list_available_providers` / `clear_discussion` |
| Modify | `pyproject.toml` | Add `httpx>=0.28` to dependencies |
| Create | `tests/test_provider_config.py` | Tests for config loading and validation |
| Create | `tests/test_openai_compat_session.py` | Tests for `OpenAICompatSession` using httpx mock |
| Create | `tests/test_gemini_env.py` | Test that CLISession passes full env to subprocess |

---

## Task 1: Fix `CLISession` — pass full env, always log stderr

**Files:**
- Modify: `sessions/base.py`

- [ ] **Step 1: Read current `base.py`** (already done in exploration — proceed)

- [ ] **Step 2: Write failing test** — create `tests/test_gemini_env.py`

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/test_gemini_env.py -v
```

Expected: FAIL — either `MY_TEST_VAR` not in output (env not passed) or import error.

- [ ] **Step 4: Update `sessions/base.py`** — add `import os`, pass env, always log stderr

Replace the `asyncio.create_subprocess_exec(...)` call block in `CLISession.send()`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/test_gemini_env.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
git add sessions/base.py tests/test_gemini_env.py
git commit -m "fix: pass full env to CLI subprocesses, always log stderr, extract BaseSession"
```

---

## Task 2: Add `httpx` to dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add httpx to pyproject.toml**

In `pyproject.toml`, change the dependencies block to:

```toml
dependencies = [
    "fastmcp>=3.1.1",
    "httpx>=0.28",
]
```

- [ ] **Step 2: Verify httpx is importable in venv**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/python -c "import httpx; print(httpx.__version__)"
```

Expected: `0.28.1` (already installed)

- [ ] **Step 3: Commit**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
git add pyproject.toml
git commit -m "build: add httpx>=0.28 dependency"
```

---

## Task 3: Create `APISession` base and `OpenAICompatSession`

**Files:**
- Create: `sessions/api_session.py`
- Create: `sessions/openai_compat_session.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_openai_compat_session.py`

```python
"""Tests for OpenAICompatSession — httpx-based OpenAI-compatible provider."""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from history.store import HistoryStore
from sessions.openai_compat_session import OpenAICompatSession


def make_session(name="deepseek"):
    store = HistoryStore()
    return OpenAICompatSession(
        history_store=store,
        name=name,
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key="sk-test",
    )


def mock_response(content: str) -> MagicMock:
    """Build a fake httpx.Response with OpenAI-style JSON."""
    response = MagicMock(spec=httpx.Response)
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return response


@pytest.mark.asyncio
async def test_send_returns_model_content():
    """Session sends message and returns model reply."""
    session = make_session()
    with patch.object(session._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response("Hello from DeepSeek!")
        result = await session.send("Hi", "test")
    assert result == "Hello from DeepSeek!"


@pytest.mark.asyncio
async def test_send_builds_correct_payload():
    """Session sends correct OpenAI-format payload."""
    session = make_session()
    with patch.object(session._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response("ok")
        await session.send("What is 2+2?", "math")

    call_kwargs = mock_post.call_args
    payload = call_kwargs.kwargs["json"]
    assert payload["model"] == "deepseek-chat"
    assert payload["messages"][-1] == {"role": "user", "content": "What is 2+2?"}


@pytest.mark.asyncio
async def test_send_http_error_returns_error_string():
    """HTTP errors are caught and returned as readable error strings."""
    session = make_session()
    with patch.object(session._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock(status_code=401)
        )
        result = await session.send("Hi", "test")
    assert "Error" in result
    assert "deepseek" in result.lower() or "401" in result


@pytest.mark.asyncio
async def test_provider_name_set_correctly():
    """provider_name matches the name passed to constructor."""
    session = make_session("qianwen")
    assert session.provider_name == "qianwen"


@pytest.mark.asyncio
async def test_available_true_by_default():
    """API sessions are available by default (no CLI to find)."""
    session = make_session()
    assert session.available is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/test_openai_compat_session.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'sessions.openai_compat_session'`

- [ ] **Step 3: Create `sessions/api_session.py`**

```python
"""Base class for HTTP-based (non-CLI) LLM providers."""

import httpx
import logging
from abc import abstractmethod
from history.store import HistoryStore
from sessions.base import BaseSession

logger = logging.getLogger(__name__)


class APISession(BaseSession):
    """Base for providers accessed via HTTP API (not CLI subprocess)."""

    def __init__(self, history_store: HistoryStore, base_url: str, api_key: str):
        super().__init__(history_store)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=300.0,
        )

    @abstractmethod
    async def send(self, message: str, topic: str, timeout: int = 300) -> str:
        ...
```

- [ ] **Step 4: Create `sessions/openai_compat_session.py`**

```python
"""OpenAI-compatible HTTP session provider (DeepSeek, Qianwen, etc.)."""

import logging
import httpx
from history.store import HistoryStore, TopicHistory
from sessions.api_session import APISession

logger = logging.getLogger(__name__)


class OpenAICompatSession(APISession):
    """Session for any provider with an OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        history_store: HistoryStore,
        name: str,
        base_url: str,
        model: str,
        api_key: str,
    ):
        super().__init__(history_store, base_url=base_url, api_key=api_key)
        self.provider_name = name
        self.model = model

    def _build_messages(self, message: str, history: TopicHistory) -> list[dict]:
        """Build OpenAI-format messages array from history + current message."""
        messages = []
        # Include up to 10 prior turns for context
        for msg in history.messages[-10:]:
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        # Current message is already added to history before this is called,
        # so the last item in history IS the current message — don't double-add.
        return messages

    async def send(self, message: str, topic: str, timeout: int = 300) -> str:
        """Send a message to the OpenAI-compatible endpoint and return the reply."""
        history = self.history_store.get_or_create(self.provider_name, topic)
        history.add("user", message)

        messages = self._build_messages(message, history)
        logger.info(f"[{self.provider_name}] POST /chat/completions model={self.model}")

        try:
            response = await self._client.post(
                "/chat/completions",
                json={"model": self.model, "messages": messages},
            )
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"]

            history.add("assistant", reply)
            self.history_store.save(self.provider_name, topic)
            return reply

        except httpx.HTTPStatusError as e:
            error = f"Error: [{self.provider_name}] HTTP {e.response.status_code}"
            logger.error(error)
            return error
        except Exception as e:
            error = f"Error: [{self.provider_name}] {e}"
            logger.exception(f"[{self.provider_name}] Unexpected error")
            return error
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/test_openai_compat_session.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
git add sessions/api_session.py sessions/openai_compat_session.py tests/test_openai_compat_session.py
git commit -m "feat: add APISession and OpenAICompatSession for HTTP-based providers"
```

---

## Task 4: Create `provider_config.py` — load and validate config file

**Files:**
- Create: `sessions/provider_config.py`
- Create: `tests/test_provider_config.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_provider_config.py`

```python
"""Tests for custom provider config loading."""
import json
import pytest
from pathlib import Path
from sessions.provider_config import load_custom_providers, ProviderConfig


def write_config(tmp_path: Path, data) -> Path:
    p = tmp_path / "custom_providers.json"
    p.write_text(json.dumps(data))
    return p


def test_load_valid_config(tmp_path):
    """Valid config returns list of ProviderConfig objects."""
    cfg_path = write_config(tmp_path, [
        {"name": "deepseek", "base_url": "https://api.deepseek.com/v1",
         "model": "deepseek-chat", "api_key": "sk-123"},
    ])
    providers = load_custom_providers(cfg_path)
    assert len(providers) == 1
    assert providers[0].name == "deepseek"
    assert providers[0].model == "deepseek-chat"
    assert providers[0].api_key == "sk-123"


def test_load_missing_file_returns_empty(tmp_path):
    """Missing config file returns empty list (not an error)."""
    providers = load_custom_providers(tmp_path / "nonexistent.json")
    assert providers == []


def test_invalid_name_is_skipped(tmp_path):
    """Entries with invalid names (spaces, hyphens) are skipped with a warning."""
    cfg_path = write_config(tmp_path, [
        {"name": "bad name!", "base_url": "https://x.com", "model": "m", "api_key": "k"},
        {"name": "valid", "base_url": "https://x.com", "model": "m", "api_key": "k"},
    ])
    providers = load_custom_providers(cfg_path)
    assert len(providers) == 1
    assert providers[0].name == "valid"


def test_builtin_name_is_skipped(tmp_path):
    """Entries named 'claude', 'codex', or 'gemini' are rejected."""
    cfg_path = write_config(tmp_path, [
        {"name": "claude", "base_url": "https://x.com", "model": "m", "api_key": "k"},
    ])
    providers = load_custom_providers(cfg_path)
    assert providers == []


def test_missing_required_field_is_skipped(tmp_path):
    """Entries missing required fields are skipped."""
    cfg_path = write_config(tmp_path, [
        {"name": "deepseek", "model": "deepseek-chat", "api_key": "sk-123"},  # no base_url
    ])
    providers = load_custom_providers(cfg_path)
    assert providers == []


def test_load_multiple_providers(tmp_path):
    """Multiple valid entries all load correctly."""
    cfg_path = write_config(tmp_path, [
        {"name": "deepseek", "base_url": "https://api.deepseek.com/v1",
         "model": "deepseek-chat", "api_key": "sk-a"},
        {"name": "qianwen", "base_url": "https://dashscope.aliyuncs.com/v1",
         "model": "qwen-plus", "api_key": "sk-b"},
    ])
    providers = load_custom_providers(cfg_path)
    assert len(providers) == 2
    assert {p.name for p in providers} == {"deepseek", "qianwen"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/test_provider_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'sessions.provider_config'`

- [ ] **Step 3: Create `sessions/provider_config.py`**

```python
"""Load and validate custom provider configs from ~/.mcp-multi-llm/custom_providers.json."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILTIN_NAMES = {"claude", "codex", "gemini"}
_VALID_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
_DEFAULT_CONFIG_PATH = Path.home() / ".mcp-multi-llm" / "custom_providers.json"


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str


def load_custom_providers(path: Path | None = None) -> list[ProviderConfig]:
    """Load custom providers from a JSON config file.

    Returns an empty list if the file doesn't exist or has no valid entries.
    Invalid entries are skipped with a warning log.
    """
    if path is None:
        path = _DEFAULT_CONFIG_PATH

    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[provider_config] Failed to read {path}: {e}")
        return []

    if not isinstance(raw, list):
        logger.error(f"[provider_config] {path} must contain a JSON array, got {type(raw).__name__}")
        return []

    providers = []
    for i, entry in enumerate(raw):
        name = entry.get("name", "")
        base_url = entry.get("base_url", "")
        model = entry.get("model", "")
        api_key = entry.get("api_key", "")

        if not all([name, base_url, model, api_key]):
            logger.warning(f"[provider_config] Entry {i}: missing required field(s) — skipping")
            continue

        if not _VALID_NAME.match(name):
            logger.warning(f"[provider_config] Entry {i}: name '{name}' is not a valid identifier — skipping")
            continue

        if name in _BUILTIN_NAMES:
            logger.warning(f"[provider_config] Entry {i}: name '{name}' conflicts with a built-in provider — skipping")
            continue

        providers.append(ProviderConfig(name=name, base_url=base_url, model=model, api_key=api_key))

    logger.info(f"[provider_config] Loaded {len(providers)} custom provider(s) from {path}")
    return providers
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/test_provider_config.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
git add sessions/provider_config.py tests/test_provider_config.py
git commit -m "feat: add provider_config loader with validation"
```

---

## Task 5: Wire custom providers into `server.py`

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Replace `server.py` with the updated version**

```python
"""MCP Multi-LLM Server — Any agent as host, others as consultants."""

import asyncio
import logging
from fastmcp import FastMCP

from history.store import HistoryStore
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

_all_providers: dict = {"claude": claude, "codex": codex, "gemini": gemini}


# --- Load custom providers from config ---
def _make_discuss_tool(session: OpenAICompatSession):
    """Create a typed discuss tool function for a custom provider."""
    provider_name = session.provider_name

    async def discuss(message: str, topic: str = "general") -> str:
        return await session.send(message, topic)

    discuss.__name__ = f"discuss_with_{provider_name}"
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
```

- [ ] **Step 2: Verify server imports cleanly**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/python -c "import server; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 3: Run all tests**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
git add server.py
git commit -m "feat: wire custom OpenAI-compatible providers into server with dynamic tool registration"
```

---

## Task 6: Smoke-test Gemini and verify full server

**Files:** None (manual verification)

- [ ] **Step 1: Run server locally and check startup log**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/python server.py 2>&1 | head -20
```

Expected: server starts, no crash, gemini shows as available.

- [ ] **Step 2: Check Gemini stderr appears in logs**

Restart the MCP server from Claude Code settings, then invoke `discuss_with_gemini` with a simple message. Check the server log output for any `[gemini] stderr:` lines — this reveals what Gemini CLI is actually complaining about.

- [ ] **Step 3: If Gemini still fails — check specific error**

Common fixes based on stderr output:
- `"Could not find credentials"` → env var `HOME` not being set: already fixed by `env=os.environ.copy()`
- `"Unknown model"` → update default model in `gemini_session.py`
- `"Non-interactive mode not supported"` → add `--no-tty` or equivalent flag if gemini CLI has one

- [ ] **Step 4: Final test run**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 5: Final commit if any fixes were made in Task 6**

```bash
cd /Users/raylenzed/Github/mcp-multi-llm
git add -p
git commit -m "fix: resolve gemini CLI invocation issue"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `sessions/base.py` | Extract `BaseSession`, fix env passthrough, always log stderr |
| `sessions/api_session.py` | New — httpx base for API providers |
| `sessions/openai_compat_session.py` | New — OpenAI-compatible HTTP session |
| `sessions/provider_config.py` | New — load/validate `custom_providers.json` |
| `server.py` | Wire custom providers, dynamic tool registration |
| `pyproject.toml` | Add httpx dependency |
| `tests/test_gemini_env.py` | New — env passthrough test |
| `tests/test_openai_compat_session.py` | New — HTTP session tests |
| `tests/test_provider_config.py` | New — config loading tests |
