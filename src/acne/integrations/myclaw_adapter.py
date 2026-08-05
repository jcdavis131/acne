"""
MyClaw / MyClaw-Dottie adapter — Cameron's own claw harness expects
a `bigbang` style plugin manifest plus plain functions.

This module provides:
1) get_myclaw_tools() → list of callable tools for direct import
2) MYCLAW_MANIFEST snippet for drop-in

MyClaw (like Scout's bigbang) looks for:
  name, description, version, entry, tools[]

Usage:
    from acne.integrations.myclaw_adapter import get_myclaw_tools
    tools = get_myclaw_tools()
    # wire into your claw agent loop

Or copy manifest snippet into your myclaw plugin yaml.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path

MYCLAW_MANIFEST = {
    "name": "contacts",
    "description": "Local-first people memory + TLPG 4-stage + token-cache for expensive agents. 6 native tools, 13 via MCP.",
    "version": "0.2.1",
    "entry": "cli.py",
    "single_source": "agentic-contacts pip + harness local store ~/workspace/bundles/memory/contacts_harness (fallback ~/.agentic-contacts)",
    "capabilities": {"network": False, "filesystem": True, "secrets": False},
    "tools": [
        "contacts_resolve",
        "contacts_add",
        "run_pipeline",
        "search_entity_graph",
        "disambiguate_entity",
        "cache_stats",
    ],
    "tools_full_via_mcp": 13,
    "wallets": {
        "token_cache": "compressed GraphRAG budget-capped, % smaller varies with size, tracks est. savings @ $0.015/1k assumed",
        "provenance": "every node EXTRACTED_FROM chunk→doc with checksum",
    }
}

def get_myclaw_tools(hub=None, base_path: Optional[str]=None):
    """Return native myclaw tool dicts (same shape Hermes uses)."""
    from .hermes_adapter import get_hermes_tools
    return get_hermes_tools(hub=hub, base_path=base_path)

# Native function exports for myclaw's `from contacts import contacts_resolve` style
def _hub_singleton(base_path=None):
    from ..hub import ContactsHub
    return ContactsHub(base=Path(base_path) if base_path else None)

_default_hub = None
def _get_default_hub():
    global _default_hub
    if _default_hub is None:
        _default_hub = _hub_singleton()
    return _default_hub

def contacts_resolve(query: str, context: str = ""):
    hub = _get_default_hub()
    r = hub.resolve(query, context={"hint": context} if context else None)
    if not r:
        return None
    contact = getattr(r, "contact", r)
    name = getattr(contact, "name", getattr(contact, "canonical_name", str(contact)))
    return {"name": name, "confidence": getattr(r, "confidence", 0), "why": getattr(r, "why", "")}

def run_pipeline(raw_text: str, title: str = "doc"):
    return _get_default_hub().pipeline_run(raw_text, title=title)

def search_entity_graph(query: str, compressed: bool = True):
    return _get_default_hub().graphrag(query, compressed=compressed)

def disambiguate_entity(query: str):
    return _get_default_hub().disambiguate(query)

def cache_stats():
    return _get_default_hub().cache_stats()

def contacts_add(name: str, email: str = "", role: str = "", trigger: str = ""):
    c = _get_default_hub().add_contact(name=name, email=email, role=role, trigger=trigger)
    return {"id": c.id}
