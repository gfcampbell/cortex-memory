"""SQLite store for Cortex Memory."""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from cortex_memory.config import get_config

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db_path() -> Path:
    cfg = get_config()
    return Path(cfg["database"]["path"]).expanduser()


def get_db() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()


def new_id() -> str:
    return str(uuid.uuid4())


# --- Memories ---

def add_memory(content, memory_type="observation", source=None, importance=0.5, metadata=None):
    conn = get_db()
    mid = new_id()
    conn.execute(
        "INSERT INTO memories (id, content, memory_type, source, importance, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (mid, content, memory_type, source, importance, json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()
    return mid


def get_memory(memory_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_memories(memory_type=None, min_importance=None, limit=50, include_archived=False):
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


def recent_memories(limit=200):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM memories WHERE archived = 0 ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_importance(memory_id, importance):
    conn = get_db()
    conn.execute("UPDATE memories SET importance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (importance, memory_id))
    conn.commit()
    conn.close()


def archive_memory(memory_id, consolidated_into=None):
    conn = get_db()
    conn.execute("UPDATE memories SET archived = 1, consolidated_into = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (consolidated_into, memory_id))
    conn.commit()
    conn.close()


def set_memory_protected(memory_id, protected=True):
    """Set or remove decay protection on a memory."""
    conn = get_db()
    row = conn.execute("SELECT metadata FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if row:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        if protected:
            meta["protected"] = True
        else:
            meta.pop("protected", None)
        conn.execute("UPDATE memories SET metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                     (json.dumps(meta), memory_id))
        conn.commit()
    conn.close()


def delete_memory(memory_id):
    """Permanently delete a memory by ID, including entity mentions."""
    conn = get_db()
    conn.execute("DELETE FROM entity_mentions WHERE memory_id = ?", (memory_id,))
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()


def delete_memories_by_content(content_prefix):
    """Delete memories where content starts with a prefix. Useful for cleanup."""
    conn = get_db()
    # Clean up entity mentions first
    mem_ids = [r[0] for r in conn.execute("SELECT id FROM memories WHERE content LIKE ?", (f"{content_prefix}%",)).fetchall()]
    for mid in mem_ids:
        conn.execute("DELETE FROM entity_mentions WHERE memory_id = ?", (mid,))
    cursor = conn.execute("DELETE FROM memories WHERE content LIKE ?", (f"{content_prefix}%",))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count


# --- Entities ---

def add_entity(name, entity_type="person", summary=None, metadata=None):
    conn = get_db()
    eid = new_id()
    conn.execute(
        "INSERT INTO entities (id, name, entity_type, summary, metadata) VALUES (?, ?, ?, ?, ?)",
        (eid, name, entity_type, summary, json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()
    return eid


def get_entity_by_name(name):
    conn = get_db()
    row = conn.execute("SELECT * FROM entities WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_entity(entity_id, summary=None, metadata=None):
    conn = get_db()
    if summary is not None:
        conn.execute("UPDATE entities SET summary = ?, last_referenced = CURRENT_TIMESTAMP WHERE id = ?", (summary, entity_id))
    if metadata is not None:
        conn.execute("UPDATE entities SET metadata = ?, last_referenced = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(metadata), entity_id))
    if summary is None and metadata is None:
        # Just touch the timestamp
        conn.execute("UPDATE entities SET last_referenced = CURRENT_TIMESTAMP WHERE id = ?", (entity_id,))
    conn.commit()
    conn.close()


def add_entity_mention(entity_id, memory_id, context=None):
    conn = get_db()
    mid = new_id()
    conn.execute("INSERT INTO entity_mentions (id, entity_id, memory_id, context) VALUES (?, ?, ?, ?)", (mid, entity_id, memory_id, context))
    conn.execute("UPDATE entities SET last_referenced = CURRENT_TIMESTAMP WHERE id = ?", (entity_id,))
    conn.commit()
    conn.close()
    return mid


def list_entities(entity_type=None):
    conn = get_db()
    if entity_type:
        rows = conn.execute("SELECT * FROM entities WHERE entity_type = ? ORDER BY last_referenced DESC", (entity_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM entities ORDER BY last_referenced DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_entity(entity_id):
    """Permanently delete an entity by ID."""
    conn = get_db()
    conn.execute("DELETE FROM entity_mentions WHERE entity_id = ?", (entity_id,))
    conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
    conn.commit()
    conn.close()


# --- Open Loops ---

def add_open_loop(summary, priority="medium", follow_up_question=None, source_memory_id=None, metadata=None):
    conn = get_db()
    lid = new_id()
    conn.execute(
        "INSERT INTO open_loops (id, summary, priority, follow_up_question, source_memory_id, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (lid, summary, priority, follow_up_question, source_memory_id, json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()
    return lid


def get_open_loops(limit=10):
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM open_loops WHERE resolved_at IS NULL 
           ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END, created_at DESC
           LIMIT ?""", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_loop(loop_id):
    conn = get_db()
    conn.execute("UPDATE open_loops SET resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (loop_id,))
    conn.commit()
    conn.close()


def delete_loop(loop_id):
    """Permanently delete an open loop."""
    conn = get_db()
    conn.execute("DELETE FROM open_loops WHERE id = ?", (loop_id,))
    conn.commit()
    conn.close()


# --- Conversations ---

def start_conversation(session_key=None, channel=None):
    conn = get_db()
    cid = new_id()
    conn.execute("INSERT INTO conversations (id, session_key, channel) VALUES (?, ?, ?)", (cid, session_key, channel))
    conn.commit()
    conn.close()
    return cid


def end_conversation(conversation_id, summary=None):
    conn = get_db()
    conn.execute("UPDATE conversations SET ended_at = CURRENT_TIMESTAMP, summary = ? WHERE id = ?", (summary, conversation_id))
    conn.commit()
    conn.close()


def get_unanalyzed_conversations():
    conn = get_db()
    rows = conn.execute("SELECT * FROM conversations WHERE analyzed = 0 AND ended_at IS NOT NULL ORDER BY ended_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_analyzed(conversation_id):
    conn = get_db()
    conn.execute("UPDATE conversations SET analyzed = 1 WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()


# --- Prepared Contexts ---

def save_prepared_context(conversation_id, context_summary, open_loops_json, selected_memories_json, topic_index, priority_topics, prepared_prompt, ttl_days=7):
    conn = get_db()
    pid = new_id()
    expires = datetime.utcnow() + timedelta(days=ttl_days)
    conn.execute(
        """INSERT INTO prepared_contexts (id, conversation_id, context_summary, open_loops_json, selected_memories_json, topic_index, priority_topics, prepared_prompt, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, conversation_id, context_summary, json.dumps(open_loops_json), json.dumps(selected_memories_json), topic_index, priority_topics, prepared_prompt, expires.isoformat())
    )
    conn.commit()
    conn.close()
    return pid


def get_unused_context():
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM prepared_contexts WHERE used_at IS NULL AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
        (datetime.utcnow().isoformat(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_context_used(context_id):
    conn = get_db()
    conn.execute("UPDATE prepared_contexts SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (context_id,))
    conn.commit()
    conn.close()


# --- Stats ---

def stats():
    conn = get_db()
    result = {}
    for table in ['memories', 'entities', 'open_loops', 'conversations', 'prepared_contexts']:
        result[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    result['active_loops'] = conn.execute("SELECT COUNT(*) FROM open_loops WHERE resolved_at IS NULL").fetchone()[0]
    result['active_memories'] = conn.execute("SELECT COUNT(*) FROM memories WHERE archived = 0").fetchone()[0]
    result['archived_memories'] = result['memories'] - result['active_memories']
    # Last analyze time
    row = conn.execute("SELECT MAX(created_at) FROM prepared_contexts").fetchone()
    result['last_analyze'] = row[0] if row and row[0] else None
    # Last decay (approximated by last archived memory)
    row = conn.execute("SELECT MAX(updated_at) FROM memories WHERE archived = 1").fetchone()
    result['last_decay'] = row[0] if row and row[0] else None
    # Unused prepared contexts
    result['unused_contexts'] = conn.execute(
        "SELECT COUNT(*) FROM prepared_contexts WHERE used_at IS NULL AND expires_at > datetime('now')"
    ).fetchone()[0]
    # Memory type breakdown
    rows = conn.execute(
        "SELECT memory_type, COUNT(*) FROM memories WHERE archived = 0 GROUP BY memory_type ORDER BY COUNT(*) DESC"
    ).fetchall()
    result['memory_types'] = {row[0]: row[1] for row in rows}
    conn.close()
    return result
