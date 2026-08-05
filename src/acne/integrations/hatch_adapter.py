"""
Hatch adapter — native for Meta's Hatch agents.

Hatch agents run on a dedicated VM like this one, with skills under ~/skills/.
They love tools that are local-first, cache-aware, and explain why they matched.

This module gives you Hatch-native tools without any extra glue:

  from acne.integrations.hatch_adapter import get_hatch_tools
  tools = get_hatch_tools()   # [{name, description, parameters, execute}]

It mirrors the same 6 tools every other harness uses, so triggers you set
in Scout, LangChain, MyClaw, etc. show up here too — same store at
~/workspace/bundles/memory/contacts_harness/.

Hatch extras:
- get_hatch_skill() → dict you can drop into a Hatch Skill's SKILL.md
- Uses memory_search when available to enrich confidence
- Works with Hatch's everyday-language expectation (why/confidence in output)

pip install agentic-contacts            # no extra deps
pip install agentic-contacts[hatch]     # same, just semantic
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path

# Keep same canonical tool shapes as other adapters so knowledge carries over
def _default_base() -> Optional[Path]:
    # Prefer the shared workspace harness if present (so all agents see same data)
    # Fallback to ~/.agentic-contacts which is the pip default
    ws = Path.home() / "workspace" / "bundles" / "memory" / "contacts_harness"
    if ws.exists():
        return ws
    return None

def get_hatch_tools(hub=None, base_path: Optional[str]=None) -> List[Dict[str, Any]]:
    from ..hub import ContactsHub
    if hub is None and base_path is None:
        default = _default_base()
        _hub = ContactsHub(base=default) if default else ContactsHub()
    else:
        _hub = hub or ContactsHub(base=Path(base_path) if base_path else None)

    # Try to use memory search if running inside Hatch, otherwise degrade gracefully
    def _memory_hint(name: str) -> str:
        # Hatch provides memory_search as a tool invocation, not a python import.
        # We try the python import for local testing, but swallow all errors.
        try:
            import importlib
            m = importlib.import_module("default")
            fn = getattr(m, "memory_search", None)
            if fn and callable(fn):
                hits = fn(queries=[name])
                if hits:
                    return f" memory_hint found {len(hits)} mentions"
        except Exception:
            pass
        # Also try skill-style host tool via hatch host API if present
        try:
            # Some Hatch runtimes inject memory_search via host
            from skills import memory as _mem  # type: ignore
            hits = _mem.search([name])
            if hits:
                return f" memory_hint {len(hits)}"
        except Exception:
            pass
        return ""

    def _resolve(query: str, context: str = ""):
        r = _hub.resolve(query, context={"hint": context} if context else None)
        if not r:
            return {"ok": False, "error": f"no match for '{query}' — try adding a trigger like 'my designer' → real person"}
        contact = getattr(r, "contact", r)
        name = getattr(contact, "name", getattr(contact, "canonical_name", str(contact)))
        conf = getattr(r, "confidence", getattr(contact, "confidence", 0))
        why = getattr(r, "why", "")
        return {
            "ok": True,
            "name": name,
            "confidence": float(conf),
            "why": why,
            "source": getattr(r, "source", "resolver"),
            "extra": _memory_hint(name),
            "contact": contact.to_dict() if hasattr(contact, "to_dict") else str(contact),
        }

    def _add(name: str, email: str = "", role: str = "", trigger: str = "", phone: str = ""):
        c = _hub.add_contact(name=name, email=email, role=role, trigger=trigger)
        # phone goes into extras if provided (ContactsStore keeps it in phones)
        if phone and hasattr(c, "phones") and phone not in c.phones:
            c.phones.append(phone)
            _hub.store.save_contact(c)
        return {"ok": True, "id": c.id, "name": name, "trigger": trigger}

    def _list(top: int = 20, role: str = ""):
        # legacy contacts first
        try:
            contacts = _hub.store.list_contacts()[:top]
            if contacts:
                if role:
                    contacts = [c for c in contacts if role.lower() in (getattr(c, "role", "") or "").lower()]
                return {"ok": True, "contacts": [c.to_dict() for c in contacts]}
        except Exception:
            pass
        nodes = _hub.tlpg.list_nodes()[:top]
        if role:
            nodes = [n for n in nodes if role.lower() in n.canonical_name.lower() or role.lower() in str(n.attributes).lower()]
        return {"ok": True, "nodes": [n.to_dict() for n in nodes]}

    def _pipeline(raw_text: str, title: str = "doc"):
        r = _hub.pipeline_run(raw_text, title=title)
        return {
            "ok": True,
            "doc_id": r.get("document", {}).get("id"),
            "chunks": r.get("chunks"),
            "nodes_created": r["stage2"]["nodes_created"],
            "edges_created": r["stage2"]["edges_created"],
            "resolutions": r["stage3"]["resolutions"],
            "note": "local-first, no cloud, provenance EXTRACTED_FROM",
        }

    def _graphrag(query: str, compressed: bool = True, hops: int = 2, budget_tokens: int = 600):
        res = _hub.graphrag(query, compressed=compressed, hops=hops, budget_tokens=budget_tokens)
        if compressed:
            return {
                "ok": True,
                "compressed": True,
                "saving": res.get("saving"),
                "tiny_chars": res.get("tiny_chars"),
                "full_chars": res.get("full_chars"),
                "facts": res.get("facts", [])[:20],
                "seeds": res.get("seeds", [])[:6],
            }
        return {"ok": True, **res}

    def _disambiguate(query: str):
        return {"ok": True, **_hub.disambiguate(query)}

    def _cache_stats():
        s = _hub.cache_stats()
        return {
            "ok": True,
            "hits": f"doc {s.get('doc_hits')}/{s.get('doc_miss')} ext {s.get('ext_hits')}/{s.get('ext_miss')} query {s.get('query_hits')}/{s.get('query_miss')}",
            "tokens_saved": s.get("tokens_saved"),
            "money_saved": f"${s.get('money_saved')}",
            "hit_rate": s.get("hit_rate_est"),
            "note": "gets cheaper every heartbeat — ideal for always-on Hatch agents",
        }

    def _cache_clear():
        _hub.cache_clear()
        return {"ok": True, "cleared": True}

    tools = [
        {
            "name": "contacts_resolve",
            "description": "Resolve 'my designer', 'the client call', 'freelancer' → real person with confidence + why. Use when user mentions a vague person. Native for Hatch — returns why/confidence for everyday language answers.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "vague reference like 'my designer'"}, "context": {"type": "string", "description": "optional hint like 'the Figma file'"}}, "required": ["query"]},
            "execute": _resolve,
        },
        {
            "name": "contacts_add",
            "description": "Add a person with optional trigger phrase ('my designer') so you remember them next time. Local-first, no cloud.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "role": {"type": "string"}, "trigger": {"type": "string", "description": "phrase that maps to this person"}, "phone": {"type": "string"}}, "required": ["name"]},
            "execute": _add,
        },
        {
            "name": "contacts_list",
            "description": "List your top contacts or TLPG nodes, optionally filtered by role.",
            "parameters": {"type": "object", "properties": {"top": {"type": "integer"}, "role": {"type": "string"}}, "required": []},
            "execute": _list,
        },
        {
            "name": "run_pipeline",
            "description": "4-stage TLPG: ingest→extract→resolve→graph. Dedup-cached, provenance-aware, saves tokens on repeats.",
            "parameters": {"type": "object", "properties": {"raw_text": {"type": "string", "description": "email or doc blob"}, "title": {"type": "string"}}, "required": ["raw_text"]},
            "execute": _pipeline,
        },
        {
            "name": "search_entity_graph",
            "description": "Hybrid GraphRAG over people graph + multi-hop + provenance. Use compressed=True (default) for 80%+ token saving on expensive models — ideal for always-on Hatch agents.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "compressed": {"type": "boolean"}, "hops": {"type": "integer"}, "budget_tokens": {"type": "integer"}}, "required": ["query"]},
            "execute": _graphrag,
        },
        {
            "name": "disambiguate_entity",
            "description": "When 'A. Chen' could be 'Alice Chen', returns SAME_AS cluster with confidence. Ask agent if high-stakes.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            "execute": _disambiguate,
        },
        {
            "name": "cache_stats",
            "description": "Token-cache ROI for always-on agents: hits, tokens_saved, money_saved, hit_rate.",
            "parameters": {"type": "object", "properties": {}},
            "execute": _cache_stats,
        },
        {
            "name": "cache_clear",
            "description": "Clear token-cache (rarely needed).",
            "parameters": {"type": "object", "properties": {}},
            "execute": _cache_clear,
        },
    ]
    return tools

def get_openai_tools(*args, **kwargs):
    """Alias: Hatch tools are already OpenAI-compatible."""
    from .openai_adapter import get_openai_tools as _openai
    return _openai(*args, **kwargs)

def get_hatch_skill() -> Dict[str, Any]:
    """Returns a dict you can render into ~/skills/agentic-contacts/SKILL.md"""
    return {
        "name": "agentic-contacts",
        "description": "Local-first people memory + TLPG + token-cache for expensive agents. 8 native tools: resolve, add, list, pipeline, graphrag, disambiguate, cache. No cloud, privacy-first.",
        "version": "0.2.1",
        "entry": "from acne.integrations.hatch_adapter import get_hatch_tools",
        "tools": [t["name"] for t in get_hatch_tools()],
        "store": "~/workspace/bundles/memory/contacts_harness/",
        "install": "pip install agentic-contacts",
        "examples": [
            "tools = get_hatch_tools()\ntools[0]['execute']('my designer')",
            "hub = ContactsHub(); hub.add_contact(name='Alex', trigger='my designer')",
        ],
    }

def dispatch(tool_name: str, args: Dict[str, Any], hub=None):
    """Generic dispatch like other adapters."""
    tools = {t["name"]: t["execute"] for t in get_hatch_tools(hub=hub)}
    if tool_name not in tools:
        raise ValueError(f"unknown hatch tool {tool_name}. Available: {list(tools)}")
    return tools[tool_name](**args)

def get_tools(*args, **kwargs):
    return get_hatch_tools(*args, **kwargs)
