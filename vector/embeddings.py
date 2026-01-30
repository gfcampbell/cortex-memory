"""ChromaDB vector store for semantic memory retrieval."""

import chromadb
from pathlib import Path
from typing import Optional


CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma"


def get_client() -> chromadb.PersistentClient:
    """Get a persistent ChromaDB client."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(client: chromadb.PersistentClient = None):
    """Get or create the quinn_memories collection."""
    if client is None:
        client = get_client()
    return client.get_or_create_collection(
        name="quinn_memories",
        metadata={"hnsw:space": "cosine"}
    )


def add_memory(memory_id: str, content: str, metadata: dict = None):
    """Add a memory to the vector store."""
    collection = get_collection()
    meta = metadata or {}
    # ChromaDB metadata values must be str, int, float, or bool
    clean_meta = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)):
            clean_meta[k] = v
        else:
            clean_meta[k] = str(v)
    
    collection.upsert(
        ids=[memory_id],
        documents=[content],
        metadatas=[clean_meta] if clean_meta else None
    )


def search(query: str, n_results: int = 10, where: dict = None) -> list[dict]:
    """Semantic search across memories."""
    collection = get_collection()
    
    kwargs = {
        "query_texts": [query],
        "n_results": min(n_results, collection.count()) if collection.count() > 0 else 1
    }
    if where:
        kwargs["where"] = where
    
    if collection.count() == 0:
        return []
    
    results = collection.query(**kwargs)
    
    memories = []
    for i in range(len(results["ids"][0])):
        memories.append({
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "distance": results["distances"][0][i] if results.get("distances") else None,
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {}
        })
    
    return memories


def delete_memory(memory_id: str):
    """Remove a memory from the vector store."""
    collection = get_collection()
    collection.delete(ids=[memory_id])


def count() -> int:
    """How many memories are in the vector store."""
    collection = get_collection()
    return collection.count()


if __name__ == "__main__":
    client = get_client()
    coll = get_collection(client)
    print(f"ChromaDB initialized at {CHROMA_DIR}")
    print(f"Collection: {coll.name}, count: {coll.count()}")
