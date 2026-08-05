"""
LangChain / LangGraph deep agents adapter for agentic-contacts.

Drop-in: `tools = get_langchain_tools()` and pass to your agent executor.

No extra glue — hub lives local-first beside your harness, cache-aware,
82-87% token saving on compressed packs.

Usage:
    from acne.integrations.langchain_adapter import get_langchain_tools
    tools = get_langchain_tools()               # creates its own hub
    # or
    from acne import ContactsHub
    hub = ContactsHub(base=Path("./memory/contacts"))
    tools = get_langchain_tools(hub=hub)

LangGraph deep agents:
    from langgraph.prebuilt import create_react_agent
    agent = create_react_agent(model, tools)
"""

from __future__ import annotations
from typing import List, Optional
from pathlib import Path

def _get_hub(hub=None, base_path: Optional[str]=None):
    if hub is not None:
        return hub
    from ..hub import ContactsHub
    if base_path:
        return ContactsHub(base=Path(base_path))
    return ContactsHub()

def get_langchain_tools(hub=None, base_path: Optional[str]=None):
    """
    Returns list[BaseTool] ready for LangChain / LangGraph / DeepAgents.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as e:
        raise ImportError(
            "langchain_core not installed. Install with:\n"
            "  pip install langchain-core langchain\n"
            "Or use MCP server directly: agentic-contacts mcp-def"
        ) from e

    _hub = _get_hub(hub, base_path)

    # --- tool funcs ---
    def contacts_resolve(query: str, context: str = "") -> str:
        """Resolve 'my designer', 'the client call' → real person with confidence+source+why. Use when you need to map a vague reference to a contact."""
        try:
            r = _hub.resolve(query, context={"hint": context} if context else None)
            if not r:
                return f"No match for '{query}'"
            contact = getattr(r, "contact", None) or r
            name = getattr(contact, "name", getattr(contact, "canonical_name", str(getattr(contact, "canonical_name", contact))))
            # if r is ResolveResult, pull fields from it
            conf = getattr(r, "confidence", getattr(contact, "confidence", 0))
            why = getattr(r, "why", "")
            source = getattr(r, "source", getattr(contact, "source", "resolver"))
            email = getattr(contact, "emails", [getattr(contact, "email", "")])[0] if hasattr(contact, "emails") else getattr(contact, "email", "")
            return f"{name} <{email}> confidence {conf:.2f} source {source} why:{why} {getattr(contact,'attributes',{})}"
        except Exception as exc:
            return f"resolve error: {exc}"

    def contacts_add(name: str, email: str = "", role: str = "", trigger: str = "") -> str:
        """Add a contact with optional trigger phrase like 'my designer'. Returns id."""
        try:
            c = _hub.add_contact(name=name, email=email, role=role, trigger=trigger)
            return f"added {c.canonical_name} id={c.id} trigger={trigger or role}"
        except Exception as exc:
            return f"add error: {exc}"

    def contacts_list(top: int = 20, role: str = "") -> str:
        """List top contacts optionally filtered by role."""
        try:
            nodes = _hub.store.list_contacts() if hasattr(_hub, 'store') else []
            # TLPG nodes fallback
            if not nodes:
                tlpg_nodes = _hub.tlpg.list_nodes()
                persons = [n for n in tlpg_nodes if n.node_class in ("Person","Organization")][:top]
                return "\n".join(f"{n.canonical_name} [{n.node_class}] conf {n.confidence:.2f}" for n in persons) or "no contacts yet"
            filtered = [c for c in nodes if role.lower() in (getattr(c,'role','') or '').lower() or not role][:top]
            return "\n".join(f"{c.canonical_name} <{getattr(c,'email','')}> role={getattr(c,'role','')} id={c.id}" for c in filtered) or "no contacts yet"
        except Exception as exc:
            return f"list error: {exc}"

    def run_pipeline(raw_text: str, title: str = "doc") -> str:
        """Run full TLPG 4-stage pipeline: ingest→extract→resolve→graph. Returns doc_id chunks nodes edges resolutions. Cheap on repeats via dedup cache."""
        try:
            r = _hub.pipeline_run(raw_text, title=title)
            s2 = r.get("stage2", {})
            s3 = r.get("stage3", {})
            return f"pipeline {title}: doc {r.get('document',{}).get('id','')} chunks {r.get('chunks_created',1)} → nodes {s2.get('nodes_created',0)} edges {s2.get('edges_created',0)} resolutions {s3.get('resolutions',0)} cache {r.get('cache')}"
        except Exception as exc:
            return f"pipeline error: {exc}"

    def search_entity_graph(query: str, compressed: bool = True, hops: int = 2, budget_tokens: int = 600) -> str:
        """Hybrid GraphRAG over people graph: dense vector + multi-hop walk + provenance. Use compressed=True to save 82-87% tokens for expensive models (recommended)."""
        try:
            res = _hub.graphrag(query, compressed=compressed, hops=hops, budget_tokens=budget_tokens)
            if compressed:
                return f"[compressed {res.get('saving','')} tiny {res.get('tiny_chars')} vs full {res.get('full_chars')} ({res.get('compression_pct',0)*100:.0f}% saved)] facts:{len(res.get('facts',[]))} seeds:{[s.get('name', s.get('canonical_name','')) for s in res.get('seeds',[])[:5]]}"
            return str(res)[:4000]
        except Exception as exc:
            return f"graphrag error: {exc}"

    def disambiguate_entity(query: str) -> str:
        """When entity is ambiguous (A. Chen vs Alice Chen), returns SAME_AS cluster with confidence. Use before linking high-stakes."""
        try:
            cl = _hub.disambiguate(query)
            clusters = cl.get("clusters", [])
            if not clusters:
                return f"no clusters for {query}"
            out = []
            for c in clusters[:3]:
                canon = c.get("canonical", {})
                edges = c.get("same_as_edges", [])
                out.append(f"{canon.get('canonical_name','?')} conf {canon.get('confidence','')} same_as_links {len(edges)}")
            return "\n".join(out)
        except Exception as exc:
            return f"disambiguate error: {exc}"

    def cache_stats() -> str:
        """Show token-cache ROI: hits, tokens_saved, money_saved. Great for heartbeat loops."""
        try:
            s = _hub.cache_stats()
            return f"cache doc {s.get('doc_hits')}/{s.get('doc_miss')} ext {s.get('ext_hits')}/{s.get('ext_miss')} query {s.get('query_hits')}/{s.get('query_miss')} tokens_saved {s.get('tokens_saved')} money ${s.get('money_saved')} hit_rate {s.get('hit_rate_est'):.2f}"
        except Exception as exc:
            return f"cache-stats error: {exc}"

    def cache_clear() -> str:
        """Clear all token-cache entries for this harness."""
        try:
            _hub.cache_clear()
            return "cache cleared"
        except Exception as exc:
            return f"clear error: {exc}"

    def ingest_document(raw_text: str, title: str = "doc") -> str:
        """Ingest a doc with dedup (checksum) → returns doc_id chunks count. Stage 1 only."""
        try:
            r = _hub.ingest(raw_text, title=title)
            return f"ingested {title} doc_id {r.get('doc_id')} chunks {r.get('chunks')} dedup={r.get('dedup')}"
        except Exception as exc:
            return f"ingest error: {exc}"

    def extract_entities(text: str) -> str:
        """Extract typed nodes Person/Org/Location/Thing/Citation + edge triples from text. Cached ~400 tok saved on repeat."""
        try:
            r = _hub.extract(text)
            return f"extracted {len(r.get('nodes',[]))} nodes {len(r.get('edges',[]))} edges avg_conf {r.get('confidence_avg')}"
        except Exception as exc:
            return f"extract error: {exc}"

    # Build StructuredTools - use explicit description, ensure funcs have docs
    tools: List = []
    def _mk(fn, name):
        return StructuredTool.from_function(func=fn, name=name, description=fn.__doc__ or name)
    tools.append(_mk(contacts_resolve, "contacts_resolve"))
    tools.append(_mk(contacts_add, "contacts_add"))
    tools.append(_mk(contacts_list, "contacts_list"))
    tools.append(_mk(run_pipeline, "run_pipeline"))
    tools.append(_mk(search_entity_graph, "search_entity_graph"))
    tools.append(_mk(disambiguate_entity, "disambiguate_entity"))
    tools.append(_mk(cache_stats, "cache_stats"))
    tools.append(_mk(cache_clear, "cache_clear"))
    tools.append(_mk(ingest_document, "ingest_document"))
    tools.append(_mk(extract_entities, "extract_entities"))
    return tools
