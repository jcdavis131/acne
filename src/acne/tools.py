"""
ACNE Contacts Power Suite — pure functions for scout-cli & MCP
Zero-deps, local-only, no cloud. Graceful when nodes.jsonl missing.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict, Any
import json, time
from datetime import datetime, timezone

def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def _get_hub(base: Optional[Path | str] = None, workspace: Optional[Path | str] = None):
    from .hub import ContactsHub
    if base:
        return ContactsHub(base=base)
    if workspace:
        return ContactsHub(workspace=workspace)
    # default to workspace auto-discovery: bundles/memory/contacts_harness
    ws = Path.home() / "workspace"
    return ContactsHub(workspace=ws)

# ---------------- pure functions ----------------

def resolve_contact(query: str, context: Optional[Dict[str, Any]] = None, base: Optional[str] = None, workspace: Optional[str] = None) -> Dict[str, Any]:
    """Resolve a contact phrase to canonical contact."""
    hub = _get_hub(base=base, workspace=workspace)
    try:
        res = hub.resolve(query, context=context)
        # resolver returns ResolveResult
        if hasattr(res, "to_dict"):
            return res.to_dict()
        if isinstance(res, dict):
            return res
        return {"query": query, "contact": None, "confidence": 0.0, "why": str(res)}
    except Exception as e:
        return {"query": query, "contact": None, "confidence": 0.0, "why": f"resolve failed: {e}", "error": str(e)}

def search_nodes(query: str, top_k: int = 5, node_class: Optional[str] = None, base: Optional[str] = None, workspace: Optional[str] = None) -> List[Dict[str, Any]]:
    """Vector search TLPG nodes."""
    hub = _get_hub(base=base, workspace=workspace)
    try:
        nodes = hub.tlpg.vector_search_nodes(query, top_k=top_k, node_class=node_class)
        return [n.to_dict() if hasattr(n, "to_dict") else n for n in nodes]
    except Exception as e:
        # graceful when nodes.jsonl missing -> empty
        return []

def graphify_query(query: str, hops: int = 2, top_k: int = 5, compressed: bool = False, budget_tokens: int = 600, base: Optional[str] = None, workspace: Optional[str] = None) -> Dict[str, Any]:
    """GraphRAG hybrid — seeds + multi-hop."""
    hub = _get_hub(base=base, workspace=workspace)
    try:
        res = hub.graphrag(query, hops=hops, top_k=top_k, compressed=compressed, budget_tokens=budget_tokens)
        return res
    except Exception as e:
        return {"query": query, "seeds": [], "nodes": [], "edges": [], "provenance_chunks": [], "hops": hops, "error": str(e), "cached": False}

def health_report(base: Optional[str] = None, workspace: Optional[str] = None) -> Dict[str, Any]:
    """Full harness health snapshot."""
    hub = _get_hub(base=base, workspace=workspace)
    out: Dict[str, Any] = {}
    try:
        out["contacts"] = hub.store.stats() if hasattr(hub.store, "stats") else {"contacts": len(hub.list_contacts())}
    except Exception as e:
        out["contacts"] = {"error": str(e)}
    try:
        tlpg_stats = hub.tlpg.stats()
        out["tlpg"] = tlpg_stats
        out["by_class"] = tlpg_stats.get("by_class", {})
    except Exception as e:
        out["tlpg"] = {"error": str(e)}
        out["by_class"] = {}
    try:
        out["cache"] = hub.cache.stats()
    except Exception as e:
        out["cache"] = {"error": str(e)}

    # stale triggers heuristic: triggers not used in last 30d or low confidence <0.4
    stale = []
    try:
        # ContactsStore may have triggers? list from store if exists
        triggers_file = hub.store.base / "triggers.jsonl" if hasattr(hub.store, "base") else None
        if triggers_file and triggers_file.exists():
            for line in triggers_file.read_text().splitlines()[:2000]:
                if not line.strip():
                    continue
                try:
                    t = json.loads(line)
                    if t.get("confidence", 1.0) < 0.4:
                        stale.append(t)
                except:
                    continue
        # also scan nodes for low conf
        nodes = hub.tlpg.list_nodes() if hasattr(hub.tlpg, "list_nodes") else []
        low_conf_nodes = [n.to_dict() for n in nodes if getattr(n, "confidence", 1.0) < 0.45][:20]
        out["low_conf_nodes"] = low_conf_nodes
    except Exception:
        pass
    out["stale_triggers"] = stale[:50]
    out["ts"] = _now_iso()
    return out

def sync_all(manifest_path: Optional[str] = None, base: Optional[str] = None, workspace: Optional[str] = None) -> Dict[str, Any]:
    """One-shot: sync_from_bundles + graphify_constructs + goal_healthcheck."""
    hub = _get_hub(base=base, workspace=workspace)
    res: Dict[str, Any] = {"ts": _now_iso()}
    # sync
    try:
        sync_res = hub.sync_from_bundles(manifest_path=manifest_path)
        res["sync"] = sync_res
    except Exception as e:
        res["sync"] = {"error": str(e)}
    # graphify
    try:
        g = hub.graphify_constructs()
        res["graphify"] = g
    except Exception as e:
        res["graphify"] = {"error": str(e)}
    # goal health
    try:
        health = hub.goal_healthcheck()
        res["goal_health"] = health
        # goal_writeback for audit
        try:
            wb = hub.goal_writeback()
            res["goal_writeback"] = wb
        except Exception:
            pass
    except Exception as e:
        res["goal_health"] = {"error": str(e)}
    # final stats
    try:
        res["stats"] = hub.tlpg.stats()
    except Exception:
        res["stats"] = {}
    return res

# Convenience dict for MCP tool routing
TOOLS = {
    "resolve_contact": resolve_contact,
    "search_nodes": search_nodes,
    "graphify_query": graphify_query,
    "health_report": health_report,
    "sync_all": sync_all,
}
