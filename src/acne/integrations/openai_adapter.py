"""
OpenAI / Autogen / Generic function-calling adapter.

Returns OpenAI-compatible tool definitions + dispatch.

Usage:
    from acne.integrations.openai_adapter import get_openai_tools, dispatch
    tools = get_openai_tools()
    # pass to client.chat.completions.create(tools=tools)
    # when model returns tool_calls, call dispatch(name, args, hub)
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional

OPENAI_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "contacts_resolve",
            "description": "Resolve 'my designer', 'the client call' → real person with confidence+source+why.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type":"string","description":"vague reference like 'my designer'"},"context": {"type":"string"}},
                "required": ["query"]
            }
        }
    },
    {
        "type":"function",
        "function":{
            "name":"contacts_add",
            "description":"Add contact with optional trigger phrase",
            "parameters":{"type":"object","properties":{"name":{"type":"string"},"email":{"type":"string"},"role":{"type":"string"},"trigger":{"type":"string"}},"required":["name"]}
        }
    },
    {
        "type":"function",
        "function":{
            "name":"run_pipeline",
            "description":"4-stage TLPG ingest→extract→resolve→graph, dedup cached",
            "parameters":{"type":"object","properties":{"raw_text":{"type":"string"},"title":{"type":"string"}},"required":["raw_text"]}
        }
    },
    {
        "type":"function",
        "function":{
            "name":"search_entity_graph",
            "description":"Hybrid GraphRAG multi-hop + provenance, compressed saves 82-87% tokens, use compressed=True for expensive models",
            "parameters":{"type":"object","properties":{"query":{"type":"string"},"compressed":{"type":"boolean"},"hops":{"type":"integer"},"budget_tokens":{"type":"integer"}},"required":["query"]}
        }
    },
    {
        "type":"function",
        "function":{
            "name":"disambiguate_entity",
            "description":"SAME_AS cluster for ambiguous entity like 'A. Chen' → Alice Chen",
            "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}
        }
    },
    {
        "type":"function",
        "function":{
            "name":"cache_stats",
            "description":"Token-cache ROI hits tokens_saved money_saved",
            "parameters":{"type":"object","properties":{}}
        }
    },
]

def get_openai_tools(hub=None, base_path: Optional[str]=None):
    # definition is static — hub not needed, but accept args so all adapters have same signature
    # and per-hub dispatch can still use hub via dispatch()
    return OPENAI_TOOLS

def dispatch(tool_name: str, args: Dict[str, Any], hub=None):
    from pathlib import Path
    from ..hub import ContactsHub
    _hub = hub or ContactsHub()
    if tool_name == "contacts_resolve":
        r = _hub.resolve(args.get("query",""), context={"hint":args.get("context","")} if args.get("context") else None)
        if not r:
            return {"no_match": True}
        # ResolveResult has .contact and .confidence and .why
        contact = getattr(r, "contact", None)
        if contact:
            name = getattr(contact, "name", getattr(contact, "canonical_name", str(contact)))
            return {"name": name, "confidence": getattr(r,"confidence",0), "why": getattr(r,"why",""), "contact": contact.to_dict() if hasattr(contact,"to_dict") else str(contact)}
        # fallback if resolver returns TLPG node directly
        name = getattr(r, "canonical_name", getattr(r, "name", str(r)))
        return {"name": name, "confidence": getattr(r,"confidence",0), "why": getattr(r,"why","")}
    if tool_name == "contacts_add":
        c = _hub.add_contact(name=args["name"], email=args.get("email",""), role=args.get("role",""), trigger=args.get("trigger",""))
        return {"id": c.id, "name": getattr(c, "name", getattr(c, "canonical_name", args["name"]))}
    if tool_name == "run_pipeline":
        return _hub.pipeline_run(args["raw_text"], title=args.get("title","doc"))
    if tool_name == "search_entity_graph":
        return _hub.graphrag(args["query"], compressed=args.get("compressed",True), hops=args.get("hops",2), budget_tokens=args.get("budget_tokens",600))
    if tool_name == "disambiguate_entity":
        return _hub.disambiguate(args["query"])
    if tool_name == "cache_stats":
        return _hub.cache_stats()
    raise ValueError(f"unknown tool {tool_name}")
