"""Post-session analysis — generates prepared context for next session."""

import json
import os

from cortex_memory.config import get_config, load_env
from cortex_memory.db.store import (
    recent_memories, get_open_loops, save_prepared_context,
    mark_analyzed, start_conversation, end_conversation
)

load_env()

ANALYSIS_PROMPT = """You are analyzing a conversation between an AI assistant and a user.
Your job is to produce a structured context summary that will be injected into the assistant's system prompt at the start of the next session.

## Recent Conversation
{conversation}

## Recent Memories (from past interactions)
{memories}

## Current Open Loops
{open_loops}

---

Produce a JSON response with exactly this structure:
{{
  "context_summary": "2-3 sentence summary of where things left off and what matters most right now",
  "open_loops": [
    {{
      "summary": "What's unfinished",
      "priority": "high|medium|low",
      "follow_up_question": "Natural question to re-engage on this topic"
    }}
  ],
  "selected_memories": [
    {{
      "content": "The actual memory text (quote if from conversation)",
      "reason": "Why this memory matters for the next session"
    }}
  ],
  "topic_index": "comma-separated list of topics discussed",
  "priority_topics": "top 3-5 most important topics right now"
}}

Be concise. Focus on what the assistant needs to know to be immediately useful in the next session.
Only include open loops that are genuinely unfinished — not things that were resolved.
Select 3-8 memories that are most relevant for continuity."""


def build_analysis_input(conversation_text):
    memories = recent_memories(200)
    loops = get_open_loops(10)
    memory_text = "\n".join([
        f"- [{m['memory_type']}] {m['content']}" for m in memories[:50]
    ]) or "(No prior memories yet)"
    loop_text = "\n".join([
        f"- [{l['priority']}] {l['summary']}" for l in loops
    ]) or "(No open loops)"
    return {
        "prompt": ANALYSIS_PROMPT.format(
            conversation=conversation_text, memories=memory_text, open_loops=loop_text
        )
    }


def call_llm(prompt):
    """Call the configured LLM provider for analysis."""
    cfg = get_config()
    provider = cfg["analysis"].get("provider", "anthropic")
    model = cfg["analysis"].get("model", "claude-haiku-4-5")

    if provider == "anthropic":
        return _call_anthropic(prompt, model)
    elif provider == "openai":
        return _call_openai(prompt, model)
    else:
        raise ValueError(f"Unknown analysis provider: {provider}. Use 'anthropic' or 'openai'.")


def _call_anthropic(prompt, model):
    try:
        import anthropic
    except ImportError:
        raise ImportError("Install anthropic: pip install cortex-memory[anthropic]")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model, max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return _parse_json(response.content[0].text)


def _call_openai(prompt, model):
    try:
        import openai
    except ImportError:
        raise ImportError("Install openai: pip install cortex-memory[openai]")
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=model or "gpt-4o-mini", max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return _parse_json(response.choices[0].message.content)


def _parse_json(text):
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def build_prepared_prompt(analysis):
    parts = []
    loops = analysis.get("open_loops", [])
    if loops:
        parts.append("🔄 OPEN LOOPS - FOLLOW UP ON THESE FIRST:")
        for loop in loops:
            parts.append(f"• {loop['summary'].upper()} [{loop['priority']}]")
            if loop.get("follow_up_question"):
                parts.append(f"  Ask: \"{loop['follow_up_question']}\"")
        parts.append("")
    summary = analysis.get("context_summary", "")
    if summary:
        parts.append("🧠 KEY CONTEXT FOR THIS SESSION:")
        parts.append(summary)
        parts.append("")
    priority = analysis.get("priority_topics", "")
    if priority:
        parts.append(f"Priority Topics: {priority}")
        parts.append("")
    topics = analysis.get("topic_index", "")
    if topics:
        parts.append(f"📚 COMPREHENSIVE TOPIC INDEX: {topics}")
        parts.append("")
    memories = analysis.get("selected_memories", [])
    if memories:
        parts.append("Relevant Memories:")
        for mem in memories:
            parts.append(f"• {mem['content']}")
            if mem.get("reason"):
                parts.append(f"  ({mem['reason']})")
        parts.append("")
    return "\n".join(parts)


def run_analysis(conversation_text, conversation_id=None):
    input_data = build_analysis_input(conversation_text)

    try:
        result = call_llm(input_data["prompt"])
    except Exception as e:
        return {"error": str(e)}

    if not result:
        return None

    # Filter out any loops that are already resolved
    current_open_loop_summaries = {l["summary"] for l in get_open_loops(100)}
    result["open_loops"] = [
        loop for loop in result.get("open_loops", [])
        if loop.get("summary") in current_open_loop_summaries
    ]

    prepared_prompt = build_prepared_prompt(result)

    if not conversation_id:
        conversation_id = start_conversation("manual", "cli")
        end_conversation(conversation_id, result.get("context_summary", ""))

    context_id = save_prepared_context(
        conversation_id=conversation_id,
        context_summary=result.get("context_summary", ""),
        open_loops_json=result.get("open_loops", []),
        selected_memories_json=result.get("selected_memories", []),
        topic_index=result.get("topic_index", ""),
        priority_topics=result.get("priority_topics", ""),
        prepared_prompt=prepared_prompt
    )

    if conversation_id:
        mark_analyzed(conversation_id)

    return {
        "context_id": context_id,
        "analysis": result,
        "prepared_prompt": prepared_prompt
    }
