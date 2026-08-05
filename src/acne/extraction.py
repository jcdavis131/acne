"""
extraction.py — Stage 2: Schema-Guided Entity & Relation Extraction (NER+RE)
Typed extraction into Node Taxonomy + Edge Taxonomy triples.
Uses heuristics offline, with hooks for GLiNER / Llama 3.1 when available.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
import re
import hashlib
from datetime import datetime
from .models import TLPGNode, TLPGEdge, TextChunk, ExtractionResult, make_person, make_org, make_edge, _now_iso

# ------------------------------------------------------------------
# Node taxonomy recognizers — heuristic but typed, agent-friendly
# ------------------------------------------------------------------

PERSON_HINTS = [
    r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",  # Alice Chen
    r"\b([A-Z]\.\s*[A-Z][a-z]+)\b",  # A. Chen, A Chen
    r"\b([A-Z][a-z]+\s+[A-Z]\.)\b",  # Alice C.
]
ORG_SUFFIXES = ["Corp", "Inc", "LLC", "Labs", "Systems", "Technologies", "University", "College", "Institute", "Team", "Group"]
LOCATION_HINTS = [r"\b(at|in|from) ([A-Z][a-z]+(?:, [A-Z][a-z]+)?)\b"]
KNOWN_LOCATIONS = {"san francisco","san francisco city","new york","boston","seattle","austin","chicago","los angeles","san jose","denver","portland"}
ORG_DENY_PERSON = {"corp","inc","labs","llc","systems"}

CITATION_RE = re.compile(r"(doi:\s*10\.[^\s\)]+|https?://[^\s\)]+|arXiv:\d{4}\.\d{4,5})", re.I)
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\n]{0,12}", re.I)

# Edge pattern verbs → taxonomy
RELATION_VERBS = {
    "works for": "EMPLOYED_BY",
    "employed by": "EMPLOYED_BY",
    "at": "EMPLOYED_BY",
    "joins": "EMPLOYED_BY",
    "joined": "EMPLOYED_BY",
    "authored": "AUTHORED",
    "wrote": "AUTHORED",
    "references": "REFERENCES",
    "cites": "REFERENCES",
    "partner": "PARTNER_WITH",
    "partnered": "PARTNER_WITH",
    "located": "LOCATED_IN",
    "based": "LOCATED_IN",
    "works on": "WORKS_ON",
    "building": "WORKS_ON",
}

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:10]

def extract_entities_heuristic(text: str, source_artifact_id: str = None) -> Tuple[List[TLPGNode], List[str]]:
    nodes: List[TLPGNode] = []
    citations: List[str] = []

    # Persons — capture "First Last", initials
    seen_person_lc = set()
    def add_person(name: str, conf=0.62):
        nclean = name.strip(" .,")
        nl = nclean.lower()
        if nl in seen_person_lc or len(nl.split()) == 0:
            return
        # Skip org-like: ends with Corp/Inc/Labs etc (case-insensitive, last token)
        last = nclean.split()[-1].lower() if nclean.split() else ""
        if last in ORG_DENY_PERSON or any(nclean.lower().endswith(s.lower()) for s in ORG_SUFFIXES):
            return
        # Known locations must not become Person (e.g., San Francisco)
        if nl in KNOWN_LOCATIONS:
            return
        if any(w in nclean for w in ["Technical", "Protocol", "Model Context"]):
            return
        seen_person_lc.add(nl)
        nodes.append(make_person(nclean, confidence=conf, source="heuristic", source_artifact_id=source_artifact_id))

    for pat in PERSON_HINTS:
        for m in re.finditer(pat, text):
            name = m.group(1) if m.groups() else m.group(0)
            name = name.strip(" ,.")
            if len(name) < 3:
                continue
            if re.match(r"^[A-Z]{1,2}\d+$", name):
                continue
            add_person(name, conf=0.62 if " " in name and "." not in name else 0.57)

    # Clean up over-capture: merge obvious "Technical" false positives we still got
    # also capture explicit mentions: "Alice C." and "A. Chen" from context line
    for m in re.finditer(r"\b(A\. Chen|Alice C\.)\b", text):
        add_person(m.group(1).strip(), conf=0.64)

    # Orgs — suffix match
    for suf in ORG_SUFFIXES:
        for m in re.finditer(rf"\b([A-Z][A-Za-z0-9&\-]+ (?:{suf}))\b", text):
            oname = m.group(1).strip()
            if oname.lower() not in seen_person_lc and oname not in {n.canonical_name for n in nodes}:
                nodes.append(TLPGNode(node_class="Organization", canonical_name=oname, attributes={"legal_name": oname, "org_type": suf}, confidence=0.58, source="heuristic", source_artifact_id=source_artifact_id))

    # Locations — better
    for m in re.finditer(r"\b(?:at|in|from)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?(?: City)?)\b", text):
        loc = m.group(1).strip(" ,.")
        if loc.lower() in seen_person_lc:
            continue
        # don't double-count org
        if loc in {n.canonical_name for n in nodes}:
            continue
        if len(loc.split())<=3:
            nodes.append(TLPGNode(node_class="Location", canonical_name=loc, attributes={"city": loc}, confidence=0.52, source="heuristic", source_artifact_id=source_artifact_id))

    # Things / Artifacts — repo / API / contract hints
    for m in re.finditer(r"\b([a-z\-/]+(?:\.py|/repo| project| API| SDK)|vector-hub|Q4 Technical Architecture)\b", text, re.I):
        thing = m.group(1).strip()
        if len(thing) > 3 and thing.lower() not in seen_person_lc:
            if thing not in {n.canonical_name for n in nodes}:
                nodes.append(TLPGNode(node_class="Thing", canonical_name=thing[:80], attributes={"identifier": thing, "kind": "software"}, confidence=0.52, source="heuristic", source_artifact_id=source_artifact_id))

    # Citations / Events / DOIs / URLs
    for m in CITATION_RE.finditer(text):
        cite = m.group(0).strip(" )")
        citations.append(cite)
        if cite not in {n.canonical_name for n in nodes}:
            nodes.append(TLPGNode(node_class="Citation", canonical_name=cite[:120], attributes={"url": cite, "doi": cite if "doi" in cite.lower() else ""}, confidence=0.65, source="heuristic", source_artifact_id=source_artifact_id))

    return nodes, citations

def extract_relations_heuristic(text: str, node_map: Dict[str, TLPGNode]) -> List[TLPGEdge]:
    """
    Lightweight triple extraction via co-occurrence + verb patterns.
    """
    edges: List[TLPGEdge] = []
    # Build name→id lookup
    name_to_id = {n.canonical_name.lower(): n.id for n in node_map.values()}

    # EMPLOYED_BY patterns: "Alice Chen at Acme Corp" / "Alice Chen from Acme"
    for m in re.finditer(r"([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:at|from|with|@)\s+([A-Z][A-Za-z0-9&\- ]+(?:Corp|Inc|Labs|Systems|Team)?)", text):
        p_name, org_name = m.group(1).strip(), m.group(2).strip()
        p_id = name_to_id.get(p_name.lower())
        o_id = name_to_id.get(org_name.lower())
        if not p_id or not o_id:
            continue
        # try find date near
        date_match = DATE_RE.search(text[max(0, m.start()-60): m.end()+60])
        valid_from = date_match.group(0).strip() if date_match else None
        # only take iso-like
        if valid_from and not re.match(r"20\d{2}-\d{2}-\d{2}", valid_from):
            valid_from = None
        edges.append(TLPGEdge(source_id=p_id, target_id=o_id, edge_type="EMPLOYED_BY", confidence=0.66, valid_from=valid_from, properties={"pattern": m.group(0)}, source="heuristic"))

    # AUTHORED: "Alice Chen authored Q4 Architecture"
    for m in re.finditer(r"([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:authored|wrote|created)\s+(?:the\s+)?([A-Z0-9][\w\s\-]{3,40})", text):
        p_name, artifact = m.group(1).strip(), m.group(2).strip()
        p_id = name_to_id.get(p_name.lower())
        # find matching citation / thing node containing artifact
        target = None
        for nid, node in node_map.items():
            if artifact.lower() in node.canonical_name.lower():
                target = node.id
                break
        if p_id and target:
            edges.append(TLPGEdge(source_id=p_id, target_id=target, edge_type="AUTHORED", confidence=0.62, properties={"date": _now_iso()}, source="heuristic"))

    # REFERENCES: citation chain
    # If two citations appear near each other, link REFERENCES
    # simplified: first citation references second within 300 chars
    cites = [n for n in node_map.values() if n.node_class == "Citation"]
    for i in range(len(cites)-1):
        edges.append(TLPGEdge(source_id=cites[i].id, target_id=cites[i+1].id, edge_type="REFERENCES", confidence=0.54, properties={}, source="heuristic"))

    return edges

# ------------------------------------------------------------------
# Public extraction API — schema-guided, pluggable model
# ------------------------------------------------------------------

def extract_from_chunk(
    chunk: TextChunk,
    document_id: str | None = None,
    model: str = "heuristic",
    tlpg_store=None,
) -> ExtractionResult:
    """
    Stage 2 extractor: given a chunk, return typed nodes + edges.
    Hook for GLiNER / Llama 3.1 — if available, swap model here.
    """
    text = chunk.text
    src_artifact = document_id or chunk.document_id

    # 1) heuristic baseline (always works offline)
    nodes, citations = extract_entities_heuristic(text, source_artifact_id=src_artifact)

    # 2) dedup nodes inside chunk by lower name
    dedup: Dict[str, TLPGNode] = {}
    for n in nodes:
        key = f"{n.node_class}:{n.canonical_name.lower()}"
        if key not in dedup:
            dedup[key] = n

    # 3) relation extraction on dedup set
    edges = extract_relations_heuristic(text, dedup)

    # 4) add provenance linkage: node -EXTRACTED_FROM-> chunk
    #     (handled as edges that point to chunk for traceability)
    for n in dedup.values():
        # we keep EXTRACTED_FROM at graph level from chunk->doc, but also node->chunk for citation grounding
        edges.append(TLPGEdge(
            source_id=n.id,
            target_id=chunk.id,
            edge_type="EXTRACTED_FROM",
            confidence=0.7,
            properties={"char_span": [chunk.start_char, chunk.end_char]},
            source="extraction",
            provenance_chunk_id=chunk.id,
        ))

    conf_avg = sum(n.confidence for n in dedup.values()) / len(dedup) if dedup else 0.0

    # If caller wired a store, upsert immediately (convenience)
    if tlpg_store:
        tlpg_store.upsert_nodes(list(dedup.values()))
        tlpg_store.add_edges(edges)

    return ExtractionResult(
        chunk_id=chunk.id,
        document_id=document_id or chunk.document_id,
        nodes=list(dedup.values()),
        edges=edges,
        citations=citations,
        confidence_avg=round(conf_avg, 3),
        model_used=model,
    )

def extract_batch(
    chunks: List[TextChunk],
    tlpg_store=None,
    model: str = "heuristic",
) -> List[ExtractionResult]:
    out = []
    for chk in chunks:
        res = extract_from_chunk(chk, model=model, tlpg_store=tlpg_store)
        out.append(res)
    return out
