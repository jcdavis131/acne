"""
graph.py — Temporal Labeled Property Graph for agentic-contacts
Stores TLPG nodes, edges, documents, chunks on disk as JSONL, no cloud.
GraphRAG hybrid: dense vector seed + multi-hop traversal.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional, Any, Set
import json
import hashlib
from .models import TLPGNode, TLPGEdge, DocumentArtifact, TextChunk, _now_iso

class TLPGStore:
    """
    Local-first TLPG, sits alongside ContactsStore.
    Files:
      nodes.jsonl      — typed entities
      edges.jsonl      — relationships with temporal validity
      documents.jsonl  — source artifacts
      chunks.jsonl     — provenance chunks
    """

    def __init__(self, base: Path):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.nodes_file = self.base / "nodes.jsonl"
        self.edges_file = self.base / "edges.jsonl"
        self.docs_file = self.base / "documents.jsonl"
        self.chunks_file = self.base / "chunks.jsonl"

    # ---- generic JSONL helpers ----
    def _read(self, p: Path) -> List[Dict]:
        if not p.exists():
            return []
        out = []
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _write(self, p: Path, items: List[Dict]):
        p.write_text("\n".join(json.dumps(x) for x in items) + "\n" if items else "")

    def _append(self, p: Path, obj: Dict):
        with p.open("a") as f:
            f.write(json.dumps(obj) + "\n")

    # ---- documents ----
    def save_document(self, doc: DocumentArtifact) -> DocumentArtifact:
        docs = [DocumentArtifact.from_dict(d) for d in self._read(self.docs_file)]
        docs = [d for d in docs if d.id != doc.id and d.uri != doc.uri]
        docs.append(doc)
        self._write(self.docs_file, [d.to_dict() for d in docs])
        return doc

    def list_documents(self) -> List[DocumentArtifact]:
        return [DocumentArtifact.from_dict(d) for d in self._read(self.docs_file)]

    def get_document(self, doc_id: str) -> Optional[DocumentArtifact]:
        for d in self.list_documents():
            if d.id == doc_id or d.uri == doc_id:
                return d
        return None

    # ---- chunks ----
    def save_chunk(self, chk: TextChunk) -> TextChunk:
        self._append(self.chunks_file, chk.to_dict())
        return chk

    def save_chunks(self, chunks: List[TextChunk]):
        for c in chunks:
            self._append(self.chunks_file, c.to_dict())
        return chunks

    def list_chunks(self, document_id: str = None) -> List[TextChunk]:
        all_chunks = [TextChunk.from_dict(d) for d in self._read(self.chunks_file)]
        if document_id:
            return [c for c in all_chunks if c.document_id == document_id]
        return all_chunks

    # ---- nodes ----
    def list_nodes(self, node_class: str = None) -> List[TLPGNode]:
        nodes = [TLPGNode.from_dict(d) for d in self._read(self.nodes_file)]
        if node_class:
            return [n for n in nodes if n.node_class == node_class]
        return nodes

    def get_node(self, node_id: str) -> Optional[TLPGNode]:
        for n in self.list_nodes():
            if n.id == node_id or n.canonical_name.lower() == node_id.lower():
                return n
        return None

    def find_nodes_by_name(self, name: str) -> List[TLPGNode]:
        name_l = name.lower().strip()
        out = []
        for n in self.list_nodes():
            if name_l == n.canonical_name.lower():
                out.append(n)
            elif name_l in [a.lower() for a in n.aliases]:
                out.append(n)
        return out

    def upsert_node(self, node: TLPGNode) -> TLPGNode:
        nodes = self.list_nodes()
        # dedup by id first, then by canonical + class low-conf handling done in resolution
        nodes = [n for n in nodes if n.id != node.id]
        nodes.append(node)
        self._write(self.nodes_file, [n.to_dict() for n in nodes])
        return node

    def upsert_nodes(self, nodes_to_save: List[TLPGNode]):
        for n in nodes_to_save:
            self.upsert_node(n)

    # ---- edges ----
    def list_edges(self, edge_type: str = None) -> List[TLPGEdge]:
        edges = [TLPGEdge.from_dict(d) for d in self._read(self.edges_file)]
        if edge_type:
            return [e for e in edges if e.edge_type == edge_type]
        return edges

    def get_edges_for(self, node_id: str) -> List[TLPGEdge]:
        return [e for e in self.list_edges() if e.source_id == node_id or e.target_id == node_id]

    def add_edge(self, edge: TLPGEdge) -> TLPGEdge:
        # avoid exact dup source/type/target
        edges = self.list_edges()
        for ex in edges:
            if ex.source_id == edge.source_id and ex.target_id == edge.target_id and ex.edge_type == edge.edge_type:
                # update confidence if higher
                if edge.confidence > ex.confidence:
                    edges.remove(ex)
                    break
                else:
                    return ex
        edges.append(edge)
        self._write(self.edges_file, [e.to_dict() for e in edges])
        return edge

    def add_edges(self, edges: List[TLPGEdge]):
        for e in edges:
            self.add_edge(e)
        return edges

    # ---- graph ops ----
    def neighbors(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        """BFS neighborhood up to depth, returns nodes and edges."""
        visited: Set[str] = set([node_id])
        frontier = [node_id]
        found_edges: List[TLPGEdge] = []
        found_nodes: List[TLPGNode] = []

        for _ in range(depth):
            next_frontier = []
            for nid in frontier:
                for e in self.get_edges_for(nid):
                    found_edges.append(e)
                    other = e.target_id if e.source_id == nid else e.source_id
                    if other not in visited:
                        visited.add(other)
                        next_frontier.append(other)
                        node = self.get_node(other)
                        if node:
                            found_nodes.append(node)
            frontier = next_frontier
            if not frontier:
                break

        return {"nodes": found_nodes, "edges": found_edges, "visited": list(visited)}

    # ------------------------------------------------------------------
    # GraphRAG — hybrid search
    # ------------------------------------------------------------------
    def _simple_embedding(self, text: str, dim: int = 32, _cache: Any = None) -> List[float]:
        """Cheap hash embed, stands in when ONNX blocked. Deterministic, with optional TokenCache."""
        if _cache:
            hit = _cache.get_emb(text[:400])
            if hit:
                return hit
        h = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(dim):
            vec.append(((h[i % len(h)] / 255.0) * 2) - 1)
        if _cache:
            _cache.put_emb(text[:400], vec)
        return vec

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x*y for x, y in zip(a, b))
        mag_a = (sum(x*x for x in a)) ** 0.5
        mag_b = (sum(x*x for x in b)) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def vector_search_nodes(self, query: str, top_k: int = 5, node_class: str = None, _cache: Any = None) -> List[TLPGNode]:
        q_emb = self._simple_embedding(query, _cache=_cache)
        scored = []
        for node in self.list_nodes(node_class):
            # lazy embed if missing
            if not node.embedding:
                txt = f"{node.canonical_name} {' '.join(node.aliases)} {node.attributes}"
                node.embedding = self._simple_embedding(txt, _cache=_cache)
            # small boost for name exact
            bonus = 0.15 if query.lower() in node.canonical_name.lower() else 0.0
            score = self._cosine(q_emb, node.embedding) + bonus
            scored.append((score, node))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored[:top_k]]

    def graphrag_query(self, query: str, hops: int = 2, top_k: int = 5, _cache: Any = None) -> Dict[str, Any]:
        """
        Hybrid GraphRAG:
          1) dense vector search for seed nodes
          2) multi-hop traversal to pull context
          3) verifiable payload with provenance chunks
        """
        if _cache:
            hit = _cache.get_query(query, hops, top_k)
            if hit:
                return hit
        seeds = self.vector_search_nodes(query, top_k=top_k, _cache=_cache)
        all_nodes = {s.id: s for s in seeds}
        all_edges: List[TLPGEdge] = []
        provenance_chunks: List[TextChunk] = []

        for seed in seeds:
            nb = self.neighbors(seed.id, depth=hops)
            for n in nb["nodes"]:
                all_nodes[n.id] = n
            all_edges.extend(nb["edges"])

        # dedup edges
        uniq_edges = {}
        for e in all_edges:
            uniq_edges[e.id] = e

        # gather provenance: edges with EXTRACTED_FROM point to chunks
        chunk_ids = set()
        for e in uniq_edges.values():
            if e.provenance_chunk_id:
                chunk_ids.add(e.provenance_chunk_id)
        if chunk_ids:
            all_chunks = self.list_chunks()
            provenance_chunks = [c for c in all_chunks if c.id in chunk_ids]

        result = {
            "query": query,
            "seeds": [s.to_dict() for s in seeds],
            "nodes": [n.to_dict() for n in all_nodes.values()],
            "edges": [e.to_dict() for e in uniq_edges.values()],
            "provenance_chunks": [c.to_dict() for c in provenance_chunks[:10]],
            "hops": hops,
            "cached": False,
        }
        if _cache:
            _cache.put_query(query, hops, top_k, result)
        return result

    def stats(self) -> Dict[str, Any]:
        return {
            "base": str(self.base),
            "nodes": len(self.list_nodes()),
            "edges": len(self.list_edges()),
            "documents": len(self.list_documents()),
            "chunks": len(self.list_chunks()),
            "by_class": {cls: len(self.list_nodes(cls)) for cls in ["Person", "Organization", "Location", "Thing", "Citation", "Document"]},
        }
