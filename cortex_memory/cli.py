#!/usr/bin/env python3
"""Cortex Memory CLI — your AI assistant's brain."""

import argparse
import json
import sys

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()


def cmd_init(args):
    """Interactive setup wizard."""
    from cortex_memory.config import (
        is_initialized, save_config, save_env, DEFAULT_CONFIG,
        CORTEX_HOME, get_seed_entities_path
    )

    console.print(Panel.fit(
        "[bold green]🧠 Cortex Memory Setup[/]\n\n"
        "A local-first memory system for AI assistants.\n"
        "Everything stays on your machine.",
        border_style="green"
    ))

    if is_initialized():
        if not Confirm.ask("\n[yellow]Cortex is already initialized. Reinitialize?[/]", default=False):
            console.print("Aborted.")
            return

    config = DEFAULT_CONFIG.copy()

    # Data directory
    console.print(f"\n[dim]Data directory: {CORTEX_HOME}[/]")

    # Analysis provider
    console.print("\n[bold]Analysis Provider[/]")
    console.print("Post-session analysis uses a cheap/fast LLM to curate your memories.")
    console.print("  1. [cyan]Anthropic[/] (Claude Haiku — recommended)")
    console.print("  2. [cyan]OpenAI[/] (GPT-4o-mini)")

    choice = Prompt.ask("Choose provider", choices=["1", "2"], default="1")
    if choice == "1":
        config["analysis"]["provider"] = "anthropic"
        config["analysis"]["model"] = "claude-haiku-4-5"
        key_name = "ANTHROPIC_API_KEY"
        key_hint = "sk-ant-..."
    else:
        config["analysis"]["provider"] = "openai"
        config["analysis"]["model"] = "gpt-4o-mini"
        key_name = "OPENAI_API_KEY"
        key_hint = "sk-..."

    # API key
    console.print(f"\n[bold]API Key[/]")
    import os
    existing_key = os.environ.get(key_name, "")
    if existing_key:
        console.print(f"[dim]Found {key_name} in environment[/]")
        if not Confirm.ask("Use existing key?", default=True):
            existing_key = ""

    if not existing_key:
        key = Prompt.ask(f"Enter your {key_name}", password=True)
        if key:
            save_env(key_name, key)
            console.print(f"[green]✓[/] Key saved to {CORTEX_HOME}/.env")
        else:
            console.print("[yellow]⚠ No key provided — analysis will fail until you set one[/]")

    # Service port
    port = Prompt.ask("Service port", default="8420")
    config["service"]["port"] = int(port)

    # Save config
    save_config(config)
    console.print(f"\n[green]✓[/] Config saved to {CORTEX_HOME}/config.yaml")

    # Initialize database
    from cortex_memory.db.store import init_db
    init_db()
    console.print("[green]✓[/] Database initialized")

    # Test vector store
    from cortex_memory.vector.embeddings import count
    console.print(f"[green]✓[/] Vector store ready ({count()} embeddings)")

    # Seed entities
    seed_path = get_seed_entities_path()
    if not seed_path.exists():
        if Confirm.ask("\nWould you like to create a seed entities file?", default=False):
            _create_seed_entities(seed_path)
    else:
        from cortex_memory.pipeline.entities import seed_entities
        n = seed_entities()
        if n:
            console.print(f"[green]✓[/] Seeded {n} entities")

    # Done
    console.print(Panel.fit(
        "[bold green]✅ Cortex Memory is ready![/]\n\n"
        f"  Home:    {CORTEX_HOME}\n"
        f"  Config:  {CORTEX_HOME}/config.yaml\n"
        f"  Service: cortex start\n"
        f"  Help:    cortex --help",
        border_style="green"
    ))


def _create_seed_entities(path):
    """Interactive seed entity creation."""
    import yaml

    entities = []
    console.print("\n[dim]Add people, projects, or organizations your AI knows about.[/]")
    console.print("[dim]Press Enter with empty name to finish.[/]\n")

    while True:
        name = Prompt.ask("Entity name (or Enter to finish)", default="")
        if not name:
            break
        etype = Prompt.ask("Type", choices=["person", "project", "organization", "tool", "place", "concept"], default="person")
        summary = Prompt.ask("Brief summary", default="")
        entity = {"name": name, "type": etype}
        if summary:
            entity["summary"] = summary
        entities.append(entity)
        console.print(f"  [green]✓[/] Added {name} ({etype})")

    if entities:
        path.write_text(yaml.dump({"entities": entities}, default_flow_style=False))
        console.print(f"\n[green]✓[/] Saved {len(entities)} entities to {path}")

        from cortex_memory.pipeline.entities import seed_entities
        seed_entities()


def cmd_start(args):
    """Start the HTTP service."""
    from cortex_memory.config import get_config, is_initialized

    if not is_initialized():
        console.print("[red]Cortex not initialized. Run: cortex init[/]")
        return

    cfg = get_config()
    host = cfg["service"]["host"]
    port = cfg["service"]["port"]

    console.print(f"[green]🧠 Cortex Memory[/] starting on http://{host}:{port}")

    from cortex_memory.db.store import init_db
    from cortex_memory.pipeline.entities import seed_entities
    init_db()
    seed_entities()

    import uvicorn
    uvicorn.run(
        "cortex_memory.service:app",
        host=host, port=port,
        log_level="info"
    )


def cmd_stats(args):
    """Show memory system statistics."""
    from cortex_memory.db.store import stats
    from cortex_memory.vector.embeddings import count as vec_count

    s = stats()
    vc = vec_count()

    table = Table(title="🧠 Cortex Memory", border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Memories (active)", str(s['active_memories']))
    table.add_row("Memories (total)", str(s['memories']))
    table.add_row("Entities", str(s['entities']))
    table.add_row("Open Loops", str(s['active_loops']))
    table.add_row("Conversations", str(s['conversations']))
    table.add_row("Prepared Contexts", str(s['prepared_contexts']))
    table.add_row("Vector Embeddings", str(vc))
    console.print(table)


def cmd_remember(args):
    """Store a new memory."""
    from cortex_memory.pipeline.ingest import ingest_raw_memory
    from cortex_memory.pipeline.entities import extract_entity_names

    mid = ingest_raw_memory(args.content, args.type, args.source or "cli", args.importance)
    console.print(f"[green]✓[/] Stored: {mid[:8]}... ({args.type}, importance: {args.importance})")

    entities = extract_entity_names(args.content)
    if entities:
        console.print(f"  [dim]Entities detected: {', '.join(entities)}[/]")


def cmd_search(args):
    """Semantic search across memories."""
    from cortex_memory.vector.embeddings import search as vec_search

    results = vec_search(args.query, n_results=args.limit)
    if not results:
        console.print("[dim]No memories found.[/]")
        return

    console.print(f"\n[bold]🔍 \"{args.query}\"[/] — {len(results)} results\n")
    for i, r in enumerate(results, 1):
        dist = f" ({r['distance']:.3f})" if r.get('distance') is not None else ""
        mtype = r.get('metadata', {}).get('memory_type', '?')
        console.print(f"  [cyan]{i}.[/] [{mtype}]{dist}")
        console.print(f"     {r['content'][:150]}")
        console.print()


def cmd_loops(args):
    """Show open loops."""
    from cortex_memory.db.store import get_open_loops

    loops = get_open_loops(args.limit)
    if not loops:
        console.print("[dim]No open loops.[/]")
        return

    console.print(f"\n[bold]🔄 Open Loops[/] ({len(loops)})\n")
    for loop in loops:
        color = {"high": "red", "medium": "yellow", "low": "dim"}.get(loop['priority'], "white")
        console.print(f"  [{color}][{loop['priority'].upper()}][/{color}] {loop['summary']}")
        if loop.get('follow_up_question'):
            console.print(f"    [dim]→ {loop['follow_up_question']}[/]")
        console.print()


def cmd_entities(args):
    """List known entities."""
    from cortex_memory.db.store import list_entities

    entities = list_entities(args.type)
    if not entities:
        console.print("[dim]No entities found.[/]")
        return

    console.print(f"\n[bold]👤 Entities[/] ({len(entities)})\n")
    for e in entities:
        console.print(f"  [cyan][{e['entity_type']}][/] [bold]{e['name']}[/]")
        if e.get('summary'):
            console.print(f"    [dim]{e['summary'][:120]}[/]")
        console.print()


def cmd_context(args):
    """Get prepared context for session injection."""
    from cortex_memory.context.prepare import get_prepared_context

    ctx = get_prepared_context(mark_used=not args.peek)
    console.print(Panel(
        ctx['prompt'],
        title=f"📋 Context (source: {ctx['source']})",
        border_style="cyan"
    ))


def cmd_analyze(args):
    """Run post-session analysis."""
    if args.file:
        with open(args.file) as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        console.print("[red]Provide --text or --file[/]")
        return

    console.print("[dim]🔄 Running analysis...[/]")
    from cortex_memory.context.analyze import run_analysis
    result = run_analysis(text, args.conversation_id)

    if not result or result.get("error"):
        console.print(f"[red]✗ Analysis failed: {result.get('error', 'unknown')}[/]")
        return

    console.print(f"[green]✓[/] Context ID: {result['context_id'][:8]}...")
    console.print(Panel(result['prepared_prompt'], title="Prepared Context", border_style="green"))


def cmd_decay(args):
    """Apply decay to memory importance."""
    from cortex_memory.pipeline.consolidate import apply_decay
    result = apply_decay(args.rate, args.min_importance)
    console.print(f"[green]✓[/] {result['decayed']} decayed, {result['archived']} archived")


def cmd_recent(args):
    """Show recent memories."""
    from cortex_memory.db.store import recent_memories

    memories = recent_memories(args.limit)
    if not memories:
        console.print("[dim]No memories yet.[/]")
        return

    console.print(f"\n[bold]📝 Recent Memories[/] ({len(memories)})\n")
    for m in memories:
        imp = f"[{'green' if m['importance'] > 0.7 else 'yellow' if m['importance'] > 0.4 else 'dim'}]{m['importance']:.2f}[/]"
        console.print(f"  [{m['memory_type']}] {imp} {m['content'][:120]}")


def main():
    parser = argparse.ArgumentParser(
        description="🧠 Cortex Memory — A local-first memory system for AI assistants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cortex init                              Interactive setup
  cortex start                             Start the HTTP service
  cortex remember "User likes dark mode"   Store a memory
  cortex search "preferences"              Semantic search
  cortex context                           Get prepared context
  cortex loops                             Show open loops
  cortex stats                             System statistics

Documentation: https://github.com/gfcampbell/cortex-memory
"""
    )
    parser.add_argument("--version", action="version", version="cortex-memory 0.1.0")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Interactive setup wizard")
    sub.add_parser("start", help="Start the HTTP service")
    sub.add_parser("stats", help="Show memory statistics")

    p = sub.add_parser("remember", help="Store a new memory")
    p.add_argument("content", help="Memory content")
    p.add_argument("--type", "-t", default="observation",
                   choices=["conversation", "observation", "decision", "personality", "action_item", "fact"])
    p.add_argument("--source", "-s", default=None)
    p.add_argument("--importance", "-i", type=float, default=0.5)

    p = sub.add_parser("search", help="Semantic search")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", "-n", type=int, default=5)

    p = sub.add_parser("loops", help="Show open loops")
    p.add_argument("--limit", "-n", type=int, default=10)

    p = sub.add_parser("entities", help="List entities")
    p.add_argument("--type", "-t", default=None)

    p = sub.add_parser("context", help="Get prepared context")
    p.add_argument("--peek", action="store_true", help="Don't mark as used")

    p = sub.add_parser("analyze", help="Run post-session analysis")
    p.add_argument("--text", help="Conversation text")
    p.add_argument("--file", "-f", help="File with conversation text")
    p.add_argument("--conversation-id", help="Conversation ID to link")

    p = sub.add_parser("decay", help="Apply memory decay")
    p.add_argument("--rate", type=float, default=0.95)
    p.add_argument("--min-importance", type=float, default=0.1)

    p = sub.add_parser("recent", help="Show recent memories")
    p.add_argument("--limit", "-n", type=int, default=10)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "init": cmd_init, "start": cmd_start, "stats": cmd_stats,
        "remember": cmd_remember, "search": cmd_search, "loops": cmd_loops,
        "entities": cmd_entities, "context": cmd_context, "analyze": cmd_analyze,
        "decay": cmd_decay, "recent": cmd_recent,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
