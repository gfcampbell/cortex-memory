"""Entity extraction and seeding."""

import yaml
from pathlib import Path

from cortex_memory.config import get_seed_entities_path
from cortex_memory.db.store import get_entity_by_name, list_entities


def load_seed_entities():
    path = get_seed_entities_path()
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("entities", [])


def extract_entity_names(text, seed_entities=None):
    if seed_entities is None:
        seed_entities = load_seed_entities()
    known = {}
    for e in seed_entities:
        name = e.get("name", "")
        known[name.lower()] = name
        first = name.split()[0].lower()
        if len(first) > 2:
            known[first] = name
    for e in list_entities():
        name = e["name"]
        known[name.lower()] = name
        first = name.split()[0].lower()
        if len(first) > 2:
            known[first] = name
    found = []
    text_lower = text.lower()
    for key, name in known.items():
        if key in text_lower and name not in found:
            found.append(name)
    return found


def seed_entities():
    from cortex_memory.pipeline.ingest import ingest_entity
    entities = load_seed_entities()
    if not entities:
        return 0
    created = 0
    for e in entities:
        existing = get_entity_by_name(e["name"])
        if not existing:
            ingest_entity(e["name"], e.get("type", "person"), e.get("summary"), e.get("metadata", {}))
            created += 1
    return created
