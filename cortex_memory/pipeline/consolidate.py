"""Memory consolidation and decay."""

from datetime import datetime, timedelta
from cortex_memory.db.store import get_db, update_importance, archive_memory


def apply_decay(decay_rate=0.95, min_importance=0.1):
    conn = get_db()
    rows = conn.execute("SELECT id, importance, decay_factor FROM memories WHERE archived = 0").fetchall()
    decayed = 0
    archived = 0
    for row in rows:
        new_importance = row["importance"] * (row["decay_factor"] or decay_rate)
        if new_importance < min_importance:
            archive_memory(row["id"])
            archived += 1
        else:
            update_importance(row["id"], new_importance)
            decayed += 1
    conn.close()
    return {"decayed": decayed, "archived": archived}


def get_consolidation_candidates(older_than_days=7, limit=50):
    conn = get_db()
    cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()
    rows = conn.execute(
        "SELECT * FROM memories WHERE archived = 0 AND created_at < ? ORDER BY created_at ASC LIMIT ?",
        (cutoff, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
