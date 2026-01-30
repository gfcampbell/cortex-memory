# Quinn Memory System — Build Plan

## What This Is
A standalone, modular memory system for Quinn. Provides structured memory storage, semantic retrieval, and prepared context injection across sessions. Inspired by Proteus/Vector's memory architecture.

## Design Principles
- **Standalone module** — no modifications to Clawdbot source
- **Simple interface** — local HTTP service or CLI calls
- **Pluggable** — can be swapped out or retired if Clawdbot builds native memory
- **Local only** — runs on the Mac Mini, no external dependencies
- **Start simple** — get the core loop working first, polish later

## Architecture

```
clawdbot (untouched)
    ↕ reads/writes via CLI or local HTTP
quinn-memory/
    ├── service.py          # Local HTTP API (FastAPI or Flask)
    ├── db/
    │   ├── schema.sql      # SQLite structured store
    │   └── store.py        # CRUD operations
    ├── vector/
    │   └── embeddings.py   # ChromaDB interface
    ├── pipeline/
    │   ├── ingest.py       # Conversation → memories
    │   ├── consolidate.py  # Decay + merge over time
    │   └── entities.py     # People/project extraction
    ├── context/
    │   ├── analyze.py      # Post-session analysis (cheap model)
    │   └── prepare.py      # Build injection-ready prompt
    ├── cli.py              # Command-line interface for testing
    ├── config.yaml         # All tuning in one place
    └── requirements.txt    # Dependencies
```

## Data Model (SQLite)

### memories
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| content | TEXT | The memory text |
| memory_type | TEXT | conversation, observation, decision, personality, action_item |
| source | TEXT | Which conversation/channel it came from |
| created_at | TIMESTAMP | When it happened |
| updated_at | TIMESTAMP | Last modified |
| importance | REAL | 0.0-1.0 score |
| decay_factor | REAL | How fast it loses relevance |
| consolidated_into | TEXT | If merged into another memory, points to that ID |
| metadata | JSON | Flexible extra data |

### entities
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| name | TEXT | Person/project/org name |
| entity_type | TEXT | person, project, organization, tool |
| summary | TEXT | What Quinn knows about them |
| first_seen | TIMESTAMP | First encounter |
| last_referenced | TIMESTAMP | Most recent mention |
| metadata | JSON | Relationships, roles, etc. |

### entity_mentions
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| entity_id | TEXT | FK to entities |
| memory_id | TEXT | FK to memories |
| context | TEXT | How they were mentioned |

### open_loops
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| summary | TEXT | What's unfinished |
| priority | TEXT | high, medium, low |
| follow_up_question | TEXT | Suggested follow-up |
| created_at | TIMESTAMP | When identified |
| resolved_at | TIMESTAMP | NULL if still open |
| source_memory_id | TEXT | FK to memories |
| metadata | JSON | Extra context |

### conversations
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| session_key | TEXT | Clawdbot session identifier |
| channel | TEXT | telegram, webchat, etc. |
| started_at | TIMESTAMP | Session start |
| ended_at | TIMESTAMP | Session end |
| summary | TEXT | Post-session summary |
| analyzed | BOOLEAN | Whether post-processing ran |

### prepared_contexts
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| conversation_id | TEXT | FK to conversations |
| context_summary | TEXT | Summary of where things left off |
| open_loops_json | JSON | Prioritized open loops |
| selected_memories_json | JSON | LLM-chosen memories with reasons |
| topic_index | TEXT | Comma-separated topics |
| priority_topics | TEXT | Top topics |
| prepared_prompt | TEXT | Injection-ready system prompt text |
| created_at | TIMESTAMP | When generated |
| used_at | TIMESTAMP | When injected (NULL if unused) |
| expires_at | TIMESTAMP | TTL (7 days default) |

## Vector Store (ChromaDB)

Single collection: `quinn_memories`
- Documents: memory content text
- Metadata: memory_id, memory_type, created_at, importance
- Embeddings: generated on ingest (ChromaDB default or OpenAI)
- Query: semantic search returns top-N with metadata for joining back to SQLite

## Pipeline

### 1. Ingest (after each conversation)
- Receive conversation transcript
- Extract individual memories (decisions, facts, preferences, action items)
- Extract entities (people, projects mentioned)
- Store in SQLite + embed in ChromaDB
- Identify open loops

### 2. Analyze (post-session, async)
- Take conversation + recent memories (200 window)
- Call cheap model (Haiku or GPT-4o-mini)
- Produce: summary, open loops, selected memories, topic index
- Store as prepared_context

### 3. Prepare (at session start)
- Check for unused prepared_context
- If found: inject into system prompt, mark used
- If expired/missing: fall back to formula-based retrieval (vector search + recent memories + open loops)

### 4. Consolidate (periodic, via cron/heartbeat)
- Review memories older than N days
- Merge related memories into consolidated versions
- Apply decay to importance scores
- Archive or prune low-value memories

## Integration with Clawdbot

**Post-session:** Clawdbot's session transcript → quinn-memory ingest endpoint
**Session start:** quinn-memory prepare endpoint → returns prepared prompt text
**Both are HTTP calls to localhost — no Clawdbot code changes needed.**

Quinn calls these via exec/curl from within Clawdbot sessions, or via cron jobs.

## Build Order

### Phase 1: Foundation (Day 1)
- [ ] Set up project structure and dependencies
- [ ] Create SQLite schema and store.py
- [ ] Set up ChromaDB and embeddings.py
- [ ] Basic CLI for testing (add memory, search, list)

### Phase 2: Pipeline (Day 2)
- [ ] Ingest pipeline — conversation → memories + entities
- [ ] Post-session analyzer — produce prepared context
- [ ] Context preparer — build injection-ready prompt

### Phase 3: Service (Day 3)
- [ ] Local HTTP API (FastAPI)
- [ ] Endpoints: /ingest, /prepare, /search, /memories, /entities, /loops
- [ ] Integration script — Quinn calls service from Clawdbot sessions

### Phase 4: Polish (Day 4-5)
- [ ] Decay and consolidation logic
- [ ] Backfill existing markdown memories
- [ ] Tune prompt engineering for analysis quality
- [ ] Add to launchd for auto-start on boot
- [ ] Documentation

## Dependencies
- Python 3.9+
- chromadb
- sqlite3 (built-in)
- fastapi + uvicorn (for HTTP service)
- anthropic or openai (for analysis calls)
- pydantic (data validation)

## Notes
- Keep config.yaml for all tunable parameters (TTL, decay rates, model choice, etc.)
- Embedding model: start with ChromaDB's default (all-MiniLM-L6-v2), upgrade later if needed
- Analysis model: Haiku (cheap, fast, good enough for curation)
- This is Quinn's brain, not a product. Optimize for Quinn's needs.
