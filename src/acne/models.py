"""agentic-contacts — core models, humble and clear. v0.2 TLPG edition."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timezone
import uuid
import hashlib

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

# ---------------------------------------------------------------------
# Legacy cozy models (kept for backward compat)
# ---------------------------------------------------------------------
@dataclass
class Trigger:
    phrase: str  # "my designer", "the client call"
    maps_to_name: str
    confidence: float  # 0.2 heuristic → 0.95 real
    reason: str  # why we think so, plain words
    source: str = "manual"  # manual | calendar | memory_heuristic | enriched
    role: Optional[str] = None
    count: Optional[int] = None  # how many meetings
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self): return asdict(self)

@dataclass
class Enrichment:
    kind: str  # calendar | email | memory | manual
    detail: str
    confidence: float
    source: str
    at: str = field(default_factory=_now_iso)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self): return asdict(self)

@dataclass
class Contact:
    id: str = field(default_factory=lambda: "c_" + uuid.uuid4().hex[:8])
    name: str = ""
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    org: Optional[str] = None
    role: Optional[str] = None  # designer, client, etc.
    triggers: List[str] = field(default_factory=list)  # phrases that point here
    notes: Optional[str] = None
    last_seen: Optional[str] = None
    first_seen: str = field(default_factory=_now_iso)
    confidence: float = 0.6  # how sure we are this person is real
    source: str = "manual"
    enrichments: List[Enrichment] = field(default_factory=list)
    graph_edges: List[str] = field(default_factory=list)  # ids of related nodes
    extras: Dict[str, Any] = field(default_factory=dict)

    def primary_email(self) -> Optional[str]:
        return self.emails[0] if self.emails else None

    def to_dict(self):
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Contact":
        enrich = d.get("enrichments", [])
        clean = []
        for e in enrich:
            if isinstance(e, dict):
                clean.append(Enrichment(**e))
            else:
                clean.append(e)
        d = {**d, "enrichments": clean}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class ResolveResult:
    query: str
    contact: Optional[Contact]
    confidence: float
    why: str
    alternatives: List[Contact] = field(default_factory=list)
    trigger_matched: Optional[str] = None
    source: str = "resolver"

    def to_dict(self):
        return {
            "query": self.query,
            "contact": self.contact.to_dict() if self.contact else None,
            "confidence": self.confidence,
            "why": self.why,
            "trigger_matched": self.trigger_matched,
            "alternatives": [c.to_dict() for c in self.alternatives],
            "source": self.source,
        }

# ---------------------------------------------------------------------
# v0.2 TLPG models — typed graph for agentic harnesses
# ---------------------------------------------------------------------

NodeClass = Literal[
    "Person", "Organization", "Location", "Thing", "Citation", "Document", "Chunk",
    # --- constructs v0.4 — harness-aware ---
    "Construct", "Concept", "Project", "Goal", "Task",
    "Agent", "Workflow", "Skill", "Bundle", "Event"
]
EdgeType = Literal[
    "EMPLOYED_BY", "AUTHORED", "REFERENCES", "EXTRACTED_FROM",
    "SAME_AS", "PARTNER_WITH", "LOCATED_IN", "WORKS_ON", "BELONGS_TO",
    "MENTIONS", "CITES", "ATTENDED", "ORGANIZED_BY", "RELATED_TO",
    # --- constructs edges v0.4 ---
    "OWNS", "CREATED_BY", "USES", "DEPENDS_ON", "IMPLEMENTS",
    "PART_OF", "MANAGES", "EXECUTES", "TRACKS", "DEFINES",
    "REALIZES", "ABSTRACTS", "COMPOSED_OF"
]

@dataclass
class TLPGNode:
    """A typed node in the Temporal Labeled Property Graph."""

    id: str = field(default_factory=lambda: _new_id("n"))
    node_class: NodeClass = "Thing"
    canonical_name: str = ""
    # flexible attributes per taxonomy
    attributes: Dict[str, Any] = field(default_factory=dict)
    # temporal metadata
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    tx_time: str = field(default_factory=_now_iso)  # transaction time
    # provenance & confidence
    confidence: float = 0.7
    source: str = "extraction"  # extraction | manual | calendar | memory_heuristic | ingest
    source_artifact_id: Optional[str] = None
    # aliases & linking
    aliases: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None  # 384-d when available

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TLPGNode":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def display_name(self) -> str:
        return self.canonical_name or self.attributes.get("legal_name") or self.attributes.get("canonical_name") or self.id

    def checksum(self) -> str:
        # stable-ish hash for dedup checks
        h = hashlib.sha256(f"{self.node_class}:{self.canonical_name}:{sorted(self.aliases)}".encode()).hexdigest()[:8]
        return h

@dataclass
class TLPGEdge:
    """A temporal, typed edge between two nodes."""

    id: str = field(default_factory=lambda: _new_id("e"))
    source_id: str = ""  # from node id
    target_id: str = ""  # to node id
    edge_type: EdgeType = "RELATED_TO"
    # temporal validity (real-world time)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    tx_time: str = field(default_factory=_now_iso)
    confidence: float = 0.7
    properties: Dict[str, Any] = field(default_factory=dict)  # e.g. {date, doi, role, count}
    source: str = "extraction"
    provenance_chunk_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TLPGEdge":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class DocumentArtifact:
    """Source artifact node — provenance root for all extractions."""

    id: str = field(default_factory=lambda: _new_id("doc"))
    node_class: Literal["Document", "Citation"] = "Document"
    uri: str = ""  # file://, https://, gmail://, etc.
    title: str = ""
    author: Optional[str] = None
    publication_timestamp: Optional[str] = None
    checksum: Optional[str] = None
    mime_type: str = "text/plain"
    byte_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tx_time: str = field(default_factory=_now_iso)

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DocumentArtifact":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class TextChunk:
    """Overlapping context chunk from ingestion — bridges doc → entities."""

    id: str = field(default_factory=lambda: _new_id("chk"))
    document_id: str = ""
    text: str = ""
    token_count: int = 0
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    overlap_with_prev: int = 0
    embedding: Optional[List[float]] = None
    tx_time: str = field(default_factory=_now_iso)

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TextChunk":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class ExtractionResult:
    """Outcome of running schema-guided NER+RE on a chunk."""

    chunk_id: str
    document_id: str
    nodes: List[TLPGNode]
    edges: List[TLPGEdge]
    citations: List[str] = field(default_factory=list)  # raw citation strings found
    confidence_avg: float = 0.0
    model_used: str = "heuristic"

    def to_dict(self):
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "citations": self.citations,
            "confidence_avg": self.confidence_avg,
            "model_used": self.model_used,
        }

@dataclass
class ResolutionResult:
    """Outcome of entity resolution pass."""

    canonical_id: str
    merged_ids: List[str]
    same_as_edges: List[TLPGEdge]
    confidence: float
    reason: str  # plain words why merged or linked
    method: str  # deterministic_block | vector_filter | topological | human

    def to_dict(self):
        return {
            "canonical_id": self.canonical_id,
            "merged_ids": self.merged_ids,
            "same_as_edges": [e.to_dict() for e in self.same_as_edges],
            "confidence": self.confidence,
            "reason": self.reason,
            "method": self.method,
        }

# ---------------------------------------------------------------------
# Helpers for taxonomy defaults
# ---------------------------------------------------------------------
TAXONOMY_ATTRS: Dict[NodeClass, List[str]] = {
    "Person": ["canonical_name", "email_aliases", "role", "title", "aliases"],
    "Organization": ["legal_name", "domain", "industry", "org_type"],
    "Location": ["geo_coordinates", "time_zone", "address", "city", "country"],
    "Thing": ["identifier", "version", "status", "kind", "url"],
    "Citation": ["doi", "event_timestamp", "url", "venue", "authors"],
    "Document": ["uri", "author", "publication_timestamp", "checksum", "mime_type"],
    "Chunk": ["document_id", "chunk_index", "token_count"],
    # constructs v0.4
    "Construct": ["kind", "layer", "principle", "status", "version"],
    "Concept": ["domain", "abstraction_level", "source_nodes", "definition"],
    "Project": ["status", "repo", "tech_stack", "owner", "deadline"],
    "Goal": ["status", "metric", "deadline", "success_criteria", "owner"],
    "Task": ["status", "priority", "assignee", "due", "project"],
    "Agent": ["role", "layer", "model", "tools", "packs"],
    "Workflow": ["phases", "entry", "version", "owner"],
    "Skill": ["pack", "tools", "use_for", "layer"],
    "Bundle": ["agents", "packs", "workflows", "version"],
    "Event": ["timestamp", "type", "participants", "location", "outcome"],
}

def make_person(name: str, email: str = "", role: str = "", confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None) -> TLPGNode:
    attrs = {}
    if email: attrs["email_aliases"] = [email]
    if role: attrs["role"] = role
    return TLPGNode(node_class="Person", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_org(name: str, domain: str = "", industry: str = "", confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None) -> TLPGNode:
    attrs = {}
    if domain: attrs["domain"] = domain
    if industry: attrs["industry"] = industry
    attrs["legal_name"] = name
    return TLPGNode(node_class="Organization", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_construct(name: str, kind: str = "construct", layer: str = "", confidence: float = 0.72, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {"kind": kind}
    if layer: attrs["layer"] = layer
    attrs.update(extras)
    return TLPGNode(node_class="Construct", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_concept(name: str, domain: str = "", definition: str = "", confidence: float = 0.68, source: str = "extraction", source_artifact_id: str = None) -> TLPGNode:
    attrs = {}
    if domain: attrs["domain"] = domain
    if definition: attrs["definition"] = definition[:400]
    return TLPGNode(node_class="Concept", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_project(name: str, status: str = "active", confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {"status": status}
    attrs.update(extras)
    return TLPGNode(node_class="Project", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_goal(name: str, status: str = "active", confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {"status": status}
    attrs.update(extras)
    return TLPGNode(node_class="Goal", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_task(name: str, status: str = "open", confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {"status": status}
    attrs.update(extras)
    return TLPGNode(node_class="Task", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_agent_node(name: str, role: str = "", layer: int = 3, confidence: float = 0.75, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {"role": role, "layer": layer}
    attrs.update(extras)
    return TLPGNode(node_class="Agent", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_workflow_node(name: str, phases: int = 0, confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {}
    if phases: attrs["phases"] = phases
    attrs.update(extras)
    return TLPGNode(node_class="Workflow", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_skill_node(name: str, pack: str = "", confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {"pack": pack or name}
    attrs.update(extras)
    return TLPGNode(node_class="Skill", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_bundle_node(name: str, version: str = "", confidence: float = 0.7, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {}
    if version: attrs["version"] = version
    attrs.update(extras)
    return TLPGNode(node_class="Bundle", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_event_node(name: str, timestamp: str = None, confidence: float = 0.65, source: str = "extraction", source_artifact_id: str = None, **extras) -> TLPGNode:
    attrs = {}
    if timestamp: attrs["timestamp"] = timestamp
    attrs.update(extras)
    return TLPGNode(node_class="Event", canonical_name=name, attributes=attrs, confidence=confidence, source=source, source_artifact_id=source_artifact_id)

def make_edge(src: str, dst: str, edge_type: EdgeType, confidence: float = 0.7, valid_from: str = None, props: Dict[str, Any] = None) -> TLPGEdge:
    return TLPGEdge(source_id=src, target_id=dst, edge_type=edge_type, confidence=confidence, valid_from=valid_from, properties=props or {})
