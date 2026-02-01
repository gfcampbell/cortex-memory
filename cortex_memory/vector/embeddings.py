"""ChromaDB vector store for semantic memory retrieval."""

import chromadb
from pathlib import Path

from cortex_memory.config import get_config


def get_client():
    cfg = get_config()
    chroma_path = Path(cfg["vector"]["path"]).expanduser()
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_path))


def get_collection(client=None):
    if client is None:
        client = get_client()
    cfg = get_config()
    return client.get_or_create_collection(
        name=cfg["vector"]["collection"],
        metadata={"hnsw:space": "cosine"}
    )


def add_memory(memory_id, content, metadata=None):
    collection = get_collection()
    clean_meta = {}
    for k, v in (metadata or {}).items():
        if isinstance(v, (str, int, float, bool)):
            clean_meta[k] = v
        else:
            clean_meta[k] = str(v)
    collection.upsert(
        ids=[memory_id],
        documents=[content],
        metadatas=[clean_meta] if clean_meta else None
    )


def search(query, n_results=10, where=None, max_distance=None):
    collection = get_collection()
    if collection.count() == 0:
        return []
    kwargs = {
        "query_texts": [query],
        "n_results": min(n_results, collection.count())
    }
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)
    memories = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i] if results.get("distances") else None
        # Filter out low-relevance results
        if max_distance is not None and distance is not None and distance > max_distance:
            continue
        memories.append({
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "distance": distance,
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {}
        })
    return memories


def delete_memory(memory_id):
    collection = get_collection()
    collection.delete(ids=[memory_id])


def count():
    collection = get_collection()
    return collection.count()
