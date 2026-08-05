"""
Hermes adapter — Hermes is a popular lightweight harness that expects
tools = [ {name, description, parameters: json-schema, execute: fn } ]

Also works for generic JSON-tool agents that follow same shape.

Usage:
    from acne.integrations.hermes_adapter import get_hermes_tools
    tools = get_hermes_tools()
    # hermes_agent = HermesAgent(tools=tools)
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path

def get_hermes_tools(hub=None, base_path: Optional[str]=None) -> List[Dict[str, Any]]:
    from ..hub import ContactsHub
    _hub = hub or ContactsHub(base=Path(base_path) if base_path else None)

    def _resolve(query: str, context: str = ""):
        r = _hub.resolve(query, context={"hint": context} if context else None)
        if not r:
            return {"ok": False, "error": f"no match for {query}"}
        contact = getattr(r, "contact", r)
        name = getattr(contact, "name", getattr(contact, "canonical_name", str(contact)))
        return {"ok": True, "name": name, "confidence": getattr(r,"confidence",0), "why": getattr(r,"why",""), "source": getattr(r,"source","resolver")}

    def _add(name: str, email: str = "", role: str = "", trigger: str = ""):
        c = _hub.add_contact(name=name, email=email, role=role, trigger=trigger)
        return {"ok": True, "id": c.id, "name": name}

    def _pipeline(raw_text: str, title: str = "doc"):
        r = _hub.pipeline_run(raw_text, title=title)
        return {"ok": True, "doc": r.get("document",{}).get("id"), "nodes": r["stage2"]["nodes_created"], "edges": r["stage2"]["edges_created"], "resolutions": r["stage3"]["resolutions"], "cache": r.get("cache")}

    def _graphrag(query: str, compressed: bool = True, hops: int = 2, budget_tokens: int = 600):
        res = _hub.graphrag(query, compressed=compressed, hops=hops, budget_tokens=budget_tokens)
        if compressed:
            return {"ok": True, "compressed": True, "saving": res.get("saving"), "facts": len(res.get("facts",[])), "seeds": res.get("seeds",[])[:5]}
        return {"ok": True, **res}

    def _disambiguate(query: str):
        return _hub.disambiguate(query)

    def _cache_stats():
        return _hub.cache_stats()

    tools = [
        {
            "name": "contacts_resolve",
            "description": "Resolve 'my designer', 'the client call' → real person with confidence+why. Use for vague references.",
            "parameters": {"type":"object","properties":{"query":{"type":"string"},"context":{"type":"string"}},"required":["query"]},
            "execute": _resolve,
        },
        {
            "name": "contacts_add",
            "description": "Add contact with optional trigger phrase",
            "parameters": {"type":"object","properties":{"name":{"type":"string"},"email":{"type":"string"},"role":{"type":"string"},"trigger":{"type":"string"}},"required":["name"]},
            "execute": _add,
        },
        {
            "name": "run_pipeline",
            "description": "4-stage TLPG ingest→extract→resolve→graph, dedup cached",
            "parameters": {"type":"object","properties":{"raw_text":{"type":"string"},"title":{"type":"string"}},"required":["raw_text"]},
            "execute": _pipeline,
        },
        {
            "name": "search_entity_graph",
            "description": "Hybrid GraphRAG multi-hop + provenance, compressed 82-87% cheaper, use compressed=True for expensive models",
            "parameters": {"type":"object","properties":{"query":{"type":"string"},"compressed":{"type":"boolean"},"hops":{"type":"integer"},"budget_tokens":{"type":"integer"}},"required":["query"]},
            "execute": _graphrag,
        },
        {
            "name": "disambiguate_entity",
            "description": "SAME_AS cluster for ambiguous entity like 'A. Chen' vs 'Alice Chen'",
            "parameters": {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]},
            "execute": _disambiguate,
        },
        {
            "name": "cache_stats",
            "description": "Token-cache ROI hits tokens money",
            "parameters": {"type":"object","properties":{}},
            "execute": _cache_stats,
        },
    ]
    return tools

def get_tools(*args, **kwargs):
    return get_hermes_tools(*args, **kwargs)
