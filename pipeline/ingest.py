"""Ingest conversations into structured memories."""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.store import (
    add_memory, add_entity, get_entity_by_name, update_entity,
    add_entity_mention, add_open_loop, start_conversation, end_conversation
)
from vector.embeddings import add_memory as vec_add


def ingest_raw_memory(
    content: str,
    memory_type: str = "observation",
    source: str = None,
    importance: float = 0.5,
    metadata: dict = None
) -> str:
    """Add a single memory to both SQLite and vector store."""
    mid = add_memory(content, memory_type, source, importance, metadata)
    vec_add(mid, content, {
        "memory_type": memory_type,
        "importance": importance,
        "source": source or ""
    })
    return mid


def ingest_entity(
    name: str,
    entity_type: str = "person",
    summary: str = None,
    metadata: dict = None,
    memory_id: str = None,
    mention_context: str = None
) -> str:
    """Add or update an entity, optionally linking to a memory."""
    existing = get_entity_by_name(name)
    if existing:
        eid = existing["id"]
        if summary:
            update_entity(eid, summary=summary)
        if metadata:
            # Merge metadata
            old_meta = json.loads(existing["metadata"]) if existing["metadata"] else {}
            old_meta.update(metadata)
            update_entity(eid, metadata=old_meta)
    else:
        eid = add_entity(name, entity_type, summary, metadata)
    
    if memory_id:
        add_entity_mention(eid, memory_id, mention_context)
    
    return eid


def ingest_conversation(
    messages: list[dict],
    session_key: str = None,
    channel: str = None
) -> dict:
    """
    Process a conversation transcript into memories.
    
    messages: list of {"role": "user"|"assistant", "content": str}
    
    Returns dict with conversation_id and memory_ids created.
    """
    cid = start_conversation(session_key, channel)
    memory_ids = []
    
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            content = msg["content"]
            # Store substantive user messages as conversation memories
            if len(content) > 20:  # Skip very short messages
                mid = ingest_raw_memory(
                    content=content,
                    memory_type="conversation",
                    source=f"conversation:{cid}",
                    importance=0.5,
                    metadata={"role": "user", "channel": channel}
                )
                memory_ids.append(mid)
    
    return {
        "conversation_id": cid,
        "memory_ids": memory_ids
    }


if __name__ == "__main__":
    # Quick test
    mid = ingest_raw_memory(
        "Quinn's memory system uses SQLite + ChromaDB for structured and semantic storage",
        "decision",
        "self",
        0.8
    )
    print(f"Ingested memory: {mid}")
    
    eid = ingest_entity(
        "Josh",
        "person",
        "CEO of FiscalNote. Career-long friend of Gerry. Hard driver who pushes.",
        {"role": "CEO", "company": "FiscalNote"}
    )
    print(f"Entity: {eid}")
