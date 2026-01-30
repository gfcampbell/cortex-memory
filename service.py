"""Quinn Memory System — Local HTTP API."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
from pathlib import Path
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn

from db.store import stats, get_open_loops, recent_memories, list_entities
from vector.embeddings import search as vec_search, count as vec_count
from pipeline.ingest import ingest_raw_memory, ingest_entity, ingest_conversation
from pipeline.consolidate import apply_decay
from context.prepare import get_prepared_context
from context.analyze import run_analysis

app = FastAPI(title="Quinn Memory System", version="0.1.0")


# --- Request Models ---

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
    messages: list[dict]
    session_key: Optional[str] = None
    channel: Optional[str] = None


class AnalyzeRequest(BaseModel):
    conversation_text: str
    conversation_id: Optional[str] = None


class OpenLoopCreate(BaseModel):
    summary: str
    priority: str = "medium"
    follow_up_question: Optional[str] = None


# --- Endpoints ---

@app.get("/")
def root():
    return {"service": "quinn-memory", "version": "0.1.0", "status": "running"}


@app.get("/stats")
def get_stats():
    s = stats()
    s["vector_count"] = vec_count()
    return s


@app.post("/memory")
def create_memory(mem: MemoryCreate):
    mid = ingest_raw_memory(
        content=mem.content,
        memory_type=mem.memory_type,
        source=mem.source,
        importance=mem.importance,
        metadata=mem.metadata
    )
    return {"id": mid, "status": "stored"}


@app.post("/entity")
def create_entity(ent: EntityCreate):
    eid = ingest_entity(
        name=ent.name,
        entity_type=ent.entity_type,
        summary=ent.summary,
        metadata=ent.metadata
    )
    return {"id": eid, "status": "stored"}


@app.post("/search")
def search(q: SearchQuery):
    results = vec_search(q.query, q.n_results)
    return {"results": results, "count": len(results)}


@app.get("/loops")
def loops(limit: int = 10):
    return {"loops": get_open_loops(limit)}


@app.post("/loops")
def create_loop(loop: OpenLoopCreate):
    from db.store import add_open_loop
    lid = add_open_loop(loop.summary, loop.priority, loop.follow_up_question)
    return {"id": lid, "status": "created"}


@app.post("/loops/{loop_id}/resolve")
def resolve(loop_id: str):
    from db.store import resolve_loop
    resolve_loop(loop_id)
    return {"status": "resolved"}


@app.get("/entities")
def entities(entity_type: Optional[str] = None):
    return {"entities": list_entities(entity_type)}


@app.get("/recent")
def recent(limit: int = 20):
    return {"memories": recent_memories(limit)}


@app.get("/context")
def context(peek: bool = False):
    """Get prepared context for session injection."""
    return get_prepared_context(mark_used=not peek)


@app.post("/ingest")
def ingest(conv: ConversationIngest):
    """Ingest a full conversation."""
    result = ingest_conversation(conv.messages, conv.session_key, conv.channel)
    return result


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Run post-session analysis."""
    result = run_analysis(req.conversation_text, req.conversation_id)
    if not result:
        raise HTTPException(status_code=500, detail="Analysis failed")
    return result


@app.post("/decay")
def decay(rate: float = 0.95, min_importance: float = 0.1):
    return apply_decay(rate, min_importance)


if __name__ == "__main__":
    from db.store import init_db
    from pipeline.entities import seed_entities
    
    # Ensure DB is ready
    init_db()
    seed_entities()
    
    uvicorn.run(app, host="127.0.0.1", port=8420)
