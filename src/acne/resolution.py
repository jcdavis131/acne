"""
resolution.py — Stage 3: Dynamic Entity Resolution & Disambiguation
Deterministic blocking, vector filtering, topological neighborhood analysis,
linkage vs merging with SAME_AS edges and confidence.
"""

from __future__ import annotations
from typing import List, Dict, Tuple, Optional, Set
import hashlib
import re
from collections import defaultdict
from .models import TLPGNode, TLPGEdge, ResolutionResult, _now_iso

# ------------------------------------------------------------------
# Similarity helpers — offline-friendly
# ------------------------------------------------------------------

def name_normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())

def initials(name: str) -> str:
    return "".join(w[0] for w in name.split() if w) .lower()

def is_abbrev(short: str, long: str) -> bool:
    # "A. Chen" vs "Alice Chen", "Alice C." vs "Alice Chen"
    s = name_normalize(short).replace(".", "").strip()
    l = name_normalize(long)
    s_parts = s.split()
    l_parts = l.split()
    if not s_parts or not l_parts:
        return False
    # Same last name, first initial matches
    if len(s_parts) == 2 and len(l_parts) >= 2:
        if s_parts[-1] == l_parts[-1] and s_parts[0] and l_parts[0] and s_parts[0][0] == l_parts[0][0]:
            return True
    if len(s_parts) == 2 and "." in short and s_parts[0][0] == l_parts[0][0] and s_parts[1] == l_parts[-1]:
        return True
    # "Alice C." vs "Alice Chen": first same, last initial
    if len(s_parts) == 2 and len(l_parts) == 2:
        if s_parts[0] == l_parts[0] and s_parts[1][0] == l_parts[1][0] and len(s_parts[1])==1:
            return True
    if s in l or l in s:
        return True
    return False

def jaccard(a: str, b: str) -> float:
    sa = set(name_normalize(a).split())
    sb = set(name_normalize(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def hash_embed(text: str, dim: int = 32) -> List[float]:
    h = hashlib.sha256(text.encode()).digest()
    vec = []
    for i in range(dim):
        vec.append(((h[i % len(h)] / 255.0) * 2) - 1)
    return vec

def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    ma = sum(x*x for x in a) ** 0.5
    mb = sum(x*x for x in b) ** 0.5
    if ma == 0 or mb == 0:
        return 0.0
    return dot / (ma * mb)

# ------------------------------------------------------------------
# Deterministic blocking & vector filtering
# ------------------------------------------------------------------

def blocking_key(node: TLPGNode) -> str:
    """
    Blocking: reduce O(n²) to buckets.
    Person → last name, Org → first token, Location → city, etc.
    """
    name = name_normalize(node.canonical_name)
    parts = name.split()
    if node.node_class == "Person":
        # last token is strong
        return f"P:{parts[-1][:4] if parts else ''}"
    if node.node_class == "Organization":
        return f"O:{parts[0][:5] if parts else ''}"
    if node.node_class == "Location":
        return f"L:{parts[0][:4] if parts else ''}"
    return f"T:{name[:4]}"

def vector_filter_candidates(nodes: List[TLPGNode], query_node: TLPGNode, threshold: float = 0.35) -> List[Tuple[TLPGNode, float]]:
    """
    Cheap vector similarity over name+aliases + abbreviation-aware recall.
    """
    q_emb = hash_embed(f"{query_node.canonical_name} {' '.join(query_node.aliases)} {query_node.attributes}")
    scored = []
    for n in nodes:
        if n.id == query_node.id:
            continue
        if n.node_class != query_node.node_class:
            continue
        txt = f"{n.canonical_name} {' '.join(n.aliases)} {n.attributes}"
        c = cosine(q_emb, hash_embed(txt))
        # recall boosts: abbrev match or lower jaccard
        abbrev_match = is_abbrev(query_node.canonical_name, n.canonical_name) or is_abbrev(n.canonical_name, query_node.canonical_name)
        jac = jaccard(query_node.canonical_name, n.canonical_name)
        if c >= threshold or jac > 0.25 or abbrev_match:
            # boost abbrev candidates so they rank high
            if abbrev_match:
                c = max(c, 0.85)
            scored.append((n, c))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:10]

# ------------------------------------------------------------------
# Topological neighborhood analysis
# ------------------------------------------------------------------

def topological_boost(query_node: TLPGNode, candidate: TLPGNode, tlpg_store) -> float:
    """
    If two nodes share neighbors (same org, same co-authors, same email domain),
    boost confidence.
    """
    if not tlpg_store:
        return 0.0
    q_edges = tlpg_store.get_edges_for(query_node.id)
    c_edges = tlpg_store.get_edges_for(candidate.id)

    q_neighbors = set()
    for e in q_edges:
        other = e.target_id if e.source_id == query_node.id else e.source_id
        q_neighbors.add(other)
    c_neighbors = set()
    for e in c_edges:
        other = e.target_id if e.source_id == candidate.id else e.source_id
        c_neighbors.add(other)

    shared = q_neighbors & c_neighbors
    if not q_neighbors and not c_neighbors:
        return 0.0
    # ratio of overlap
    overlap = len(shared) / max(1, min(len(q_neighbors), len(c_neighbors)))
    # email domain bonus
    q_domains = set(re.findall(r"@([\w\.-]+)", str(query_node.attributes)))
    c_domains = set(re.findall(r"@([\w\.-]+)", str(candidate.attributes)))
    domain_bonus = 0.15 if q_domains & c_domains else 0.0
    return overlap * 0.25 + domain_bonus

# ------------------------------------------------------------------
# Resolution driver
# ------------------------------------------------------------------

def resolve_entities(
    tlpg_store,
    merge_threshold: float = 0.82,
    same_as_threshold: float = 0.55,
    auto_merge: bool = True,
) -> List[ResolutionResult]:
    """
    Stage 3: sweep all nodes, block, filter, score, then merge or SAME_AS.
    Returns resolution actions taken.
    """
    nodes = tlpg_store.list_nodes()
    # buckets
    buckets: Dict[str, List[TLPGNode]] = defaultdict(list)
    for n in nodes:
        buckets[blocking_key(n)].append(n)

    results: List[ResolutionResult] = []
    already_merged: Set[str] = set()

    for bkey, bnodes in buckets.items():
        if len(bnodes) < 2:
            continue
        for i, q in enumerate(bnodes):
            if q.id in already_merged:
                continue
            cand_scored = vector_filter_candidates(bnodes, q, threshold=0.3)
            for cand, vscore in cand_scored:
                if cand.id in already_merged or cand.id == q.id:
                    continue

                # composite score
                jac = jaccard(q.canonical_name, cand.canonical_name)
                abbrev = 0.92 if is_abbrev(q.canonical_name, cand.canonical_name) or is_abbrev(cand.canonical_name, q.canonical_name) else 0.0
                topo = topological_boost(q, cand, tlpg_store)

                # weighted
                score = max(abbrev, 0.45*vscore + 0.35*jac + topo)
                # exact alias bonus
                shared_alias = set(a.lower() for a in q.aliases) & set(a.lower() for a in cand.aliases)
                if shared_alias:
                    score = min(0.96, score + 0.12)

                if score >= merge_threshold and auto_merge:
                    # High-confidence → merge under canonical
                    canonical = q if len(q.canonical_name) >= len(cand.canonical_name) else cand
                    merged = cand if canonical == q else q
                    # merge aliases and attrs
                    canonical.aliases = list(set(canonical.aliases + [merged.canonical_name] + merged.aliases + canonical.aliases))
                    # merge attributes shallow
                    for k, v in merged.attributes.items():
                        if k not in canonical.attributes:
                            canonical.attributes[k] = v
                    canonical.confidence = min(0.98, max(canonical.confidence, merged.confidence, score))
                    tlpg_store.upsert_node(canonical)
                    # rewire edges: move merged's edges to canonical (soft delete merged)
                    # For now we keep merged node but mark SAME_AS merged internally, then drop duplicate later
                    # We actually keep canonical and create a SAME_AS 1.0 then delete merged? Simplest: delete merged node file entry
                    # We'll delete by not rewriting it — we need direct file surgery, so do upsert canonical and filter out merged
                    # hack: read all, filter
                    all_nodes = tlpg_store.list_nodes()
                    all_nodes = [n for n in all_nodes if n.id not in (merged.id,)]
                    # ensure canonical present
                    if canonical.id not in [n.id for n in all_nodes]:
                        all_nodes.append(canonical)
                    # write back
                    tlpg_store._write(tlpg_store.nodes_file, [n.to_dict() for n in all_nodes])
                    already_merged.add(merged.id)

                    edge = TLPGEdge(source_id=merged.id, target_id=canonical.id, edge_type="SAME_AS", confidence=score, properties={"reason": f"merged {merged.canonical_name} -> {canonical.canonical_name}", "method": "auto_merge", "blocked_key": bkey}, source="resolution")
                    tlpg_store.add_edge(edge)

                    results.append(ResolutionResult(
                        canonical_id=canonical.id,
                        merged_ids=[merged.id],
                        same_as_edges=[edge],
                        confidence=round(score,3),
                        reason=f"{merged.canonical_name} ≈ {canonical.canonical_name} (jaccard {jac:.2f}, vec {vscore:.2f}, topo {topo:.2f}) → auto-merged",
                        method="deterministic_block+vector+topological",
                    ))
                elif score >= same_as_threshold:
                    # Lower confidence → SAME_AS edge, prompt agent later if high-stakes
                    edge = TLPGEdge(
                        source_id=q.id,
                        target_id=cand.id,
                        edge_type="SAME_AS",
                        confidence=round(score,3),
                        properties={
                            "reason": f"possible {q.canonical_name} ↔ {cand.canonical_name}",
                            "jaccard": jac,
                            "vec": vscore,
                            "topo": topo,
                            "blocked_key": bkey,
                        },
                        source="resolution",
                    )
                    tlpg_store.add_edge(edge)
                    results.append(ResolutionResult(
                        canonical_id=q.id,
                        merged_ids=[],
                        same_as_edges=[edge],
                        confidence=round(score,3),
                        reason=f"ambiguous {q.canonical_name} vs {cand.canonical_name} — keep both, link with SAME_AS {score:.2f}, ask agent if task is high-stakes",
                        method="probabilistic_link",
                    ))

    return results

def disambiguate_query(query: str, tlpg_store, top_k: int = 5) -> Dict:
    """
    Helper for agent when it hits ambiguous entity — returns SAME_AS cluster.
    """
    hits = tlpg_store.find_nodes_by_name(query) or tlpg_store.vector_search_nodes(query, top_k=top_k)
    clusters = []
    for h in hits:
        edges = tlpg_store.get_edges_for(h.id)
        same_as = [e for e in edges if e.edge_type == "SAME_AS"]
        clusters.append({"canonical": h.to_dict(), "same_as_edges": [e.to_dict() for e in same_as]})
    return {"query": query, "clusters": clusters}
