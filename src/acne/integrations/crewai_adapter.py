"""
CrewAI adapter — same hub, native CrewAI BaseTool.

pip install crewai

Usage:
    from acne.integrations.crewai_adapter import get_crewai_tools
    tools = get_crewai_tools()
    agent = Agent(..., tools=tools)
"""

from __future__ import annotations
from typing import List, Optional

def get_crewai_tools(hub=None, base_path: Optional[str]=None):
    try:
        from crewai.tools import BaseTool
    except ImportError as e:
        raise ImportError("crewai not installed: pip install crewai") from e

    from pathlib import Path
    from ..hub import ContactsHub
    _hub = hub or ContactsHub(base=Path(base_path) if base_path else None)

    def _make(name, desc, func):
        # dynamic subclass to capture closure
        class _T(BaseTool):
            _name: str = name
            _description: str = desc
            def _run(self, *args, **kwargs):
                return func(*args, **kwargs)
            # crewai expects name/description properties
            @property
            def name(self):
                return self._name
            @property
            def description(self):
                return self._description
        t = _T()
        t._name = name
        t._description = desc
        return t

    def resolve(q: str):
        r = _hub.resolve(q)
        if not r:
            return f"no match {q}"
        contact = getattr(r, "contact", None) or getattr(r, "canonical_name", None) or r
        # r is ResolveResult -> has .contact, .confidence, .why
        name = getattr(contact, "name", None) or getattr(contact, "canonical_name", str(contact))
        conf = getattr(r, "confidence", getattr(contact, "confidence", 0))
        why = getattr(r, "why", "")
        return f"{name} conf {conf:.2f} {why}" if conf else f"{name}"

    def pipeline(text: str, title: str="doc"):
        r = _hub.pipeline_run(text, title=title)
        # pipeline_run returns document dict + stage2/stage3 dicts
        s2 = r.get("stage2", {}) if isinstance(r, dict) else {}
        s3 = r.get("stage3", {}) if isinstance(r, dict) else {}
        return f"nodes {s2.get('nodes_created', s2.get('nodes', 0))} edges {s2.get('edges_created', s2.get('edges',0))} resolutions {len(s3.get('actions', s3)) if isinstance(s3, dict) else s3}"

    def graphrag(q: str, compressed: bool=True):
        res = _hub.graphrag(q, compressed=compressed)
        if compressed:
            return f"compressed {res.get('saving')} facts {len(res.get('facts',[]))}"
        return str(res)[:3000]

    def stats():
        s = _hub.cache_stats()
        return f"tokens {s.get('tokens_saved')} money {s.get('money_saved')} hit_rate {s.get('hit_rate_est')}"

    tools: List[BaseTool] = []
    tools.append(_make("contacts_resolve","Resolve 'my designer' → person with confidence, use for vague references", resolve))
    tools.append(_make("run_pipeline","Ingest→Extract→Resolve→Graph, 4-stage TLPG, dedup cached", pipeline))
    tools.append(_make("search_entity_graph","Hybrid GraphRAG multi-hop + provenance, compressed saves 82-87%", graphrag))
    tools.append(_make("cache_stats","Token-cache ROI hits tokens money", stats))
    return tools
