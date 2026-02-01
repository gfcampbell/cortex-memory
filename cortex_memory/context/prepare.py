"""Prepare context for session injection."""

from cortex_memory.db.store import get_unused_context, mark_context_used, get_open_loops, recent_memories
from cortex_memory.vector.embeddings import search as vec_search


def get_prepared_context(mark_used=True, fallback=False):
    ctx = get_unused_context()
    if ctx:
        if mark_used:
            mark_context_used(ctx["id"])
        return {
            "prompt": ctx["prepared_prompt"],
            "source": "prepared",
            "context_id": ctx["id"]
        }
    if not fallback:
        raise RuntimeError("No prepared context available. Run 'cortex analyze' to generate one.")
    return build_fallback_context()


def build_fallback_context():
    parts = []
    loops = get_open_loops(5)
    if loops:
        parts.append("🔄 OPEN LOOPS - FOLLOW UP ON THESE FIRST:")
        for loop in loops:
            parts.append(f"• {loop['summary']} [{loop['priority']}]")
            if loop.get("follow_up_question"):
                parts.append(f"  Ask: \"{loop['follow_up_question']}\"")
        parts.append("")
    memories = recent_memories(20)
    if memories:
        parts.append("📝 RECENT MEMORIES:")
        for m in memories[:10]:
            parts.append(f"• [{m['memory_type']}] {m['content'][:200]}")
        parts.append("")
    prompt = "\n".join(parts) if parts else "(No context available yet)"
    return {"prompt": prompt, "source": "fallback"}


def search_context(query, n_results=5):
    return vec_search(query, n_results)
