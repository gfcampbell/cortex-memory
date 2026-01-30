#!/usr/bin/env python3
"""Quinn Memory System CLI — the brain's command line."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.store import init_db, stats, get_open_loops, recent_memories, search_memories, list_entities
from vector.embeddings import search as vec_search, count as vec_count
from pipeline.ingest import ingest_raw_memory, ingest_entity, ingest_conversation
from pipeline.entities import seed_entities, extract_entity_names
from pipeline.consolidate import apply_decay
from context.prepare import get_prepared_context, search_context
from context.analyze import run_analysis


def cmd_init(args):
    """Initialize the database and seed entities."""
    init_db()
    seed_entities()
    print(f"\n✅ Quinn Memory System initialized")
    print(f"   Database: {os.path.abspath('data/quinn_memory.db')}")
    print(f"   Vector:   {os.path.abspath('data/chroma')}")
    cmd_stats(args)


def cmd_stats(args):
    """Show memory system statistics."""
    s = stats()
    vc = vec_count()
    print(f"\n🧠 Quinn Memory Stats")
    print(f"   Memories:     {s['active_memories']} active ({s['memories']} total)")
    print(f"   Entities:     {s['entities']}")
    print(f"   Open Loops:   {s['active_loops']}")
    print(f"   Conversations:{s['conversations']}")
    print(f"   Prepared Ctx: {s['prepared_contexts']}")
    print(f"   Vector Store: {vc} embeddings")


def cmd_remember(args):
    """Store a new memory."""
    mid = ingest_raw_memory(
        content=args.content,
        memory_type=args.type,
        source=args.source or "cli",
        importance=args.importance
    )
    print(f"✅ Stored memory: {mid}")
    print(f"   Type: {args.type} | Importance: {args.importance}")
    
    # Auto-extract entities
    entities = extract_entity_names(args.content)
    if entities:
        print(f"   Entities found: {', '.join(entities)}")


def cmd_search(args):
    """Semantic search across memories."""
    results = vec_search(args.query, n_results=args.limit)
    if not results:
        print("No memories found.")
        return
    
    print(f"\n🔍 Search: \"{args.query}\" ({len(results)} results)")
    for i, r in enumerate(results, 1):
        dist = f" (distance: {r['distance']:.3f})" if r.get('distance') is not None else ""
        mtype = r.get('metadata', {}).get('memory_type', '?')
        print(f"  {i}. [{mtype}]{dist}")
        print(f"     {r['content'][:150]}")
        print()


def cmd_loops(args):
    """Show open loops."""
    loops = get_open_loops(args.limit)
    if not loops:
        print("No open loops.")
        return
    
    print(f"\n🔄 Open Loops ({len(loops)})")
    for loop in loops:
        print(f"  [{loop['priority'].upper()}] {loop['summary']}")
        if loop.get('follow_up_question'):
            print(f"    → {loop['follow_up_question']}")
        print()


def cmd_entities(args):
    """List known entities."""
    entities = list_entities(args.type)
    if not entities:
        print("No entities found.")
        return
    
    print(f"\n👤 Entities ({len(entities)})")
    for e in entities:
        print(f"  [{e['entity_type']}] {e['name']}")
        if e.get('summary'):
            print(f"    {e['summary'][:120]}")
        print()


def cmd_context(args):
    """Get prepared context for session injection."""
    ctx = get_prepared_context(mark_used=not args.peek)
    print(f"\n📋 Context (source: {ctx['source']})")
    print(f"{'=' * 60}")
    print(ctx['prompt'])
    print(f"{'=' * 60}")


def cmd_analyze(args):
    """Run post-session analysis on conversation text."""
    if args.file:
        with open(args.file) as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        print("Provide --text or --file")
        return
    
    print("🔄 Running analysis...")
    result = run_analysis(text, args.conversation_id)
    if result:
        print(f"\n✅ Analysis complete")
        print(f"   Context ID: {result['context_id']}")
        print(f"\n--- PREPARED PROMPT ---")
        print(result['prepared_prompt'])
    else:
        print("❌ Analysis failed")


def cmd_decay(args):
    """Apply decay to memory importance scores."""
    result = apply_decay(args.rate, args.min_importance)
    print(f"✅ Decay applied: {result['decayed']} decayed, {result['archived']} archived")


def cmd_recent(args):
    """Show recent memories."""
    memories = recent_memories(args.limit)
    if not memories:
        print("No memories yet.")
        return
    
    print(f"\n📝 Recent Memories ({len(memories)})")
    for m in memories:
        print(f"  [{m['memory_type']}] (imp: {m['importance']:.2f}) {m['created_at']}")
        print(f"    {m['content'][:150]}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Quinn Memory System")
    sub = parser.add_subparsers(dest="command")
    
    # init
    sub.add_parser("init", help="Initialize database and seed entities")
    
    # stats
    sub.add_parser("stats", help="Show memory statistics")
    
    # remember
    p = sub.add_parser("remember", help="Store a new memory")
    p.add_argument("content", help="Memory content")
    p.add_argument("--type", "-t", default="observation",
                   choices=["conversation", "observation", "decision", "personality", "action_item", "fact"])
    p.add_argument("--source", "-s", default=None)
    p.add_argument("--importance", "-i", type=float, default=0.5)
    
    # search
    p = sub.add_parser("search", help="Semantic search memories")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", "-n", type=int, default=5)
    
    # loops
    p = sub.add_parser("loops", help="Show open loops")
    p.add_argument("--limit", "-n", type=int, default=10)
    
    # entities
    p = sub.add_parser("entities", help="List entities")
    p.add_argument("--type", "-t", default=None)
    
    # context
    p = sub.add_parser("context", help="Get prepared context")
    p.add_argument("--peek", action="store_true", help="Don't mark as used")
    
    # analyze
    p = sub.add_parser("analyze", help="Run post-session analysis")
    p.add_argument("--text", help="Conversation text")
    p.add_argument("--file", "-f", help="File with conversation text")
    p.add_argument("--conversation-id", help="Conversation ID to link")
    
    # decay
    p = sub.add_parser("decay", help="Apply decay to memories")
    p.add_argument("--rate", type=float, default=0.95)
    p.add_argument("--min-importance", type=float, default=0.1)
    
    # recent
    p = sub.add_parser("recent", help="Show recent memories")
    p.add_argument("--limit", "-n", type=int, default=10)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    commands = {
        "init": cmd_init,
        "stats": cmd_stats,
        "remember": cmd_remember,
        "search": cmd_search,
        "loops": cmd_loops,
        "entities": cmd_entities,
        "context": cmd_context,
        "analyze": cmd_analyze,
        "decay": cmd_decay,
        "recent": cmd_recent,
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()
