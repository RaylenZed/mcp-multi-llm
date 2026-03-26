# Design: Gemini CLI Fix + Custom OpenAI-Compatible Providers

Date: 2026-03-26

## Overview

Two changes to `mcp-multi-llm`:

1. **Debug and fix Gemini CLI invocation** — the CLI path is found but calls fail silently; add proper error capture to diagnose the root cause, then fix it.
2. **Custom OpenAI-compatible provider support** — allow adding any model (DeepSeek, Qianwen, etc.) via a config file with `name`, `base_url`, `model`, and `api_key`. Each provider gets its own dynamically-registered MCP tool.

---

## Part 1: Gemini CLI Debug & Fix

### Problem

`shutil.which("gemini")` succeeds (CLI is in PATH), but calls return errors or no output. The exact failure is unknown because `stderr` is currently discarded on success paths.

### Fix

**Step 1 — surface the real error:** Modify `CLISession.send()` in `base.py` to always log `stderr` (not just on non-zero exit code). This will reveal the actual failure message from the gemini CLI.

**Step 2 — common root causes to check:**
- Gemini CLI needs `HOME` or `XDG_CONFIG_HOME` to find OAuth tokens — MCP subprocess may not inherit these.
- Non-zero exit even on successful calls (gemini sometimes exits non-zero for cosmetic reasons).
- The subprocess has no TTY; gemini might block waiting for interactive auth confirmation.

**Fix strategy:** Pass the full current environment (`env=os.environ.copy()`) explicitly to `asyncio.create_subprocess_exec` in `base.py`. This ensures `HOME`, `PATH`, and any other env vars gemini needs are present.

**If still broken after env fix:** Convert `GeminiSession` to use API key + HTTP (same as custom providers). Flag this decision in implementation.

---

## Part 2: Custom OpenAI-Compatible Providers

### Config File

Location: `~/.mcp-multi-llm/custom_providers.json`

```json
[
  {
    "name": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": "sk-..."
  },
  {
    "name": "qianwen",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
    "api_key": "sk-..."
  }
]
```

- File is optional — if absent, no custom providers are loaded.
- `name` must be a valid identifier (letters, digits, underscores). Validated at startup.
- Conflicts with built-in names (`claude`, `codex`, `gemini`) are rejected with a clear log warning.

### New Session Class: `OpenAICompatSession`

File: `sessions/openai_compat_session.py`

- Inherits from a new `APISession` base (not `CLISession`) — no subprocess, uses `httpx` for HTTP calls.
- Sends the full conversation history as OpenAI-format `messages` array (not injected into a prompt string).
- Implements the same `send(message, topic)` interface as `CLISession`.
- `available` is `True` by default (no CLI to find); set to `False` if config is malformed.

### Base Class Split

Extract a minimal `BaseSession` from `CLISession`:
- `BaseSession`: holds `history_store`, `available`, and the `send()` contract (abstract).
- `CLISession(BaseSession)`: current subprocess logic.
- `APISession(BaseSession)`: new httpx logic.

### Dynamic Tool Registration

In `server.py`, after loading built-in sessions, load `custom_providers.json` and register tools:

```python
for config in load_custom_providers():
    session = OpenAICompatSession(history_store, **config)
    _all_providers[config["name"]] = session

    def make_tool(s):
        async def discuss(message: str, topic: str = "general") -> str:
            f"""Discuss with {s.provider_name}. Maintains conversation context per topic."""
            return await s.send(message, topic)
        discuss.__name__ = f"discuss_with_{s.provider_name}"
        return discuss

    mcp.tool()(make_tool(session))
```

### Integration with Existing Tools

- `list_available_providers()` — lists custom providers alongside built-ins.
- `group_discuss()` — includes all available custom providers.
- `clear_discussion()` — accepts custom provider names.

### Dependency

Add `httpx` to `pyproject.toml` dependencies.

---

## Architecture Summary

```
BaseSession (abstract: send)
├── CLISession (subprocess)        ← claude, codex, gemini
└── APISession (httpx)             ← custom providers (deepseek, qianwen, ...)
```

---

## Out of Scope

- No UI or CLI for managing the config file — edit JSON directly.
- No per-provider timeout override in this iteration.
- No streaming responses.
