"""Entity extraction from text."""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import yaml

from db.store import get_entity_by_name, list_entities


def load_seed_entities() -> list[dict]:
    """Load seed entities from config file."""
    config_path = Path(__file__).parent.parent / "seed_entities.yaml"
    if not config_path.exists():
        return []
    
    with open(config_path) as f:
        data = yaml.safe_load(f)
    
    return data.get("entities", [])


def extract_entity_names(text: str, seed_entities: list[dict] = None) -> list[str]:
    """Simple entity extraction via known names."""
    if seed_entities is None:
        seed_entities = load_seed_entities()
    
    known = {}
    for e in seed_entities:
        name = e.get("name", "")
        known[name.lower()] = name
        # Also check first names
        first = name.split()[0].lower()
        if len(first) > 2:  # Skip very short first names
            known[first] = name
    
    # Also check entities already in the database
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
    """Load seed entities into the database if they don't exist."""
    from pipeline.ingest import ingest_entity
    
    entities = load_seed_entities()
    if not entities:
        print("No seed_entities.yaml found — skipping entity seeding")
        return
    
    created = 0
    for e in entities:
        existing = get_entity_by_name(e["name"])
        if not existing:
            ingest_entity(
                e["name"],
                e.get("type", "person"),
                e.get("summary"),
                e.get("metadata", {})
            )
            created += 1
            print(f"  Seeded: {e['name']} ({e.get('type', 'person')})")
    
    if created:
        print(f"Seeded {created} entities")
    else:
        print("All seed entities already exist")


if __name__ == "__main__":
    seed_entities()
    
    test = "Talked about the platform and the memory system"
    found = extract_entity_names(test)
    print(f"Found entities: {found}")
