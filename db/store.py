"""SQLite store for Quinn's memory system."""

import sqlite3
import json
import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "quinn_memory.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db() -> sqlite3.Connection:
    """Get a database connection, creating the DB if needed."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def new_id() -> str:
    return str(uuid.uuid4())


# --- Memories ---

def add_memory(
    content: str,
    memory_type: str = "observation",
    source: str = None,
    importance: float = 0.5,
    metadata: dict = None
) -> str:
    """Store a new memory. Returns the memory ID."""
    conn = get_db()
    mid = new_id()
    conn.execute(
        """INSERT INTO memories (id, content, memory_type, source, importance, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (mid, content, memory_type, source, importance, json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()
    return mid


def get_memory(memory_id: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_memories(
    memory_type: str = None,
    min_importance: float = None,
    limit: int = 50,
    include_archived: bool = False
) -> list[dict]:
    """Search memories with filters."""
    conn = get_db()
    query = "SELECT * FROM memories WHERE 1=1"
    params = []
    
    if not include_archived:
        query += " AND archived = 0"
    if memory_type:
        query += " AND memory_type = ?"
        params.append(memory_type)
    if min_importance is not None:
        query += " AND importance >= ?"
        params.append(min_importance)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recent_memories(limit: int = 200) -> list[dict]:
    """Get most recent memories (for analysis window)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM memories WHERE archived = 0 ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_importance(memory_id: str, importance: float):
    conn = get_db()
    conn.execute(
        "UPDATE memories SET importance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (importance, memory_id)
    )
    conn.commit()
    conn.close()


def archive_memory(memory_id: str, consolidated_into: str = None):
    conn = get_db()
    conn.execute(
        "UPDATE memories SET archived = 1, consolidated_into = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (consolidated_into, memory_id)
    )
    conn.commit()
    conn.close()


# --- Entities ---

def add_entity(
    name: str,
    entity_type: str = "person",
    summary: str = None,
    metadata: dict = None
) -> str:
    """Add a new entity. Returns entity ID."""
    conn = get_db()
    eid = new_id()
    conn.execute(
        """INSERT INTO entities (id, name, entity_type, summary, metadata)
           VALUES (?, ?, ?, ?, ?)""",
        (eid, name, entity_type, summary, json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()
    return eid


def get_entity_by_name(name: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM entities WHERE LOWER(name) = LOWER(?)", (name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_entity(entity_id: str, summary: str = None, metadata: dict = None):
    conn = get_db()
    if summary is not None:
        conn.execute(
            "UPDATE entities SET summary = ?, last_referenced = CURRENT_TIMESTAMP WHERE id = ?",
            (summary, entity_id)
        )
    if metadata is not None:
        conn.execute(
            "UPDATE entities SET metadata = ?, last_referenced = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(metadata), entity_id)
        )
    conn.commit()
    conn.close()


def add_entity_mention(entity_id: str, memory_id: str, context: str = None) -> str:
    conn = get_db()
    mid = new_id()
    conn.execute(
        """INSERT INTO entity_mentions (id, entity_id, memory_id, context)
           VALUES (?, ?, ?, ?)""",
        (mid, entity_id, memory_id, context)
    )
    conn.execute(
        "UPDATE entities SET last_referenced = CURRENT_TIMESTAMP WHERE id = ?",
        (entity_id,)
    )
    conn.commit()
    conn.close()
    return mid


def list_entities(entity_type: str = None) -> list[dict]:
    conn = get_db()
    if entity_type:
        rows = conn.execute(
            "SELECT * FROM entities WHERE entity_type = ? ORDER BY last_referenced DESC",
            (entity_type,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM entities ORDER BY last_referenced DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Open Loops ---

def add_open_loop(
    summary: str,
    priority: str = "medium",
    follow_up_question: str = None,
    source_memory_id: str = None,
    metadata: dict = None
) -> str:
    conn = get_db()
    lid = new_id()
    conn.execute(
        """INSERT INTO open_loops (id, summary, priority, follow_up_question, source_memory_id, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (lid, summary, priority, follow_up_question, source_memory_id, json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()
    return lid


def get_open_loops(limit: int = 10) -> list[dict]:
    """Get unresolved open loops, ordered by priority."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM open_loops 
           WHERE resolved_at IS NULL 
           ORDER BY 
             CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
             created_at DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_loop(loop_id: str):
    conn = get_db()
    conn.execute(
        "UPDATE open_loops SET resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (loop_id,)
    )
    conn.commit()
    conn.close()


# --- Conversations ---

def start_conversation(session_key: str = None, channel: str = None) -> str:
    conn = get_db()
    cid = new_id()
    conn.execute(
        """INSERT INTO conversations (id, session_key, channel)
           VALUES (?, ?, ?)""",
        (cid, session_key, channel)
    )
    conn.commit()
    conn.close()
    return cid


def end_conversation(conversation_id: str, summary: str = None):
    conn = get_db()
    conn.execute(
        "UPDATE conversations SET ended_at = CURRENT_TIMESTAMP, summary = ? WHERE id = ?",
        (summary, conversation_id)
    )
    conn.commit()
    conn.close()


def get_unanalyzed_conversations() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM conversations WHERE analyzed = 0 AND ended_at IS NOT NULL ORDER BY ended_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_analyzed(conversation_id: str):
    conn = get_db()
    conn.execute(
        "UPDATE conversations SET analyzed = 1 WHERE id = ?",
        (conversation_id,)
    )
    conn.commit()
    conn.close()


# --- Prepared Contexts ---

def save_prepared_context(
    conversation_id: str,
    context_summary: str,
    open_loops_json: list,
    selected_memories_json: list,
    topic_index: str,
    priority_topics: str,
    prepared_prompt: str,
    ttl_days: int = 7
) -> str:
    conn = get_db()
    pid = new_id()
    expires = datetime.utcnow() + timedelta(days=ttl_days)
    conn.execute(
        """INSERT INTO prepared_contexts 
           (id, conversation_id, context_summary, open_loops_json, selected_memories_json,
            topic_index, priority_topics, prepared_prompt, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, conversation_id, context_summary,
         json.dumps(open_loops_json), json.dumps(selected_memories_json),
         topic_index, priority_topics, prepared_prompt, expires.isoformat())
    )
    conn.commit()
    conn.close()
    return pid


def get_unused_context() -> Optional[dict]:
    """Get the most recent unused, non-expired prepared context."""
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM prepared_contexts 
           WHERE used_at IS NULL AND expires_at > ?
           ORDER BY created_at DESC LIMIT 1""",
        (datetime.utcnow().isoformat(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_context_used(context_id: str):
    conn = get_db()
    conn.execute(
        "UPDATE prepared_contexts SET used_at = CURRENT_TIMESTAMP WHERE id = ?",
        (context_id,)
    )
    conn.commit()
    conn.close()


# --- Stats ---

def stats() -> dict:
    conn = get_db()
    result = {}
    for table in ['memories', 'entities', 'open_loops', 'conversations', 'prepared_contexts']:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        result[table] = count
    
    active_loops = conn.execute(
        "SELECT COUNT(*) FROM open_loops WHERE resolved_at IS NULL"
    ).fetchone()[0]
    result['active_loops'] = active_loops
    
    active_memories = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE archived = 0"
    ).fetchone()[0]
    result['active_memories'] = active_memories
    
    conn.close()
    return result


if __name__ == "__main__":
    init_db()
    print("Schema created.")
    print(f"Stats: {stats()}")
