<p align="center">
  <h1 align="center">🦞 Building My Own Tiny-OpenClaw</h1>
  <p align="center">
    A minimal autonomous AI agent that thinks, uses tools, and chats via Telegram — built from scratch to understand how agents like OpenClaw work.
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white" />
    <img src="https://img.shields.io/badge/Powered%20by-Claude%20claude-opus-4-6-orange?logo=anthropic&logoColor=white" />
    <img src="https://img.shields.io/badge/Interface-Telegram-2CA5E0?logo=telegram&logoColor=white" />
    <img src="https://img.shields.io/badge/License-MIT-green" />
  </p>
</p>

---

## What is this?

This is my from-scratch implementation of a **ReAct (Reason + Act)** AI agent, inspired by the [Tiny-OpenClaw tutorial](https://blog.algomaster.io/p/how-to-build-an-autonomous-ai-agent-like-openclaw) by Ashish Bamania.

The agent:
- Receives messages **and photos** on Telegram
- **Streams responses** in real time — edits the message live as Claude generates tokens
- **Thinks** about what to do using Claude claude-opus-4-6
- **Acts** by calling tools (skills) like web search, browser control, weather, calculator, file ops…
- **Observes** the results and loops until it has a final answer
- **Remembers** facts about you across sessions
- **Analyses images** you send via Claude Vision
- **Schedules reminders** that fire asynchronously after a delay

> This project is a learning exercise — I built every component myself to understand how autonomous agents actually work under the hood.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Tiny-OpenClaw                             │
│                                                                  │
│   User (Telegram)                                                │
│        │                                                         │
│        ▼                                                         │
│  ┌─────────────────┐                                             │
│  │ TelegramChannel │  ← translates Telegram events              │
│  └────────┬────────┘                                             │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐     ┌──────────────────┐                   │
│  │ SessionManager  │────▶│  Conversation    │                   │
│  └─────────────────┘     │  History (JSON)  │                   │
│           │               └──────────────────┘                   │
│           ▼                                                      │
│  ┌─────────────────┐     ┌──────────────────┐                   │
│  │  AgentRuntime   │────▶│  ContextBuilder  │                   │
│  │  (ReAct Loop)  │     │  SOUL + Skills   │                   │
│  └────────┬────────┘     │  + Memory + Time │                   │
│           │               └──────────────────┘                   │
│           ▼                                                      │
│  ┌─────────────────────────────────────────┐                    │
│  │           Anthropic Claude API          │                    │
│  │     (claude-opus-4-6 with tool use)     │                    │
│  └─────────────┬───────────────────────────┘                    │
│                │  tool_use blocks                                │
│                ▼                                                 │
│  ┌─────────────────┐                                             │
│  │   SkillLoader   │  ← dispatches to the right skill           │
│  └────────┬────────┘                                             │
│           │                                                      │
│    ┌──────┴──────────────────────────────────┐                  │
│    ▼          ▼          ▼         ▼         ▼                  │
│  datetime  memory_   browser_  web_      weather  calculator    │
│  skill     work      use       search    skill    skill        │
│            skill     skill     skill                            │
└──────────────────────────────────────────────────────────────────┘
```

### The ReAct Loop

```
User message
     │
     ▼
Build system prompt (SOUL.md + skills + memory + time)
     │
     ▼
Call Anthropic API  ◄─────────────────────────────┐
     │                                             │
     ├── text response? ──► Send to user ──► Done  │
     │                                             │
     └── tool_use blocks? ──► Execute each tool ───┘
                              via SkillLoader
                              (max 5 rounds)
```

---

## Skills (Plugins)

| Skill | Tools | Description |
|-------|-------|-------------|
| `datetime` | `get_current_time` | Returns current UTC date/time |
| `memory_work` | `save_note`, `get_note`, `list_notes`, `delete_note` | Persistent user memory |
| `browser_use` | `browse_url`, `click_element`, `fill_input`, `get_page_content`, `get_page_links` | Full Playwright browser control |
| `web_search` | `search_web` | DuckDuckGo search, no API key needed |
| `weather` | `get_weather` | Current conditions + 3-day forecast via Open-Meteo |
| `calculator` | `calculate` | Safe AST-based math evaluator |
| `file_ops` | `read_file`, `write_file`, `list_files`, `delete_file` | Sandboxed local file access in `workspace/` |
| `reminder` | `set_reminder`, `cancel_reminders` | Async Telegram reminders via asyncio |

> The reference Tiny-OpenClaw has 3 skills. I added **web_search**, **weather**, **calculator**, **file_ops**, and **reminder** — each built from scratch.

---

## File Structure

```
.
├── main.py               # Entry point — wires all components together
├── agent_runtime.py      # ReAct loop + SSE streaming Anthropic client
├── context_builder.py    # Assembles system prompt from all sources
├── skill_loader.py       # Discovers and dispatches skill plugins
├── session_manager.py    # Per-user conversation history (JSON)
├── memory.py             # Key-value persistent store (JSON)
├── telegram_channel.py   # Telegram adapter: text, photos, streaming editor
├── logger.py             # Coloured structured logging
├── make_skill.py         # CLI scaffold for new skills
├── SOUL.md               # Agent personality and rules
├── .env.example          # Environment variable template
├── pyproject.toml        # Dependencies + project metadata
├── Dockerfile            # Container image with Playwright deps
├── docker-compose.yml    # One-command deployment
├── skills/
│   ├── datetime/         # Current time tool
│   ├── memory_work/      # Save/recall user notes (4 tools)
│   ├── browser_use/      # Playwright web automation (5 tools)
│   ├── web_search/       # DuckDuckGo search
│   ├── weather/          # Open-Meteo weather + forecast
│   ├── calculator/       # AST-safe math evaluator
│   ├── file_ops/         # Sandboxed local file read/write/list/delete
│   └── reminder/         # Async Telegram reminders via asyncio
├── workspace/            # Sandbox for file_ops skill (gitkeep'd)
└── tests/
    ├── test_memory.py
    ├── test_session_manager.py
    ├── test_calculator.py
    ├── test_context_builder.py
    └── test_skill_loader.py
```

---

## Setup

### Prerequisites

- Python 3.12+
- A [Telegram bot token](https://t.me/BotFather) (create one via `/newbot`)
- An [Anthropic API key](https://console.anthropic.com/)

### 1 — Clone and install

```bash
git clone https://github.com/abhay-codes07/Building-my-own-Tiny-OpenClaw.git
cd Building-my-own-Tiny-OpenClaw

# Using pip
pip install httpx python-dotenv "python-telegram-bot>=21.0" "playwright>=1.44.0"
playwright install chromium

# Or using uv (faster)
uv pip install httpx python-dotenv "python-telegram-bot>=21.0" "playwright>=1.44.0"
playwright install chromium
```

### 2 — Configure

```bash
cp .env.example .env
# Edit .env and fill in ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN
```

### 3 — Run

```bash
python main.py
```

You'll see:

```
==================================================
  Tiny-OpenClaw starting up…
==================================================
14:32:01  INFO      Memory loaded from MEMORY.json (0 keys)
14:32:01  INFO      Skill loaded: browser_use       (5 tools)
14:32:01  INFO      Skill loaded: calculator        (1 tools)
14:32:01  INFO      Skill loaded: datetime          (1 tools)
14:32:01  INFO      Skill loaded: memory_work       (4 tools)
14:32:01  INFO      Skill loaded: weather           (1 tools)
14:32:01  INFO      Skill loaded: web_search        (1 tools)
14:32:01  INFO      Tiny-OpenClaw is live on Telegram — Go CLAW! 🦞
```

### 4 — Chat

Open Telegram, find your bot, and start chatting:

```
You: What's the weather in Tokyo?
Bot: 🌤 Tokyo: 22°C, Partly cloudy. Wind: 14 km/h, Humidity: 68%.
     Forecast: Fri 24/18°C, Sat 23/17°C, Sun 21/16°C.
```

---

## Docker

```bash
docker build -t tiny-openclaw .
docker run -d \
  -e ANTHROPIC_API_KEY=your_key \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -v $(pwd)/SESSIONS.json:/app/SESSIONS.json \
  -v $(pwd)/MEMORY.json:/app/MEMORY.json \
  tiny-openclaw
```

---

## Telegram Commands

| Command | Action |
|---------|--------|
| `/start` | Greet the bot and initialise your session |
| `/reset` | Wipe your conversation history and start fresh |
| `/info` | Show your session ID, message count, and creation time |

---

## Writing Your Own Skill

1. Create a folder under `skills/`:

```
skills/my_skill/
├── SKILL.md    ← name + description (used in system prompt)
└── handler.py  ← tools list + async execute()
```

2. **`SKILL.md`** format:

```markdown
---
name: my_skill
description: One sentence describing what this skill does.
---
```

3. **`handler.py`** structure:

```python
tools = [
    {
        "name": "my_tool",
        "description": "What this tool does.",
        "parameters": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "..."},
            },
            "required": ["input"],
        },
    }
]

async def execute(tool_name: str, tool_input: dict, context: dict):
    memory = context["memory"]      # Memory instance
    session_id = context["session_id"]

    if tool_name == "my_tool":
        # Do something with tool_input["input"]
        return {"result": "done"}

    return {"error": f"Unknown tool: {tool_name}"}
```

4. Restart `main.py` — the skill is automatically discovered and loaded.

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## Key Design Decisions

| Decision | Reason |
|----------|--------|
| ReAct loop over single-shot | Enables sequential tool use and multi-step reasoning |
| `MAX_TOOL_ROUNDS = 5` | Prevents infinite loops while allowing complex tasks |
| SSE streaming for all rounds | Users see tokens in real time; thinking text in tool rounds is informative |
| `_StreamEditor` throttle (60 chars or 1 s) | Respects Telegram's ~20 edits/min limit without jarring updates |
| Vision as a content block | Anthropic natively supports `image` blocks — no separate vision endpoint needed |
| `asyncio.create_task` for reminders | Fire-and-forget — reminder schedules instantly, fires later without blocking |
| JSON persistence | Zero infrastructure — no database needed for a local agent |
| `workspace/` sandbox for file ops | Path traversal blocked via `os.path.realpath()` comparison |
| AST-based calculator | Avoids `eval()` on untrusted strings — safe math only |
| DuckDuckGo (no key) | Aligns with SOUL.md rules; no API signup required |
| Open-Meteo weather | Completely free, no API key, good coverage |
| Skill plugin system | Add capabilities without touching core agent code |

---

## What I Learned

Building this from scratch taught me:

1. **ReAct is simple but powerful** — the loop is just 30 lines of Python; the intelligence comes from the LLM
2. **Tool schemas are contracts** — the LLM reads `description` fields carefully; good descriptions = better tool use
3. **System prompt layering** — combining personality, skills, memory, and time context gives the LLM everything it needs
4. **Bounded loops matter** — without `MAX_TOOL_ROUNDS`, a confused model can spiral into infinite tool calls
5. **Skills as plugins** — `importlib` dynamic loading makes the architecture clean and extensible
6. **SSE streaming is easy with httpx** — `client.stream()` + `aiter_lines()` handles Anthropic's SSE format cleanly
7. **Vision is just a content block** — sending images to Claude requires no special endpoint, just a base64 block in the message array
8. **asyncio.create_task is perfect for background jobs** — fire-and-forget reminders work reliably without threading

---

<p align="center">Built with curiosity by <a href="https://github.com/abhay-codes07">abhay-codes07</a> • Powered by Claude 🦞</p>
