"""Prepare context for session injection."""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.store import get_unused_context, mark_context_used, get_open_loops, recent_memories
from vector.embeddings import search as vec_search


def get_prepared_context(mark_used: bool = True) -> dict:
    """
    Get the prepared context for this session.
    
    1. Check for unused prepared_context (from post-session analysis)
    2. If found, return it (and optionally mark as used)
    3. If not, fall back to formula-based retrieval
    
    Returns dict with 'prompt' (injection-ready text) and 'source' ('prepared' or 'fallback')
    """
    # Try prepared context first
    ctx = get_unused_context()
    if ctx:
        if mark_used:
            mark_context_used(ctx["id"])
        return {
            "prompt": ctx["prepared_prompt"],
            "source": "prepared",
            "context_id": ctx["id"]
        }
    
    # Fallback: build context from current state
    return build_fallback_context()


def build_fallback_context() -> dict:
    """Build context from open loops + recent memories + vector search."""
    parts = []
    
    # Open loops
    loops = get_open_loops(5)
    if loops:
        parts.append("🔄 OPEN LOOPS - FOLLOW UP ON THESE FIRST:")
        for loop in loops:
            parts.append(f"• {loop['summary']} [{loop['priority']}]")
            if loop.get("follow_up_question"):
                parts.append(f"  Ask: \"{loop['follow_up_question']}\"")
        parts.append("")
    
    # Recent memories
    memories = recent_memories(20)
    if memories:
        parts.append("📝 RECENT MEMORIES:")
        for m in memories[:10]:
            parts.append(f"• [{m['memory_type']}] {m['content'][:200]}")
        parts.append("")
    
    prompt = "\n".join(parts) if parts else "(No context available yet)"
    
    return {
        "prompt": prompt,
        "source": "fallback"
    }


def search_context(query: str, n_results: int = 5) -> list[dict]:
    """Semantic search for relevant context."""
    return vec_search(query, n_results)


if __name__ == "__main__":
    ctx = get_prepared_context(mark_used=False)
    print(f"Source: {ctx['source']}")
    print(f"Prompt:\n{ctx['prompt']}")
