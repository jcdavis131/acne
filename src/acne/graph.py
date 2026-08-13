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
            except:
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
    # Constructs v0.4 — Graphify helpers
    # ------------------------------------------------------------------
    def add_construct_node(self, name: str, kind: str = "Construct", confidence: float = 0.72, layer: str = "", **extras):
        """Convenience for adding a Construct/Concept node."""
        from .models import (
            make_construct, make_concept, make_project, make_goal, make_task,
            make_agent_node, make_workflow_node, make_skill_node, make_bundle_node, make_event_node
        )
        makers = {
            "Construct": lambda: make_construct(name, kind=extras.get("kind", "construct"), layer=layer, confidence=confidence, **extras),
            "Concept": lambda: make_concept(name, confidence=confidence, **extras),
            "Project": lambda: make_project(name, confidence=confidence, **extras),
            "Goal": lambda: make_goal(name, confidence=confidence, **extras),
            "Task": lambda: make_task(name, confidence=confidence, **extras),
            "Agent": lambda: make_agent_node(name, confidence=confidence, **extras),
            "Workflow": lambda: make_workflow_node(name, confidence=confidence, **extras),
            "Skill": lambda: make_skill_node(name, confidence=confidence, **extras),
            "Bundle": lambda: make_bundle_node(name, confidence=confidence, **extras),
            "Event": lambda: make_event_node(name, confidence=confidence, **extras),
        }
        maker = makers.get(kind)
        if maker:
            node = maker()
        else:
            node = make_construct(name, kind=kind, layer=layer, confidence=confidence, **extras)
        return self.upsert_node(node)

    def graphify_constructs(self, threshold: float = 0.6) -> Dict[str, Any]:
        """
        v0.4 Construct graphification:
          - Abstracts low-level entities into higher-level Concept/Construct nodes
          - Links Person--USES-->Skill, Agent--EXECUTES-->Workflow, Project--COMPOSED_OF-->Task, etc.
          - Creates COMPOSED_OF / REALIZES / ABSTRACTS edges

        Returns stats dict.
        """
        from .models import make_edge
        nodes = self.list_nodes()
        edges_created = []

        # bucket by class
        by_class: Dict[str, List] = {}
        for n in nodes:
            by_class.setdefault(n.node_class, []).append(n)

        # Heuristic 1: every Agent EXECUTES at most one Workflow if name overlap
        for agent in by_class.get("Agent", []):
            for wf in by_class.get("Workflow", []):
                if agent.canonical_name.lower() in wf.canonical_name.lower() or wf.canonical_name.lower() in agent.canonical_name.lower():
                    e = make_edge(agent.id, wf.id, "EXECUTES", confidence=0.72, props={"heuristic":"agent-workflow"})
                    self.add_edge(e); edges_created.append(e)

        # Heuristic 2: Project COMPOSED_OF Task
        for proj in by_class.get("Project", []):
            for task in by_class.get("Task", []):
                # simple co-location: if task mentions project or shared prefix
                if proj.canonical_name.lower()[:4] in task.canonical_name.lower():
                    e = make_edge(proj.id, task.id, "COMPOSED_OF", confidence=0.65)
                    self.add_edge(e); edges_created.append(e)

        # Heuristic 3: Person USES Skill / Tool -> link
        for person in by_class.get("Person", []):
            for skill in by_class.get("Skill", []):
                # if person node near skill node? For now link all high-conf manual persons to skills they mention
                e = make_edge(person.id, skill.id, "USES", confidence=0.58, props={"construct":"person-skill"})
                # only if not too many — limit to avoid spam
                if len(edges_created) < 200:
                    self.add_edge(e); edges_created.append(e)

        # Heuristic 4: Bundle PART_OF Workflow / OWNS Skill
        for bundle in by_class.get("Bundle", []):
            for skill in by_class.get("Skill", []):
                e = make_edge(bundle.id, skill.id, "OWNS", confidence=0.66)
                if len(edges_created) < 250:
                    self.add_edge(e); edges_created.append(e)

        # Heuristic 5: Abstract Construct nodes from co-occurring low-levels
        # If >2 nodes share same chunk provenance, create a Concept that ABSTRACTS them
        chunk_to_nodes: Dict[str, List] = {}
        for edge in self.list_edges(edge_type="EXTRACTED_FROM"):
            # edge source=node, target=chunk
            chunk_to_nodes.setdefault(edge.target_id, []).append(edge.source_id)

        for chunk_id, node_ids in chunk_to_nodes.items():
            if len(node_ids) >= 3:
                # make a Concept node for this chunk
                n_ids = node_ids[:5]
                concept_name = f"Concept from {chunk_id[:6]}"
                from .models import TLPGNode
                concept = TLPGNode(node_class="Concept", canonical_name=concept_name, attributes={"source_nodes": n_ids, "chunk_id": chunk_id, "abstraction_level":"chunk"}, confidence=0.62, source="construct_graphify")
                self.upsert_node(concept)
                for nid in n_ids:
                    e = make_edge(concept.id, nid, "ABSTRACTS", confidence=0.62, props={"chunk_id": chunk_id})
                    self.add_edge(e); edges_created.append(e)

        # Heuristic 6: Goal REALIZES Project (original)
        for goal in by_class.get("Goal", []):
            for proj in by_class.get("Project", []):
                e = make_edge(goal.id, proj.id, "REALIZES", confidence=0.6)
                self.add_edge(e); edges_created.append(e)
                break  # one per goal

        # --- v0.4.1 Goal Slip-Proof Extensions ---
        # Detect GOAL.md presence to force stronger linking even on name mismatch (link by project attr)
        from pathlib import Path as _Path
        goals_present_on_disk = []
        try:
            base_goals = _Path.home() / "workspace" / "goals"
            if base_goals.exists():
                for gm in base_goals.glob("*/GOAL.md"):
                    goals_present_on_disk.append(gm)
                for gm in base_goals.glob("*/*/GOAL.md"):
                    goals_present_on_disk.append(gm)
        except Exception:
            pass
        has_goal_md = len(goals_present_on_disk) > 0

        goals = by_class.get("Goal", [])
        projects = by_class.get("Project", [])
        tasks = by_class.get("Task", [])

        # If GOAL.md present, ensure success_criteria-ish goals still link
        # Re-bucket live edge lookups for idempotency
        existing_realizes = {(e.source_id, e.target_id) for e in self.list_edges(edge_type="REALIZES")}
        existing_tracks = {(e.source_id, e.target_id) for e in self.list_edges(edge_type="TRACKS")}
        existing_part_of = {(e.source_id, e.target_id) for e in self.list_edges(edge_type="PART_OF")}
        existing_composed = {(e.source_id, e.target_id) for e in self.list_edges(edge_type="COMPOSED_OF")}

        # Helper to find project match by attr
        def _proj_match(attr_val: str):
            if not attr_val:
                return None
            av = attr_val.lower().strip()
            for proj in projects:
                if av in proj.canonical_name.lower() or proj.canonical_name.lower() in av:
                    return proj
            return None

        # 6b: Task PART_OF Project via project attr, else fallback to first project
        for task in tasks:
            proj_attr = task.attributes.get("project") or task.attributes.get("project_id") or task.attributes.get("repo")
            if proj_attr:
                matched = _proj_match(str(proj_attr))
                if matched and (task.id, matched.id) not in existing_part_of:
                    e = make_edge(task.id, matched.id, "PART_OF", confidence=0.72, props={"via":"project_attr","goal_slip_proof":True})
                    self.add_edge(e); edges_created.append(e); existing_part_of.add((task.id, matched.id))

        # 6c: Goal REALIZES Project even when no name overlap (link by project attr or fallback)
        for goal in goals:
            # already has realizes?
            has_realizes = any(src == goal.id for src, _ in existing_realizes)
            if has_realizes and not has_goal_md:
                continue
            # try attr linking
            proj_attr = goal.attributes.get("project") or goal.attributes.get("repo") or goal.attributes.get("owner")
            matched = _proj_match(str(proj_attr)) if proj_attr else None
            if matched:
                if (goal.id, matched.id) not in existing_realizes:
                    # include success_criteria awareness in confidence boost
                    conf = 0.65
                    if goal.attributes.get("success_criteria") or has_goal_md:
                        conf = 0.68
                    e = make_edge(goal.id, matched.id, "REALIZES", confidence=conf, props={"via":"project_attr","goal_slip_proof":True})
                    self.add_edge(e); edges_created.append(e); existing_realizes.add((goal.id, matched.id))
                    continue
            # fallback: if projects exist and still no link, link to first project when GOAL.md present or success_criteria set
            if projects and (has_goal_md or goal.attributes.get("success_criteria") or goal.attributes.get("deadline")):
                first = projects[0]
                if (goal.id, first.id) not in existing_realizes:
                    e = make_edge(goal.id, first.id, "REALIZES", confidence=0.58, props={"via":"fallback_goal_md","goal_slip_proof":True})
                    self.add_edge(e); edges_created.append(e); existing_realizes.add((goal.id, first.id))

        # 6d: Goal TRACKS Task even when no name overlap (link by project attr)
        # Build task->project map for quick lookup
        task_to_proj = {}
        for e in self.list_edges(edge_type="PART_OF"):
            task_to_proj[e.source_id] = e.target_id
        for e in self.list_edges(edge_type="COMPOSED_OF"):
            # Project -> Task opposite direction
            task_to_proj[e.target_id] = e.source_id

        for goal in goals:
            # goal's project target(s)
            goal_projects = [tgt for src,tgt in existing_realizes if src == goal.id]
            for task in tasks:
                if (goal.id, task.id) in existing_tracks:
                    continue
                # link conditions:
                # 1) task's project attr matches goal's project attr
                t_proj_attr = task.attributes.get("project") or ""
                g_proj_attr = goal.attributes.get("project") or ""
                if t_proj_attr and g_proj_attr and t_proj_attr.lower() == g_proj_attr.lower():
                    e = make_edge(goal.id, task.id, "TRACKS", confidence=0.70, props={"via":"project_attr_match","goal_slip_proof":True})
                    self.add_edge(e); edges_created.append(e); existing_tracks.add((goal.id, task.id))
                    continue
                # 2) task's project id overlaps goal's project id
                if task.id in task_to_proj and task_to_proj[task.id] in goal_projects:
                    e = make_edge(goal.id, task.id, "TRACKS", confidence=0.66, props={"via":"shared_project","goal_slip_proof":True})
                    self.add_edge(e); edges_created.append(e); existing_tracks.add((goal.id, task.id))
                    continue
                # 3) if GOAL.md present, be generous: link any task to goal if still <3 tasks per goal
                if has_goal_md:
                    current_tracks = len([s for s,t in existing_tracks if s == goal.id])
                    if current_tracks < 3:
                        # avoid linking all blindly if many tasks — cap 3
                        e = make_edge(goal.id, task.id, "TRACKS", confidence=0.55, props={"via":"goal_md_generous","goal_slip_proof":True})
                        self.add_edge(e); edges_created.append(e); existing_tracks.add((goal.id, task.id))

        # 6e: If Goal has no Tasks linked -> placeholder Task "Need tasks for <goal>"
        from .models import TLPGNode as _Node
        for goal in goals:
            tracks_to_tasks = []
            for src,tgt in existing_tracks:
                if src == goal.id:
                    # check target is Task (or will be)
                    # we need to know node class; use live list
                    tn = next((n for n in self.list_nodes(node_class="Task") if n.id == tgt), None)
                    if tn is None:
                        # maybe placeholder already created earlier in this loop but not in list cache? Check all nodes
                        tn = self.get_node(tgt)
                        if tn and tn.node_class != "Task":
                            continue
                    # skip placeholder from counting as real?
                    if tn and tn.attributes.get("placeholder"):
                        continue
                    tracks_to_tasks.append(tgt)
            if len(tracks_to_tasks) == 0:
                placeholder_name = f"Need tasks for {goal.canonical_name}"
                # avoid duplicate placeholder
                existing_placeholder = None
                for n in self.list_nodes(node_class="Task"):
                    if n.canonical_name == placeholder_name:
                        existing_placeholder = n
                        break
                    if n.attributes.get("for_goal") == goal.id and n.attributes.get("needs_tasks"):
                        existing_placeholder = n
                        break
                if existing_placeholder is None:
                    ph_attrs = {
                        "needs_tasks": True,
                        "placeholder": True,
                        "for_goal": goal.id,
                        "status": "open",
                        "priority": "high",
                        "goal_name": goal.canonical_name,
                    }
                    placeholder = _Node(
                        node_class="Task",
                        canonical_name=placeholder_name,
                        attributes=ph_attrs,
                        confidence=0.45,
                        source="goal_health",
                    )
                    self.upsert_node(placeholder)
                    existing_placeholder = placeholder
                    # refresh by_class locally if needed
                # ensure TRACKS edge exists
                if (goal.id, existing_placeholder.id) not in existing_tracks:
                    e = make_edge(goal.id, existing_placeholder.id, "TRACKS", confidence=0.45, props={"placeholder": True, "needs_tasks": True, "goal_slip_proof": True})
                    self.add_edge(e); edges_created.append(e); existing_tracks.add((goal.id, existing_placeholder.id))

        # also ensure Project COMPOSED_OF Task edges where missing (reverse of PART_OF)
        for proj in projects:
            for task in tasks:
                # if task PART_OF proj exists, mirror COMPOSED_OF if missing
                if (task.id, proj.id) in existing_part_of and (proj.id, task.id) not in existing_composed:
                    e = make_edge(proj.id, task.id, "COMPOSED_OF", confidence=0.66, props={"mirror":"PART_OF","goal_slip_proof":True})
                    self.add_edge(e); edges_created.append(e); existing_composed.add((proj.id, task.id))

        return {"constructs_created": len([n for n in self.list_nodes() if n.node_class in ("Construct","Concept","Project","Goal","Task","Agent","Workflow","Skill","Bundle","Event")]), "edges_created": len(edges_created), "by_class": {k: len(v) for k,v in by_class.items()}, "goal_md_found": len(goals_present_on_disk)}

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
        all_nodes = self.list_nodes()
        by_class = {}
        for cls in ["Person", "Organization", "Location", "Thing", "Citation", "Document",
                    "Construct", "Concept", "Project", "Goal", "Task", "Agent", "Workflow", "Skill", "Bundle", "Event", "Chunk"]:
            cnt = len([n for n in all_nodes if n.node_class == cls])
            if cnt:
                by_class[cls] = cnt
        return {
            "base": str(self.base),
            "nodes": len(all_nodes),
            "edges": len(self.list_edges()),
            "documents": len(self.list_documents()),
            "chunks": len(self.list_chunks()),
            "by_class": by_class,
        }
