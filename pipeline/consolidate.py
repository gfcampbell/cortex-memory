"""Memory consolidation and decay."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from db.store import get_db, update_importance, archive_memory


def apply_decay(decay_rate: float = 0.95, min_importance: float = 0.1):
    """
    Apply time-based decay to memory importance scores.
    Memories that decay below min_importance get archived.
    
    Called periodically (e.g., daily via cron).
    """
    conn = get_db()
    
    # Get all active memories
    rows = conn.execute(
        "SELECT id, importance, decay_factor, created_at FROM memories WHERE archived = 0"
    ).fetchall()
    
    decayed = 0
    archived = 0
    
    for row in rows:
        mid = row["id"]
        importance = row["importance"]
        decay = row["decay_factor"] or decay_rate
        
        # Apply decay
        new_importance = importance * decay
        
        if new_importance < min_importance:
            archive_memory(mid)
            archived += 1
        else:
            update_importance(mid, new_importance)
            decayed += 1
    
    conn.close()
    
    print(f"Decay applied: {decayed} memories decayed, {archived} archived")
    return {"decayed": decayed, "archived": archived}


def get_consolidation_candidates(older_than_days: int = 7, limit: int = 50) -> list[dict]:
    """Find memories that are candidates for consolidation."""
    conn = get_db()
    cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()
    
    rows = conn.execute(
        """SELECT * FROM memories 
           WHERE archived = 0 AND created_at < ? 
           ORDER BY created_at ASC LIMIT ?""",
        (cutoff, limit)
    ).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    result = apply_decay()
    print(f"Result: {result}")
    
    candidates = get_consolidation_candidates()
    print(f"Consolidation candidates: {len(candidates)}")
