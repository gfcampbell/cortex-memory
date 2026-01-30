"""Cortex Memory — Local HTTP API."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from cortex_memory.config import get_config, load_env
from cortex_memory.db.store import stats, get_open_loops, recent_memories, list_entities, add_open_loop, resolve_loop, delete_memory, delete_memories_by_content, delete_entity, get_memory, delete_loop
from cortex_memory.vector.embeddings import search as vec_search, count as vec_count
from cortex_memory.pipeline.ingest import ingest_raw_memory, ingest_entity, ingest_conversation
from cortex_memory.pipeline.consolidate import apply_decay
from cortex_memory.context.prepare import get_prepared_context
from cortex_memory.context.analyze import run_analysis

load_env()
app = FastAPI(title="Cortex Memory", version="0.1.0")


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "observation"
    source: Optional[str] = None
    importance: float = 0.5
    metadata: Optional[dict] = None

class EntityCreate(BaseModel):
    name: str
    entity_type: str = "person"
    summary: Optional[str] = None
    metadata: Optional[dict] = None

class SearchQuery(BaseModel):
    query: str
    n_results: int = 5

class ConversationIngest(BaseModel):
    messages: list
    session_key: Optional[str] = None
    channel: Optional[str] = None

class AnalyzeRequest(BaseModel):
    conversation_text: str
    conversation_id: Optional[str] = None

class OpenLoopCreate(BaseModel):
    summary: str
    priority: str = "medium"
    follow_up_question: Optional[str] = None


@app.get("/")
def root():
    return {"service": "cortex-memory", "version": "0.1.0", "status": "running"}

@app.get("/stats")
def get_stats():
    s = stats()
    s["vector_count"] = vec_count()
    return s

@app.post("/memory")
def create_memory(mem: MemoryCreate):
    mid = ingest_raw_memory(mem.content, mem.memory_type, mem.source, mem.importance, mem.metadata)
    return {"id": mid, "status": "stored"}

@app.delete("/memory/{memory_id}")
def delete_memory_endpoint(memory_id: str):
    """Delete a memory by ID."""
    mem = get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
    delete_memory(memory_id)
    return {"id": memory_id, "status": "deleted"}

@app.delete("/memory/search/{content_prefix}")
def delete_memory_by_prefix(content_prefix: str):
    """Delete all memories where content starts with the given prefix."""
    count = delete_memories_by_content(content_prefix)
    return {"deleted": count, "status": "success", "prefix": content_prefix}

@app.post("/entity")
def create_entity(ent: EntityCreate):
    eid = ingest_entity(ent.name, ent.entity_type, ent.summary, ent.metadata)
    return {"id": eid, "status": "stored"}

@app.delete("/entity/{entity_id}")
def delete_entity_endpoint(entity_id: str):
    """Delete an entity by ID."""
    delete_entity(entity_id)
    return {"id": entity_id, "status": "deleted"}

@app.post("/search")
def search(q: SearchQuery):
    return {"results": vec_search(q.query, q.n_results), "count": len(vec_search(q.query, q.n_results))}

@app.get("/loops")
def loops(limit: int = 10):
    return {"loops": get_open_loops(limit)}

@app.post("/loops")
def create_loop(loop: OpenLoopCreate):
    lid = add_open_loop(loop.summary, loop.priority, loop.follow_up_question)
    return {"id": lid, "status": "created"}

@app.post("/loops/{loop_id}/resolve")
def resolve(loop_id: str):
    resolve_loop(loop_id)
    return {"status": "resolved"}

@app.delete("/loops/{loop_id}")
def delete_loop_endpoint(loop_id: str):
    """Delete an open loop."""
    delete_loop(loop_id)
    return {"id": loop_id, "status": "deleted"}

@app.get("/entities")
def entities(entity_type: Optional[str] = None):
    return {"entities": list_entities(entity_type)}

@app.get("/recent")
def recent(limit: int = 20):
    return {"memories": recent_memories(limit)}

@app.get("/context")
def context(peek: bool = False):
    return get_prepared_context(mark_used=not peek)

@app.post("/ingest")
def ingest(conv: ConversationIngest):
    return ingest_conversation(conv.messages, conv.session_key, conv.channel)

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    result = run_analysis(req.conversation_text, req.conversation_id)
    if not result:
        raise HTTPException(status_code=500, detail="Analysis failed")
    return result

@app.post("/decay")
def decay(rate: float = 0.95, min_importance: float = 0.1):
    return apply_decay(rate, min_importance)
