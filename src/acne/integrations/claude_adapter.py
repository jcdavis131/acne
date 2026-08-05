"""
Claude / Claude Code adapter — native tool calling for Anthropic.

Claude Code supports MCP and plain function tools with JSON Schema.
This is the same shape as our OpenAI tools, so Claude understands it instantly.

Usage in Claude Code:

1) MCP (recommended — 2 lines):
   # Add to your Claude Code MCP config (claude_desktop_config.json or .claude.json):
   {
     "mcpServers": {
       "agentic-contacts": {
         "command": "agentic-contacts",
         "args": ["mcp", "serve"],
         "env": {"CONTACTS_BASE": "~/workspace/bundles/memory/contacts_harness"}
       }
     }
   }
   # Now Claude sees 12 tools: contacts_resolve, run_pipeline, search_entity_graph, etc.

2) Native (pip module):
   from acne.integrations.claude_adapter import get_claude_tools
   tools = get_claude_tools()
   # Pass to your Claude Agent / SDK:
   # client.messages.create(model="claude-3-5-sonnet...", tools=tools, messages=[...])

All writes are tagged with source/confidence/why + tx_time, so a low-confidence
guess from a rogue agent never overwrites a manual contact, and merges are
soft SAME_AS links, not deletes — safe to share across all your agents.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path

def get_claude_tools(hub=None, base_path: Optional[str]=None) -> List[Dict[str, Any]]:
    """Claude-native tools (Anthropic format: name/description/input_schema). MCP is still preferred."""
    from .openai_adapter import get_openai_tools
    openai_tools = get_openai_tools()
    claude_tools: List[Dict[str, Any]] = []
    for t in openai_tools:
        fn = t.get("function", {}) if isinstance(t, dict) else {}
        claude_tools.append({
            "name": fn.get("name", t.get("name","")),
            "description": fn.get("description",""),
            "input_schema": fn.get("parameters", {"type":"object","properties":{}})
        })
    # Add extras that OpenAI shim misses but MCP has — keep tool count honest (6 tools)
    return claude_tools

def get_claude_tools_openai_compatible(*args, **kwargs):
    """If you need OpenAI-compatible shape for Claude tool calling."""
    from .openai_adapter import get_openai_tools as _oo
    return _oo()

def get_claude_code_skill() -> Dict[str, Any]:
    return {
        "name": "agentic-contacts",
        "description": "Local-first people memory for Claude Code. Resolve 'my designer', remember triggers, run 4-stage pipeline with provenance, token-cache aware.",
        "version": "0.2.1",
        "mcp_command": "agentic-contacts mcp serve",
        "store": "~/workspace/bundles/memory/contacts_harness/",
        "safety": "manual > calendar > heuristic (0.2-0.35 hint, never overwrites real), SAME_AS soft merges, tx_time history, source labels",
    }

def dispatch(tool_name: str, args: Dict[str, Any], hub=None):
    from .openai_adapter import dispatch as _dispatch
    return _dispatch(tool_name, args, hub=hub)

def get_tools(*args, **kwargs):
    return get_claude_tools(*args, **kwargs)
