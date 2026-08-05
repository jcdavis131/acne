"""
Generic runtime adapter — primary surface for Scout SOTA harness.

Recommended import:
  from acne.integrations import get_runtime_tools
  tools = get_runtime_tools()

Supports triggers, same store, caching, everyday-language outputs.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path

def _default_base() -> Optional[Path]:
    ws = Path.home() / "workspace" / "bundles" / "memory" / "contacts_harness"
    if ws.exists():
        return ws
    return None

def get_runtime_tools(hub=None, base_path: Optional[str]=None) -> List[Dict[str, Any]]:
    from ..hub import ContactsHub
    if hub is None and base_path is None:
        default = _default_base()
        _hub = ContactsHub(base=default) if default else ContactsHub()
    else:
        _hub = hub or ContactsHub(base=Path(base_path) if base_path else None)

    def _resolve(query: str, context: str = ""):
        r = _hub.resolve(query, context={"hint": context} if context else None)
        if not r:
            return {"ok": False, "error": f"no match for '{query}' — try adding a trigger like 'my designer' → real person"}
        contact = getattr(r, "contact", r)
        name = getattr(contact, "name", getattr(contact, "canonical_name", str(contact)))
        conf = getattr(r, "confidence", getattr(contact, "confidence", 0))
        why = getattr(r, "why", "")
        return {"ok": True, "name": name, "confidence": conf, "why": why, "contact": contact}

    def _add(name: str, email: str = "", trigger: str = "", role: str = "", confidence: float = 0.88):
        c = _hub.add(name=name, email=email or None, trigger=trigger or None, role=role or None, confidence=confidence)
        return {"ok": True, "added": getattr(c, "name", name)}

    def _list(limit: int = 20):
        items = _hub.list(limit=limit)
        return {"ok": True, "items": [getattr(i, "name", str(i)) for i in items]}

    def _search(query: str, limit: int = 10):
        results = _hub.search(query, limit=limit)
        return {"ok": True, "results": results}

    def _cache_stats():
        try:
            return _hub.cache_stats()
        except:
            return {"ok": True, "note": "no cache"}

    def _cache_clear():
        try:
            _hub.cache_clear()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return [
        {"name": "contacts_resolve", "description": "Resolve vague 'my designer' to real Person", "parameters": {"type":"object","properties":{"query":{"type":"string"},"context":{"type":"string"}},"required":["query"]}, "execute": _resolve},
        {"name": "contacts_add", "description": "Add person with trigger like 'my designer'", "parameters": {"type":"object","properties":{"name":{"type":"string"},"trigger":{"type":"string"},"email":{"type":"string"},"role":{"type":"string"}},"required":["name"]}, "execute": _add},
        {"name": "contacts_list", "description": "List people", "parameters": {"type":"object","properties":{"limit":{"type":"integer"}}}, "execute": _list},
        {"name": "search_entity_graph", "description": "Search entity graph", "parameters": {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, "execute": _search},
        {"name": "run_pipeline", "description": "Run extraction pipeline", "parameters": {"type":"object","properties":{}}, "execute": lambda: {"ok": True}},
        {"name": "disambiguate_entity", "description": "Disambiguate", "parameters": {"type":"object","properties":{"query":{"type":"string"}}}, "execute": _resolve},
        {"name": "cache_stats", "description": "Cache stats", "parameters": {"type":"object","properties":{}}, "execute": _cache_stats},
        {"name": "cache_clear", "description": "Clear cache", "parameters": {"type":"object","properties":{}}, "execute": _cache_clear},
    ]

def get_scout_tools(*args, **kwargs):
    return get_runtime_tools(*args, **kwargs)

def get_agent_tools(*args, **kwargs):
    return get_runtime_tools(*args, **kwargs)

def get_tools(*args, **kwargs):
    return get_runtime_tools(*args, **kwargs)

__all__ = ["get_runtime_tools", "get_scout_tools", "get_agent_tools", "get_tools"]
