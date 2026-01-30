-- Cortex Memory Schema

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK(memory_type IN ('conversation', 'observation', 'decision', 'personality', 'action_item', 'fact')),
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    importance REAL DEFAULT 0.5 CHECK(importance >= 0.0 AND importance <= 1.0),
    decay_factor REAL DEFAULT 0.95,
    consolidated_into TEXT REFERENCES memories(id),
    metadata JSON DEFAULT '{}',
    archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('person', 'project', 'organization', 'tool', 'place', 'concept')),
    summary TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_referenced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    memory_id TEXT NOT NULL REFERENCES memories(id),
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS open_loops (
    id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('high', 'medium', 'low')),
    follow_up_question TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    source_memory_id TEXT REFERENCES memories(id),
    metadata JSON DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_key TEXT,
    channel TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    summary TEXT,
    analyzed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prepared_contexts (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    context_summary TEXT,
    open_loops_json JSON,
    selected_memories_json JSON,
    topic_index TEXT,
    priority_topics TEXT,
    prepared_prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
CREATE INDEX IF NOT EXISTS idx_memories_archived ON memories(archived);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_memory ON entity_mentions(memory_id);
CREATE INDEX IF NOT EXISTS idx_open_loops_resolved ON open_loops(resolved_at);
CREATE INDEX IF NOT EXISTS idx_open_loops_priority ON open_loops(priority);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_key);
CREATE INDEX IF NOT EXISTS idx_prepared_contexts_used ON prepared_contexts(used_at);
CREATE INDEX IF NOT EXISTS idx_prepared_contexts_expires ON prepared_contexts(expires_at);
