"""Ingest conversations into structured memories."""

import json

from cortex_memory.db.store import (
    add_memory, add_entity, get_entity_by_name, update_entity,
    add_entity_mention, start_conversation
)
from cortex_memory.vector.embeddings import add_memory as vec_add


def ingest_raw_memory(content, memory_type="observation", source=None, importance=0.5, metadata=None):
    mid = add_memory(content, memory_type, source, importance, metadata)
    vec_add(mid, content, {
        "memory_type": memory_type,
        "importance": importance,
        "source": source or ""
    })
    return mid


def ingest_entity(name, entity_type="person", summary=None, metadata=None, memory_id=None, mention_context=None):
    existing = get_entity_by_name(name)
    if existing:
        eid = existing["id"]
        if summary:
            update_entity(eid, summary=summary)
        if metadata:
            old_meta = json.loads(existing["metadata"]) if existing["metadata"] else {}
            old_meta.update(metadata)
            update_entity(eid, metadata=old_meta)
    else:
        eid = add_entity(name, entity_type, summary, metadata)
    if memory_id:
        add_entity_mention(eid, memory_id, mention_context)
    return eid


def ingest_conversation(messages, session_key=None, channel=None):
    cid = start_conversation(session_key, channel)
    memory_ids = []
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content") and len(msg["content"]) > 20:
            mid = ingest_raw_memory(
                content=msg["content"],
                memory_type="conversation",
                source=f"conversation:{cid}",
                importance=0.5,
                metadata={"role": "user", "channel": channel}
            )
            memory_ids.append(mid)
    return {"conversation_id": cid, "memory_ids": memory_ids}
