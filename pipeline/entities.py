"""Entity extraction from text using pattern matching and LLM."""

import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.store import get_entity_by_name, list_entities

# Known entities bootstrap — these get loaded on first run
SEED_ENTITIES = [
    {
        "name": "Gerry Campbell",
        "type": "person",
        "summary": "Primary user. 30+ years shaping the internet. CTO at FiscalNote. Product visionary turned exec turned coder.",
        "metadata": {"email": "gcampbell@gmail.com", "role": "user", "company": "FiscalNote", "location": "Los Angeles"}
    },
    {
        "name": "Josh",
        "type": "person",
        "summary": "CEO of FiscalNote. Career-long friend of Gerry. Hard driver who pushes — Gerry sees this as a good thing.",
        "metadata": {"role": "CEO", "company": "FiscalNote"}
    },
    {
        "name": "Proteus",
        "type": "project",
        "summary": "Multi-tenant white-label platform for voice AI apps. Built with Next.js 14, Supabase, ElevenLabs, Claude Sonnet.",
        "metadata": {"tech": "Next.js 14, Supabase, pgvector, ElevenLabs, Claude Sonnet"}
    },
    {
        "name": "Vector",
        "type": "project",
        "summary": "Therapeutic AI voice chat client on Proteus. Has excellent memory system with pgvector embeddings and prepared contexts.",
        "metadata": {"platform": "Proteus", "type": "therapeutic AI"}
    },
    {
        "name": "Oblivn",
        "type": "project",
        "summary": "Anonymous P2P video chat using WebRTC. Two people, no data storage, end-to-end encrypted.",
        "metadata": {"tech": "WebRTC, Socket.io", "path": "~/Github/oblivnLive/"}
    },
    {
        "name": "FiscalNote",
        "type": "organization",
        "summary": "Gerry's company where he is CTO. Josh is CEO.",
        "metadata": {}
    },
    {
        "name": "Phase Four AI",
        "type": "organization",
        "summary": "Gerry's personal company. Email: gerry@phasefour.ai",
        "metadata": {"email": "gerry@phasefour.ai"}
    },
    {
        "name": "Serge",
        "type": "project",
        "summary": "Therapeutic AI voice chat client. 60k+ lines. Multi-day programs: AA 12-step, PTG, stress.",
        "metadata": {}
    },
    {
        "name": "Sara",
        "type": "person",
        "summary": "Connected to AI Initiative discussions with Gerry at FiscalNote.",
        "metadata": {"context": "AI Initiative meetings"}
    },
]


def extract_entity_names(text: str) -> list[str]:
    """Simple entity extraction via known names and capitalized words."""
    known = {e["name"].lower(): e["name"] for e in SEED_ENTITIES}
    # Also check first names
    for e in SEED_ENTITIES:
        first = e["name"].split()[0].lower()
        known[first] = e["name"]
    
    found = []
    text_lower = text.lower()
    
    for key, name in known.items():
        if key in text_lower and name not in found:
            found.append(name)
    
    return found


def seed_entities():
    """Load seed entities into the database if they don't exist."""
    from pipeline.ingest import ingest_entity
    
    created = 0
    for e in SEED_ENTITIES:
        existing = get_entity_by_name(e["name"])
        if not existing:
            ingest_entity(e["name"], e["type"], e["summary"], e["metadata"])
            created += 1
            print(f"  Seeded: {e['name']} ({e['type']})")
    
    if created:
        print(f"Seeded {created} entities")
    else:
        print("All seed entities already exist")


if __name__ == "__main__":
    seed_entities()
    
    # Test extraction
    test = "Gerry talked to Josh about the Proteus platform and Vector's memory system"
    found = extract_entity_names(test)
    print(f"Found entities: {found}")
