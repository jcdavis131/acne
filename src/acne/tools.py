"""Stable integration facade for harness plugins.

The scout-cli `contacts` plugin (dottie monorepo, apps/scout-cli) imports
exactly these five functions; treat their signatures as a public contract and
change them only additively. Each function builds a ContactsHub against the
default local store (~/.agentic-contacts) unless `base` is passed — tests pass
a tmp path, embedders may pin a workspace.

Everything here is local-first and honest about capability: `sync_all` walks a
directory of text/markdown files through the full pipeline (ingest → extract →
resolve); it does not fabricate the private bundles-manifest sync that older
plugin metadata referenced, and says so in its result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .hub import ContactsHub

_SYNC_SUFFIXES = {".md", ".txt"}


def _hub(base: Optional[Path | str] = None) -> ContactsHub:
    return ContactsHub(base=base) if base else ContactsHub()


def resolve_contact(query: str, base: Optional[Path | str] = None) -> Dict[str, Any]:
    """Resolve a fuzzy phrase ('my designer') to a contact with confidence and why."""
    res = _hub(base).resolve(query)
    d = res.to_dict() if hasattr(res, "to_dict") else dict(res)
    contact = d.get("contact")
    return {
        "query": d.get("query", query),
        "contact": contact,
        "confidence": d.get("confidence", 0.0),
        "why": d.get("why", ""),
        "trigger_matched": d.get("trigger_matched") or (
            d.get("why", "").split("'")[1] if "matched '" in d.get("why", "") else None
        ),
        "source": d.get("source", "resolver"),
    }


def search_nodes(
    query: str,
    top_k: int = 5,
    node_class: Optional[str] = None,
    base: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Dense vector search over TLPG nodes, optionally filtered by node class."""
    hub = _hub(base)
    nodes = hub.tlpg.vector_search_nodes(query, top_k=top_k, node_class=node_class, _cache=hub.cache)
    return [n.to_dict() for n in nodes]


def graphify_query(
    query: str,
    hops: int = 2,
    top_k: int = 5,
    compressed: bool = False,
    budget_tokens: int = 600,
    base: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Hybrid GraphRAG: vector seeds + multi-hop traversal with provenance."""
    return _hub(base).graphrag(
        query, hops=hops, top_k=top_k, compressed=compressed, budget_tokens=budget_tokens
    )


def health_report(base: Optional[Path | str] = None) -> Dict[str, Any]:
    """Composite health: contact store, TLPG, and token-cache statistics."""
    hub = _hub(base)
    return {
        "contacts": hub.stats(),
        "tlpg": hub.tlpg_stats(),
        "cache": hub.cache_stats(),
        "store_base": str(hub.store.base),
    }


def sync_all(
    manifest_path: Optional[str] = None,
    source_dir: Optional[str] = None,
    base: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Pipeline every .md/.txt under `source_dir` (ingest → extract → resolve).

    `manifest_path` is accepted for caller compatibility but this public
    package has no bundles-manifest concept; when only a manifest is given,
    its parent directory is walked instead and the result says so.
    """
    hub = _hub(base)
    note = None
    if source_dir is None:
        if manifest_path:
            source_dir = str(Path(manifest_path).expanduser().parent)
            note = (
                "manifest_path has no meaning in the public acne package; "
                "walked its parent directory instead"
            )
        else:
            source_dir = str(Path.home() / "workspace")
    root = Path(source_dir).expanduser()
    if not root.is_dir():
        return {"synced": 0, "errors": [f"source dir not found: {root}"], "note": note}
    synced, errors = [], []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in _SYNC_SUFFIXES or not p.is_file():
            continue
        try:
            r = hub.pipeline_run(p, title=p.stem)
            synced.append({"file": str(p), "chunks": r.get("chunk_count")})
        except Exception as e:
            errors.append(f"{p}: {e}")
    resolutions = hub.resolve_entities()
    out: Dict[str, Any] = {
        "synced": len(synced),
        "files": synced[:50],
        "resolutions": len(resolutions),
        "errors": errors,
        "graphify": {"resolutions": len(resolutions)},
    }
    if note:
        out["note"] = note
    return out
