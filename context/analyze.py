"""Post-session analysis — generates prepared context for next session."""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env for API key
from pathlib import Path
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from db.store import (
    recent_memories, get_open_loops, save_prepared_context,
    mark_analyzed
)
from vector.embeddings import search as vec_search

# Analysis prompt template
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


def build_analysis_input(conversation_text: str) -> dict:
    """Build the input for the analysis model."""
    memories = recent_memories(200)
    loops = get_open_loops(10)
    
    memory_text = "\n".join([
        f"- [{m['memory_type']}] {m['content']}" 
        for m in memories[:50]  # Top 50 for prompt size
    ]) or "(No prior memories yet)"
    
    loop_text = "\n".join([
        f"- [{l['priority']}] {l['summary']}"
        for l in loops
    ]) or "(No open loops)"
    
    return {
        "prompt": ANALYSIS_PROMPT.format(
            conversation=conversation_text,
            memories=memory_text,
            open_loops=loop_text
        ),
        "memories": memories,
        "loops": loops
    }


def analyze_with_anthropic(prompt: str) -> dict:
    """Call Anthropic API for analysis. Uses Haiku for cost efficiency."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text
        # Parse JSON from response
        # Handle potential markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return json.loads(text.strip())
    except Exception as e:
        print(f"Analysis error: {e}")
        return None


def run_analysis(conversation_text: str, conversation_id: str = None) -> dict:
    """
    Run full post-session analysis.
    
    Returns the prepared context dict, or None on failure.
    """
    input_data = build_analysis_input(conversation_text)
    result = analyze_with_anthropic(input_data["prompt"])
    
    if not result:
        print("Analysis failed — no result from model")
        return None
    
    # Build injection-ready prompt
    prepared_prompt = build_prepared_prompt(result)
    
    # Save to database — if no conversation_id, create one
    if not conversation_id:
        from db.store import start_conversation, end_conversation
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
    
    print(f"Analysis complete. Context ID: {context_id}")
    return {
        "context_id": context_id,
        "analysis": result,
        "prepared_prompt": prepared_prompt
    }


def build_prepared_prompt(analysis: dict) -> str:
    """Build the injection-ready system prompt text from analysis results."""
    parts = []
    
    # Open loops
    loops = analysis.get("open_loops", [])
    if loops:
        parts.append("🔄 OPEN LOOPS - FOLLOW UP ON THESE FIRST:")
        for loop in loops:
            parts.append(f"• {loop['summary'].upper()} [{loop['priority']}]")
            if loop.get("follow_up_question"):
                parts.append(f"  Ask: \"{loop['follow_up_question']}\"")
        parts.append("")
    
    # Context summary
    summary = analysis.get("context_summary", "")
    if summary:
        parts.append("🧠 KEY CONTEXT FOR THIS SESSION:")
        parts.append(summary)
        parts.append("")
    
    # Priority topics
    priority = analysis.get("priority_topics", "")
    if priority:
        parts.append(f"Priority Topics: {priority}")
        parts.append("")
    
    # Topic index
    topics = analysis.get("topic_index", "")
    if topics:
        parts.append(f"📚 COMPREHENSIVE TOPIC INDEX: {topics}")
        parts.append("")
    
    # Selected memories
    memories = analysis.get("selected_memories", [])
    if memories:
        parts.append("Relevant Memories:")
        for mem in memories:
            parts.append(f"• {mem['content']}")
            if mem.get("reason"):
                parts.append(f"  ({mem['reason']})")
        parts.append("")
    
    return "\n".join(parts)


if __name__ == "__main__":
    # Test with a sample conversation
    test_convo = """
    Gerry: Check my calendar for tomorrow
    Quinn: Let me look... You have a 1:1 with Josh at 5pm and a CSM follow-up at 2:30pm
    Gerry: Good. Remind me to prep for Josh. I need to discuss the AI tools review Sara asked about.
    Quinn: Got it. I'll remind you before the 1:1.
    """
    
    result = run_analysis(test_convo)
    if result:
        print("\n--- PREPARED PROMPT ---")
        print(result["prepared_prompt"])
