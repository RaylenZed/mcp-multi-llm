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
| **Any MCP client** | Claude + Codex + Gemini | Standard MCP protocol |

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
      ▼      ▼       ▼       ▼
   ┌──────┐ ┌────┐ ┌──────┐ ┌─────────┐
   │Claude│ │Codex│ │Gemini│ │ History  │
   │ CLI  │ │ CLI │ │ CLI  │ │ Store   │
   └──────┘ └────┘ └──────┘ └─────────┘
     ↑        ↑       ↑
     Your subscriptions
     你的订阅账号
```

1. The host agent calls MCP tools like `discuss_with_claude`, `discuss_with_codex`, or `group_discuss`
2. The server spawns CLI subprocesses with conversation history as context
3. Consultant agents respond with their full native tool capabilities (search, code execution, etc.)
4. The host agent synthesizes all perspectives into a final answer

## Features / 功能

| Feature | Description |
|---------|-------------|
| **Host-agnostic** | Any MCP client can be the host — Claude, Gemini, Codex, or custom agents |
| **Multi-LLM Discussion** | Consult Claude (Anthropic), Codex (OpenAI), Gemini (Google) as discussion partners |
| **Custom Providers** | Add any OpenAI-compatible model (DeepSeek, Qianwen, etc.) via a config file — each gets its own MCP tool |
| **Context Continuity** | Conversations are scoped by topic — context carries across multiple rounds |
| **Parallel Consultation** | `group_discuss` queries all available LLMs simultaneously |
| **Subscription-based** | Built-in providers use your existing CLI logins — no API keys needed |
| **Full Tool Chains** | Consultant agents retain their native abilities (file I/O, search, code execution) |
| **Persistent History** | Conversation history saved to disk, survives restarts |

| 功能 | 说明 |
|------|------|
| **主控无关** | 任何 MCP 客户端都能做主控 — Claude、Gemini、Codex 或自定义 Agent |
| **多 LLM 讨论** | 将 Claude (Anthropic)、Codex (OpenAI) 和 Gemini (Google) 作为讨论伙伴 |
| **自定义模型** | 通过配置文件添加任意 OpenAI 兼容模型（DeepSeek、千问等），每个模型自动获得独立 MCP 工具 |
| **上下文连续** | 按主题(topic)维护对话，多轮讨论保持上下文 |
| **并行咨询** | `group_discuss` 同时向所有可用模型提问 |
| **基于订阅** | 内置 provider 使用已有的 CLI 登录凭证 — 无需 API Key |
| **完整工具链** | 顾问 Agent 保留原生能力（文件读写、搜索、代码执行） |
| **持久化历史** | 对话历史保存到磁盘，重启不丢失 |

## Prerequisites / 前提条件

- **Python** >= 3.13
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- At least one consultant CLI installed and logged in:
  - **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** — `npm install -g @anthropic-ai/claude-code`
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

## Usage Guide / 使用教程

> 这一节面向初次使用的用户，用具体场景解释"怎么用、什么时候用"。

### 基本概念

使用前先理解三个概念：

| 概念 | 解释 |
|------|------|
| **主控 (Host)** | 你正在对话的那个 AI，比如 Claude Code |
| **顾问 (Consultant)** | 主控通过这个 MCP server 去调用的其他 AI |
| **话题 (topic)** | 一个对话的标签，同一 topic 的多轮对话共享上下文记忆 |

**你不需要手动调用任何工具。** 你只需要用自然语言告诉主控 AI "去问问 Gemini" 或 "让三个模型都评审一下"，主控会自行决定调用哪个工具。

---

### 场景 1：让三个模型评审你的 PRD / 需求文档

**你对 Claude Code 说：**

```
我有一个新产品的 PRD，请用 group_discuss 让三个模型同时评审，
topic 用 "prd-review"。

以下是 PRD：
[粘贴你的 PRD 内容]
```

**发生了什么：**

```
你 → Claude Code
       ↓ 同时调用
  Claude / Codex / Gemini（三个模型并行读取你的 PRD）
       ↓ 各自返回评审意见
  Claude Code 汇总给你
```

**追问（上下文是连续的）：**

```
针对 Gemini 提到的"技术可行性问题"，让三个模型继续讨论解决方案，
topic 还是 "prd-review"。
```

因为 topic 相同，三个模型都记得刚才的评审内容，可以直接接着讨论。

---

### 场景 2：只问某一个模型

有时候你只想要某个模型的意见，比如让 Gemini 搜索竞品信息（它有实时联网能力）：

```
用 discuss_with_gemini 搜索一下"AI 代码审查工具"的竞品现状，
topic 用 "competitor-research"。
```

或者只让 Codex 做代码架构评审：

```
用 discuss_with_codex 评审一下这段代码的架构，
topic 用 "code-review"。

[粘贴代码]
```

---

### 场景 3：多轮讨论 / 让模型互相"看"对方的回答

这是最强大的用法。你可以把一个模型的回答作为输入，让另一个模型继续评审：

**第一轮：**
```
用 discuss_with_gemini 评审这个数据库设计方案，topic 用 "db-design"。
[粘贴方案]
```

**第二轮（把 Gemini 的回答带给 Codex）：**
```
Gemini 说了上面这些，用 discuss_with_codex 让 Codex 评价 Gemini 的意见，
并给出它自己的建议，topic 还是 "db-design"。
```

**第三轮（三方总结）：**
```
用 group_discuss 问一下：综合前面的讨论，这个数据库设计最大的风险点是什么？
topic 还是 "db-design"。
```

---

### 场景 4：任意项目中使用

这个 MCP server 是**全局生效**的，不绑定任何具体项目。不管你在哪个目录打开 Claude Code，工具都可以用。

典型的非代码用途：

- **商业计划评审**：`group_discuss` 让三个模型从不同角度评估你的商业模式
- **技术选型讨论**：`group_discuss "用 React 还是 Vue？列出各自的理由"`
- **写作润色**：`discuss_with_claude` 润色文章，`discuss_with_gemini` 检查事实
- **面试准备**：`group_discuss` 让三个模型分别出一道你指定方向的面试题

---

### 常见问题

**Q: 某个模型没有响应怎么办？**

运行 `list_available_providers` 工具（告诉 Claude Code "帮我检查哪些模型可用"），它会列出哪些 CLI 已安装、哪些不可用。不可用的 provider 会被自动跳过，不影响其他模型。

**Q: 对话历史会一直保留吗？**

会，保存在 `~/.mcp-multi-llm/history/`。如果你想开启一轮全新的讨论，用 `clear_discussion` 清除指定 topic，或者换一个新的 topic 名字。

**Q: topic 名字有什么规则吗？**

没有规则，随便起。建议用英文短横线格式，方便识别，比如 `prd-review`、`api-design`、`db-v2`。同一个 topic 下，三个模型各自有独立的对话记录（不是共享的），但你可以通过手动传递内容让它们"看到"彼此的回答。

---

## MCP Tools / 工具列表

### `discuss_with_claude`

Ask Claude (Anthropic Opus) a question with topic-scoped context.

向 Claude (Anthropic Opus) 提问，按主题维护上下文。

```
message: "Analyze the trade-offs of this caching strategy"
topic: "caching-design"
```

### `discuss_with_codex`

Ask Codex (OpenAI) a question with topic-scoped context.

向 Codex (OpenAI) 提问，按主题维护上下文。

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

Query Claude, Codex, and Gemini in parallel, get all perspectives.

并行向 Claude、Codex 和 Gemini 提问，获取三方观点。

```
message: "Should we use GraphQL or REST for this API?"
topic: "api-design"
```

### `list_discussions`

List all active discussion topics. / 列出所有进行中的讨论主题。

### `clear_discussion`

Clear conversation history for a topic. / 清除某个主题的对话历史。

## Custom Providers / 自定义模型

支持通过配置文件接入任意 **OpenAI 兼容 API** 的模型（DeepSeek、阿里千问、Moonshot、零一万物等）。

### 配置文件

创建 `~/.mcp-multi-llm/custom_providers.json`：

```json
[
  {
    "name": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": "sk-你的key"
  },
  {
    "name": "qianwen",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
    "api_key": "sk-你的key"
  }
]
```

**重启 MCP 服务**后，每个模型会自动注册为独立工具：`discuss_with_deepseek`、`discuss_with_qianwen`，并参与 `group_discuss` 和 `list_available_providers`。

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | 工具名称，只能用字母/数字/下划线，不能是 `claude`/`codex`/`gemini` |
| `base_url` | ✅ | API 基础地址（到 `/v1` 为止） |
| `model` | ✅ | 模型名称（如 `deepseek-chat`、`qwen-plus`） |
| `api_key` | ✅ | API Key |

### 常用 provider 参考

| 模型 | base_url | 常用 model |
|------|----------|-----------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 阿里千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`、`qwen-max` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 零一万物 | `https://api.lingyiwanwu.com/v1` | `yi-large` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |

> 任何支持 `/chat/completions` 接口（OpenAI 兼容格式）的服务均可接入。

---

## Changing Models / 修改模型

Each provider's default model can be changed in one place:

每个 provider 的默认模型在以下位置修改：

| Provider | 文件 | 修改位置 |
|----------|------|---------|
| **Claude** | `sessions/claude_session.py` line 11 | `model: str = "claude-opus-4-6"` |
| **Gemini** | `sessions/gemini_session.py` line 12 | `model: str = "gemini-2.5-pro"` |
| **Codex** | `~/.codex/config.toml` | `model = "gpt-5.4"` |

> Codex CLI 的模型由全局配置文件控制，不在本项目内。
> 当 Codex 使用 ChatGPT 订阅账号时，**不支持通过 `-m` 参数指定模型**，必须通过 `~/.codex/config.toml` 设置，或留空让 Codex 自动选择当前最高配置。

## Architecture / 架构

```
mcp-multi-llm/
├── server.py                    # FastMCP server, dynamic tool registration
├── sessions/
│   ├── base.py                  # BaseSession (abstract) + CLISession (subprocess)
│   ├── api_session.py           # APISession (httpx, for OpenAI-compatible APIs)
│   ├── claude_session.py        # Claude CLI provider (claude -p)
│   ├── codex_session.py         # Codex CLI provider (codex exec)
│   ├── gemini_session.py        # Gemini CLI provider (gemini -p)
│   ├── openai_compat_session.py # Custom providers via /chat/completions
│   └── provider_config.py       # Load ~/.mcp-multi-llm/custom_providers.json
├── history/
│   └── store.py                 # Conversation history persistence
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

**方式一：API 模型（推荐）** — 编辑 `~/.mcp-multi-llm/custom_providers.json`，重启即可。无需改代码，详见 [Custom Providers](#custom-providers--自定义模型) 一节。

**方式二：CLI 模型** — 在 `sessions/` 中创建新 session 类，继承 `CLISession`，实现 `_build_command()` 和 `_parse_output()`，然后在 `server.py` 中注册。适用于有 CLI 工具的模型。

## License / 许可

MIT
