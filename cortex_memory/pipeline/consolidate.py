"""Memory consolidation and decay."""

import json
from datetime import datetime, timedelta
from cortex_memory.db.store import get_db, update_importance, archive_memory


def apply_decay(decay_rate=0.95, min_importance=0.1, dry_run=False):
    """Apply decay to memory importance scores.
    
    Args:
        decay_rate: Multiplier for importance (default 0.95)
        min_importance: Archive threshold (default 0.1)
        dry_run: If True, return what would happen without modifying anything
    
    Memories with metadata["protected"]=true are exempt from decay.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT id, content, importance, decay_factor, metadata FROM memories WHERE archived = 0"
    ).fetchall()
    
    decayed = []
    will_archive = []
    protected = []
    
    for row in rows:
        # Check if protected
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        if meta.get("protected"):
            protected.append({
                "id": row["id"],
                "content": row["content"][:100],
                "importance": row["importance"]
            })
            continue
        
        effective_rate = row["decay_factor"] or decay_rate
        new_importance = row["importance"] * effective_rate
        
        if new_importance < min_importance:
            will_archive.append({
                "id": row["id"],
                "content": row["content"][:100],
                "old_importance": row["importance"],
                "new_importance": new_importance
            })
            if not dry_run:
                archive_memory(row["id"])
        else:
            decayed.append({
                "id": row["id"],
                "content": row["content"][:100],
                "old_importance": row["importance"],
                "new_importance": new_importance
            })
            if not dry_run:
                update_importance(row["id"], new_importance)
    
    conn.close()
    
    result = {
        "dry_run": dry_run,
        "decayed_count": len(decayed),
        "archived_count": len(will_archive),
        "protected_count": len(protected)
    }
    
    if dry_run:
        result["would_decay"] = decayed
        result["would_archive"] = will_archive
        result["protected"] = protected
    
    return result


def get_consolidation_candidates(older_than_days=7, limit=50):
    conn = get_db()
    cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()
    rows = conn.execute(
        "SELECT * FROM memories WHERE archived = 0 AND created_at < ? ORDER BY created_at ASC LIMIT ?",
        (cutoff, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
