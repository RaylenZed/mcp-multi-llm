# mcp-multi-llm

**Let Claude Code discuss with Codex and Gemini — using your existing subscriptions.**

**让 Claude Code 和 Codex、Gemini 展开讨论 — 使用你已有的订阅账号。**

---

## The Idea / 起源

When using Claude Code to solve complex problems, wouldn't it be great to get second opinions from other AI agents — in real time, within the same workflow?

在用 Claude Code 解决复杂问题时，如果能在同一个工作流中实时获取其他 AI 的观点，岂不是更好？

This MCP server makes it happen. Claude can now consult **OpenAI Codex CLI** and **Google Gemini CLI** as discussion partners — with full conversation context, tool capabilities retained, and **zero API keys needed** (uses your CLI subscriptions).

这个 MCP Server 让这一切成为现实。Claude 现在可以把 **OpenAI Codex CLI** 和 **Google Gemini CLI** 作为讨论伙伴 — 保留完整的对话上下文和工具能力，**无需 API Key**（使用你的 CLI 订阅账号）。

## How It Works / 工作原理

```
┌─────────────┐
│ Claude Code  │
│  (You ↔ AI)  │
└──────┬───────┘
       │ MCP Protocol
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

1. Claude Code calls MCP tools like `discuss_with_codex` or `group_discuss`
2. The server spawns CLI subprocesses with conversation history as context
3. Codex/Gemini respond with their full native tool capabilities (search, code execution, etc.)
4. Claude synthesizes all perspectives into a final answer

## Features / 功能

| Feature | Description |
|---------|-------------|
| **Multi-LLM Discussion** | Consult Codex (OpenAI) and Gemini (Google) from within Claude Code |
| **Context Continuity** | Conversations are scoped by topic — context carries across multiple rounds |
| **Parallel Consultation** | `group_discuss` queries both LLMs simultaneously |
| **Subscription-based** | Uses your existing CLI logins — no API keys, no extra cost |
| **Full Tool Chains** | Codex and Gemini retain their native abilities (file I/O, search, code execution) |
| **Persistent History** | Conversation history saved to disk, survives restarts |

| 功能 | 说明 |
|------|------|
| **多 LLM 讨论** | 在 Claude Code 中咨询 Codex (OpenAI) 和 Gemini (Google) |
| **上下文连续** | 按主题(topic)维护对话，多轮讨论保持上下文 |
| **并行咨询** | `group_discuss` 同时向两个 LLM 提问 |
| **基于订阅** | 使用你已有的 CLI 登录凭证 — 无需 API Key，无额外费用 |
| **完整工具链** | Codex 和 Gemini 保留原生能力（文件读写、搜索、代码执行） |
| **持久化历史** | 对话历史保存到磁盘，重启不丢失 |

## Prerequisites / 前提条件

- **Python** >= 3.13
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **[Codex CLI](https://github.com/openai/codex)** — `npm install -g @openai/codex` (logged in)
- **[Gemini CLI](https://github.com/google/gemini-cli)** — `npm install -g @google/gemini-cli` (logged in)

## Installation / 安装

```bash
git clone https://github.com/raylenzed/mcp-multi-llm.git
cd mcp-multi-llm
uv sync
```

### Configure in Claude Code / 在 Claude Code 中配置

Add to your `~/.claude.json` under `mcpServers`:

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

Restart Claude Code and the tools will be available.

重启 Claude Code 后即可使用。

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

## License / 许可

MIT
