# Cortex Memory

**A local-first memory system for AI assistants that actually remembers.**

Most AI memory is either dumb chat history or basic RAG (vector search and pray). Cortex is a full **memory lifecycle** — ingest, embed, curate, prepare, inject — inspired by production therapeutic AI systems that need to deeply know their users across sessions.

## Why This Exists

AI assistants wake up fresh every session. They search their notes, hope the right stuff comes back, and often miss context that matters. Cortex fixes this with a **between-sessions brain** — it thinks about what happened *after* you leave, and has structured context ready *before* you come back.

The key insight: **the best time to prepare for the next conversation is right after the current one ends.** Not at session start, when you're already behind.

## What It Does

### 🧠 Structured Memory Store (SQLite)
- **Memories** — facts, decisions, observations, personality traits, action items
- **Entities** — people, projects, organizations with relationship tracking
- **Open Loops** — unfinished threads with priority and follow-up questions
- **Conversations** — session tracking and analysis status
- **Prepared Contexts** — pre-built, injection-ready prompts for next session

### 🔍 Semantic Search (ChromaDB)
Every memory is embedded locally using ChromaDB's built-in model (all-MiniLM-L6-v2). Search by meaning, not just keywords.

### 🔄 Post-Session Analysis
After a conversation ends, a cheap/fast model (Claude Haiku by default) analyzes the conversation against your recent 200 memories and produces:
- **Context summary** — where things left off
- **Open loops** — what's unfinished, prioritized, with follow-up questions
- **Selected memories** — LLM-chosen relevant memories with reasons
- **Topic index** — semantic map of what's been discussed
- **Injection-ready prompt** — formatted text ready to drop into a system prompt

### 📋 Session Start Injection
Next session, Cortex serves the prepared context (or falls back to formula-based retrieval if none exists). The assistant starts the conversation already knowing what matters.

### 📉 Memory Decay
Importance scores decay over time. Old, low-value memories get archived. Your context window stays focused on what's relevant now.

## Architecture

```
your-ai-assistant (untouched)
    ↕ HTTP calls to localhost:8420
cortex-memory/
    ├── service.py          # FastAPI local HTTP service
    ├── cli.py              # Command-line interface
    ├── db/
    │   ├── schema.sql      # SQLite structured store
    │   └── store.py        # CRUD operations
    ├── vector/
    │   └── embeddings.py   # ChromaDB interface
    ├── pipeline/
    │   ├── ingest.py       # Conversation → memories
    │   ├── consolidate.py  # Decay + merge
    │   └── entities.py     # People/project extraction
    ├── context/
    │   ├── analyze.py      # Post-session analysis
    │   └── prepare.py      # Build injection-ready prompt
    ├── config.yaml         # All tuning in one place
    └── seed_entities.yaml  # Your people/projects (private, git-ignored)
```

**Key design principle:** Cortex is a standalone module. It doesn't modify your AI assistant's code. It's a service your assistant talks to via HTTP or CLI. Upgrade your assistant, Cortex keeps running. Swap Cortex out, your assistant still works.

## Quick Start

### 1. Install

```bash
pip install cortex-memory[anthropic]
# or: pip install cortex-memory[openai]
# or: pip install cortex-memory[all]
```

Or from source:
```bash
git clone https://github.com/gfcampbell/cortex-memory.git
cd cortex-memory
pip install -e ".[all]"
```

### 2. Setup

```bash
cortex init
```

Interactive wizard walks you through:
- Choose analysis provider (Anthropic or OpenAI)
- Enter your API key (stored locally in `~/.cortex/.env`)
- Configure service port
- Optionally seed entities (people, projects your AI knows about)

### 3. Start the Service

```bash
cortex start
# 🧠 Cortex Memory starting on http://127.0.0.1:8420
```

For persistent background service on macOS:
```bash
# Copy the launchd plist (see docs/launchd.md)
launchctl load ~/Library/LaunchAgents/com.cortex.memory.plist
```

## CLI Usage

```bash
# Store a memory
cortex remember "User prefers direct communication" --type personality --importance 0.9

# Semantic search
cortex search "communication preferences"

# View open loops
cortex loops

# List known entities
cortex entities

# Get prepared context for session injection
cortex context

# Run post-session analysis
cortex analyze --text "User: Let's redesign the API..."

# Apply memory decay
cortex decay

# View recent memories
cortex recent

# System stats
cortex stats
```

## HTTP API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service status |
| GET | `/stats` | Memory statistics |
| POST | `/memory` | Store a new memory |
| POST | `/search` | Semantic search |
| GET | `/context` | Get prepared context for injection |
| POST | `/analyze` | Run post-session analysis |
| GET | `/loops` | List open loops |
| POST | `/loops` | Create an open loop |
| POST | `/loops/{id}/resolve` | Resolve an open loop |
| GET | `/entities` | List known entities |
| POST | `/entity` | Add/update an entity |
| GET | `/recent` | Recent memories |
| POST | `/ingest` | Ingest a full conversation |
| POST | `/decay` | Apply importance decay |

### Example: Store a memory

```bash
curl -X POST http://127.0.0.1:8420/memory \
  -H "Content-Type: application/json" \
  -d '{"content": "User prefers dark mode", "memory_type": "personality", "importance": 0.7}'
```

### Example: Get session context

```bash
curl http://127.0.0.1:8420/context
```

## How It Works (The Loop)

```
┌─────────────────────────────────────────────┐
│              CONVERSATION                    │
│  User talks to AI assistant normally         │
│  Cortex stores memories as they happen       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           POST-SESSION ANALYSIS              │
│  Cheap model analyzes conversation           │
│  + recent 200 memories                       │
│  → Open loops, selected memories,            │
│    topic index, context summary              │
│  → Stored as prepared_context (7-day TTL)    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           NEXT SESSION START                 │
│  GET /context returns prepared prompt        │
│  → Injected into system prompt               │
│  → Assistant opens with open loop follow-up  │
│  → Marked as used (won't repeat)             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           PERIODIC MAINTENANCE               │
│  Memory decay (importance * 0.95 daily)      │
│  Consolidation (merge old related memories)  │
│  Archive (remove below threshold)            │
└─────────────────────────────────────────────┘
```

## Configuration

Edit `config.yaml`:

```yaml
database:
  path: ./data/cortex.db

vector:
  path: ./data/chroma
  collection: cortex_memories

analysis:
  model: claude-haiku-4-5   # cheap model for post-session analysis
  memory_window: 200         # memories to consider

context:
  ttl_days: 7               # prepared context expiry
  max_open_loops: 5
  max_memories: 10

consolidation:
  decay_rate: 0.95           # daily multiplier
  min_importance: 0.1        # archive below this

service:
  host: 127.0.0.1
  port: 8420
```

## What This Is NOT

- **Not a chatbot.** Cortex is infrastructure — a memory layer that any AI assistant can plug into.
- **Not cloud-dependent.** Everything runs locally. Your memories stay on your machine.
- **Not a framework.** No opinions about how your AI assistant works. Just a service with an API.
- **Not a vector-search-and-pray RAG system.** Structured data + semantic search + LLM curation. The combination is what makes it work.

## Background

This architecture is distilled from a production therapeutic AI system that needs to deeply know its users across hundreds of sessions. The key innovations — prepared contexts, open loop tracking, between-session analysis, and LLM-curated memory selection — emerged from building AI that makes people feel genuinely understood.

Cortex packages those insights into a portable, local-first module that any AI assistant can use.

## License

MIT — do whatever you want with it.

## Author

Created by [Gerry Campbell](https://linkedin.com/in/gcampbell) — distilled from a year of building production AI memory systems.
