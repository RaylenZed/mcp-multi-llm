# mcp-multi-llm

**Any AI agent as the host, any others as consultants — using your existing subscriptions.**

**任意 AI Agent 做主控，任意其他 Agent 做顾问 — 使用你已有的订阅账号。**

---

## The Idea / 起源

Modern AI coding agents (Claude Code, Codex CLI, Gemini CLI) are powerful individually. But what if they could **discuss with each other**?

现代 AI 编程 Agent（Claude Code、Codex CLI、Gemini CLI）各自都很强大。但如果它们能**互相讨论**呢？

This MCP server enables **any MCP-compatible agent** to consult the others as discussion partners — with full conversation context, native tool capabilities retained, and **zero API keys needed** (uses your CLI subscriptions).

这个 MCP Server 让**任何支持 MCP 的 Agent** 都能将其他 Agent 作为讨论伙伴 — 保留完整的对话上下文和工具能力，**无需 API Key**（使用你的 CLI 订阅账号）。

### Who can be the host? / 谁可以做主控？

Any agent that supports MCP can be the host and call the others:

任何支持 MCP 的 Agent 都可以做主控，调用其他 Agent：

| Host Agent / 主控 | Consults / 咨询 | How / 方式 |
|---|---|---|
| **Claude Code** | Codex + Gemini | Native MCP support |
| **Gemini CLI** | Claude + Codex | `gemini mcp` config |
| **Codex CLI** | Claude + Gemini | `codex mcp` config |
| **Any MCP client** | All of the above | Standard MCP protocol |

The architecture is **symmetric** — there's no privileged "main" model. Whoever you're talking to becomes the host, and the others become consultants.

架构是**对称的** — 没有特权的"主模型"。你在跟谁对话，谁就是主控，其他的就是顾问。

## How It Works / 工作原理

```
┌──────────────────────────────────────┐
│  Any MCP-compatible Host Agent       │
│  (Claude Code / Gemini / Codex / …)  │
└──────────────┬───────────────────────┘
               │ MCP Protocol (stdio)
               ▼
      ┌──────────────────┐
      │  mcp-multi-llm   │
      │  (FastMCP Server) │
      ├──────┬───────────┤
      │      │           │
      ▼      ▼           ▼
   ┌────┐ ┌──────┐ ┌────────────┐
   │Codex│ │Gemini│ │  History    │
   │ CLI │ │ CLI  │ │  Store     │
   └────┘ └──────┘ └────────────┘
     ↑       ↑
     Your subscriptions
     你的订阅账号
```

1. The host agent calls MCP tools like `discuss_with_codex` or `group_discuss`
2. The server spawns CLI subprocesses with conversation history as context
3. Consultant agents respond with their full native tool capabilities (search, code execution, etc.)
4. The host agent synthesizes all perspectives into a final answer

## Features / 功能

| Feature | Description |
|---------|-------------|
| **Host-agnostic** | Any MCP client can be the host — Claude, Gemini, Codex, or custom agents |
| **Multi-LLM Discussion** | Consult Codex (OpenAI) and Gemini (Google) as discussion partners |
| **Context Continuity** | Conversations are scoped by topic — context carries across multiple rounds |
| **Parallel Consultation** | `group_discuss` queries both LLMs simultaneously |
| **Subscription-based** | Uses your existing CLI logins — no API keys, no extra cost |
| **Full Tool Chains** | Consultant agents retain their native abilities (file I/O, search, code execution) |
| **Persistent History** | Conversation history saved to disk, survives restarts |

| 功能 | 说明 |
|------|------|
| **主控无关** | 任何 MCP 客户端都能做主控 — Claude、Gemini、Codex 或自定义 Agent |
| **多 LLM 讨论** | 将 Codex (OpenAI) 和 Gemini (Google) 作为讨论伙伴 |
| **上下文连续** | 按主题(topic)维护对话，多轮讨论保持上下文 |
| **并行咨询** | `group_discuss` 同时向两个 LLM 提问 |
| **基于订阅** | 使用你已有的 CLI 登录凭证 — 无需 API Key，无额外费用 |
| **完整工具链** | 顾问 Agent 保留原生能力（文件读写、搜索、代码执行） |
| **持久化历史** | 对话历史保存到磁盘，重启不丢失 |

## Prerequisites / 前提条件

- **Python** >= 3.13
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- At least one consultant CLI installed and logged in:
  - **[Codex CLI](https://github.com/openai/codex)** — `npm install -g @openai/codex`
  - **[Gemini CLI](https://github.com/google/gemini-cli)** — `npm install -g @google/gemini-cli`

## Installation / 安装

```bash
git clone https://github.com/RaylenZed/mcp-multi-llm.git
cd mcp-multi-llm
uv sync
```

## Configuration / 配置

### As Claude Code host / Claude Code 做主控

Add to `~/.claude.json` under `mcpServers`:

在 `~/.claude.json` 的 `mcpServers` 中添加：

```json
{
  "mcpServers": {
    "multi-llm": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-multi-llm", "python", "server.py"],
      "type": "stdio"
    }
  }
}
```

### As Gemini CLI host / Gemini CLI 做主控

```bash
gemini mcp add multi-llm -- uv run --directory /path/to/mcp-multi-llm python server.py
```

### As Codex CLI host / Codex CLI 做主控

```bash
codex mcp add multi-llm -- uv run --directory /path/to/mcp-multi-llm python server.py
```

Restart your agent and the tools will be available.

重启你的 Agent 后即可使用。

## MCP Tools / 工具列表

### `discuss_with_codex`

Ask Codex (OpenAI o3) a question with topic-scoped context.

向 Codex (OpenAI o3) 提问，按主题维护上下文。

```
message: "What's the best way to handle auth in this architecture?"
topic: "auth-design"
```

### `discuss_with_gemini`

Ask Gemini (Google) a question with topic-scoped context.

向 Gemini (Google) 提问，按主题维护上下文。

```
message: "Review this database schema for potential issues"
topic: "db-review"
```

### `group_discuss`

Query both Codex and Gemini in parallel, get both perspectives.

并行向 Codex 和 Gemini 提问，获取双方观点。

```
message: "Should we use GraphQL or REST for this API?"
topic: "api-design"
```

### `list_discussions`

List all active discussion topics. / 列出所有进行中的讨论主题。

### `clear_discussion`

Clear conversation history for a topic. / 清除某个主题的对话历史。

## Architecture / 架构

```
mcp-multi-llm/
├── server.py              # FastMCP server with 5 tools
├── sessions/
│   ├── base.py            # Base class: subprocess mgmt, timeout, context
│   ├── codex_session.py   # Codex CLI provider (codex exec)
│   └── gemini_session.py  # Gemini CLI provider (gemini -p)
├── history/
│   └── store.py           # Conversation history persistence
└── pyproject.toml
```

### Why CLI instead of API? / 为什么用 CLI 而不是 API？

| | CLI Approach | API Approach |
|---|---|---|
| **Cost** | Uses existing subscriptions | Requires separate API billing |
| **Tools** | Full native tool chains (search, file I/O, code exec) | Bare model, no tools |
| **Auth** | Your existing login | Manage API keys |
| **Capability** | Agent-level (reads files, runs code) | Chat-level (text in, text out) |

### Adding more agents / 添加更多 Agent

The provider pattern is simple to extend. To add a new CLI agent, create a new session class in `sessions/` that implements `_build_command()` and `_parse_output()`. Any CLI tool that accepts a prompt and returns text can be integrated.

Provider 模式易于扩展。要添加新的 CLI Agent，只需在 `sessions/` 中创建新的 session 类，实现 `_build_command()` 和 `_parse_output()`。任何接受提示并返回文本的 CLI 工具都可以集成。

## License / 许可

MIT
