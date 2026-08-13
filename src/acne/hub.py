"""Hub — the cozy front door agents love. v0.2 TLPG + Token Cache 💰"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict, Any
from .store import ContactsStore
from .graph import TLPGStore
from .cache import TokenCache
from .resolver import ContactsResolver
from .models import Contact, Trigger, Enrichment
from . import enrichment as enrich_mod
from . import ingestion as ing_mod
from . import extraction as ext_mod
from . import resolution as res_mod

class ContactsHub:
    """Local-first contacts hub with TLPG and money-saving cache."""

    def __init__(self, base: Optional[Path | str] = None, workspace: Optional[Path | str]=None, price_per_1k: float = 0.015):
        if base:
            b = Path(base)
            store = ContactsStore(b)
            tlpg = TLPGStore(b)
            cache = TokenCache(b, price_per_1k=price_per_1k)
        elif workspace:
            ws = Path(workspace).expanduser()
            contacts_path = ws / "bundles" / "memory" / "contacts_harness"
            store = ContactsStore(contacts_path)
            tlpg = TLPGStore(contacts_path)
            cache = TokenCache(contacts_path, price_per_1k=price_per_1k)
        else:
            store = ContactsStore()
            tlpg = TLPGStore(store.base)
            cache = TokenCache(store.base, price_per_1k=price_per_1k)
        self.store = store
        self.tlpg = tlpg
        self.cache = cache
        self.resolver = ContactsResolver(store)

    # ---------------- legacy contact helpers ----------------
    def add_contact(self, name: str, email: str = "", role: str = "", org: str = "", trigger: str = "", notes: str = "") -> Contact:
        existing = self.store.get_by_name(name)
        c = existing or Contact(name=name)
        if email and email not in c.emails:
            c.emails.append(email)
        if role: c.role = role
        if org: c.org = org
        if notes: c.notes = notes
        if trigger and trigger not in c.triggers:
            c.triggers.append(trigger)
        if trigger:
            self.store.add_trigger(Trigger(phrase=trigger, maps_to_name=c.name, confidence=0.88, reason=f"you said {trigger} means {c.name}", source="manual", role=role))
        return self.store.save_contact(c)

    def add_trigger(self, phrase: str, maps_to: str, confidence: float = 0.7, reason: str = "", role: str = "", source: str="manual"):
        t = Trigger(phrase=phrase, maps_to_name=maps_to, confidence=confidence, reason=reason or f"maps {phrase} to {maps_to}", source=source, role=role)
        self.store.add_trigger(t)
        c = self.store.get_by_name(maps_to)
        if c and phrase not in c.triggers:
            c.triggers.append(phrase)
            self.store.save_contact(c)
        return t

    def resolve(self, query: str, context: Optional[Dict]=None):
        return self.resolver.resolve(query, context)

    def list_contacts(self) -> List[Contact]:
        return self.store.list_contacts()

    def enrich_from_memory(self, text: str = "", days: int = 30) -> List[Dict]:
        if not text:
            p = Path.home() / "MEMORY.md"
            if p.exists():
                text = p.read_text()[:20000]
        cands = enrich_mod.enrich_from_memory(text)
        for cand in cands[:8]:
            name = cand["name"]
            if not self.store.get_by_name(name):
                self.store.add_trigger(Trigger(phrase=name.lower(), maps_to_name=name, confidence=cand["confidence"], reason=cand["reason"], source="memory_heuristic"))
        return cands

    def enrich_from_calendar(self, events: List[Dict]) -> List[Dict]:
        cands = enrich_mod.enrich_from_calendar_events(events)
        for cand in cands:
            n = cand["name"]
            if not self.store.get_by_name(n):
                self.store.add_trigger(Trigger(phrase=n.lower(), maps_to_name=n, confidence=cand["confidence"], reason=cand["reason"], source="calendar", count=cand["count"]))
        return cands

    # ---------------- TLPG 4-stage pipeline with caching ----------------

    def ingest(self, source: str | Path, title: str = "", author: str = None, uri: str = None, meta: Dict[str, Any] = None) -> Dict[str, Any]:
        import hashlib
        raw = ""
        src_str = str(source)
        is_path = False
        if len(src_str) < 900:
            try:
                if Path(src_str).exists():
                    is_path = True
            except OSError:
                is_path = False
        if not is_path:
            if isinstance(source, str):
                raw = source
        if raw:
            chksum = hashlib.sha256(raw.encode()).hexdigest()[:16]
            hit = self.cache.get_doc_for_checksum(chksum)
            if hit:
                doc = self.tlpg.get_document(hit)
                if doc:
                    chunks = self.tlpg.list_chunks(document_id=doc.id)
                    return {"document": doc, "raw_text_len": len(raw), "chunks": chunks, "chunk_count": len(chunks), "cached": True, "provenance_edges": []}
        res = ing_mod.ingest_feed(source, self.tlpg, title=title, author=author, uri=uri, meta=meta)
        try:
            if res["document"].checksum:
                self.cache.put_doc(res["document"].checksum, res["document"].id)
        except: pass
        return res

    def extract(self, document_id: str = None, model: str = "heuristic", use_cache: bool = True) -> List[Dict]:
        """Stage 2 with extraction cache — avoids re-running NER on same chunk."""
        if document_id:
            chunks = self.tlpg.list_chunks(document_id=document_id)
        else:
            chunks = self.tlpg.list_chunks()[-50:]
        results = []
        for chk in chunks:
            if use_cache:
                hit = self.cache.get_extraction(chk.text)
                if hit:
                    results.append(hit["result"])
                    continue
            r = ext_mod.extract_from_chunk(chk, model=model, tlpg_store=self.tlpg)
            d = r.to_dict()
            self.cache.put_extraction(chk.text, {"result": d})
            results.append(d)
        return results

    def resolve_entities(self, merge_threshold: float = 0.82, same_as_threshold: float = 0.55) -> List[Dict]:
        return [r.to_dict() for r in res_mod.resolve_entities(self.tlpg, merge_threshold=merge_threshold, same_as_threshold=same_as_threshold)]

    def graphrag(self, query: str, hops: int = 2, top_k: int = 5, compressed: bool = False, budget_tokens: int = 600) -> Dict[str, Any]:
        """Stage 4 — cheap when cached, even cheaper compressed."""
        res = self.tlpg.graphrag_query(query, hops=hops, top_k=top_k, _cache=self.cache)
        if compressed:
            return self.cache.compress_graphrag(res, budget_tokens=budget_tokens)
        return res

    def mutate_relationship_edge(self, source_id: str, target_id: str, edge_type: str, confidence: float = 0.7, valid_from: str = None, properties: Dict[str, Any] = None) -> Dict[str, Any]:
        from .models import TLPGEdge
        allowed = {"EMPLOYED_BY","AUTHORED","REFERENCES","EXTRACTED_FROM","SAME_AS","PARTNER_WITH","LOCATED_IN","WORKS_ON","BELONGS_TO","MENTIONS","CITES","ATTENDED","ORGANIZED_BY","RELATED_TO",
                   # constructs v0.4
                   "OWNS","CREATED_BY","USES","DEPENDS_ON","IMPLEMENTS","PART_OF","MANAGES","EXECUTES","TRACKS","DEFINES","REALIZES","ABSTRACTS","COMPOSED_OF"}
        if edge_type not in allowed:
            raise ValueError(f"edge_type {edge_type!r} not in {sorted(allowed)}")
        edge = TLPGEdge(source_id=source_id, target_id=target_id, edge_type=edge_type, confidence=confidence, valid_from=valid_from, properties=properties or {}, source="mcp")
        saved = self.tlpg.add_edge(edge)
        # append-only audit log for rogue-agent tracing (Phase 3 minimal)
        try:
            from datetime import datetime, timezone
            import json
            audit_path = self.store.base / "audit.jsonl"
            rec = {
                "at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                "tool": "mutate_relationship_edge",
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
                "confidence": confidence,
                "edge_id": saved.id,
            }
            with audit_path.open("a") as f:
                f.write(json.dumps(rec)+"\n")
        except Exception:
            pass
        return saved.to_dict()

    def disambiguate(self, query: str) -> Dict[str, Any]:
        return res_mod.disambiguate_query(query, self.tlpg)

    def add_construct(self, name: str, kind: str = "Construct", confidence: float = 0.72, **extras) -> Dict[str, Any]:
        """Add a Construct node (Agent, Workflow, Project, Goal, Task, etc.)"""
        node = self.tlpg.add_construct_node(name, kind=kind, confidence=confidence, **extras)
        return node.to_dict() if hasattr(node, "to_dict") else node

    def graphify_constructs(self) -> Dict[str, Any]:
        """Run v0.4 construct graphification — Abstracts/Realizes/Composed_Of etc."""
        return self.tlpg.graphify_constructs()

    def pipeline_run(self, source: str | Path, title: str = "", author: str = None, graphify: bool = True) -> Dict[str, Any]:
        stage1 = self.ingest(source, title=title, author=author)
        doc_id = stage1["document"].id if hasattr(stage1["document"], "id") else stage1["document"].get("id") if isinstance(stage1["document"], dict) else None
        stage2_results = self.extract(document_id=doc_id) if doc_id else self.extract()
        # be defensive — cache formats can evolve, empty results ok
        if not stage2_results:
            total_nodes = 0
            total_edges = 0
            avg_conf = 0.0
        else:
            total_nodes = 0
            total_edges = 0
            avg_acc = 0.0
            for r in stage2_results:
                if isinstance(r, dict):
                    total_nodes += len(r.get("nodes", []))
                    total_edges += len(r.get("edges", []))
                    avg_acc += r.get("confidence_avg", 0.0) or r.get("confidence", 0.0) or 0.0
                else:
                    # ExtractionResult object
                    total_nodes += len(getattr(r, "nodes", []))
                    total_edges += len(getattr(r, "edges", []))
                    avg_acc += getattr(r, "confidence_avg", 0.0)
            avg_conf = avg_acc / max(1, len(stage2_results))
        stage3 = self.resolve_entities()
        stage4 = {}
        if graphify:
            try:
                stage4 = self.graphify_constructs()
            except Exception as e:
                stage4 = {"error": str(e)}
        return {
            "document": stage1["document"].to_dict() if hasattr(stage1["document"], "to_dict") else stage1["document"],
            "chunks": stage1.get("chunk_count", stage1.get("chunks", 1)) if isinstance(stage1, dict) else getattr(stage1, "chunk_count", 1),
            "stage2": {"extractions": len(stage2_results), "nodes_created": total_nodes, "edges_created": total_edges, "avg_conf": avg_conf},
            "stage3": {"resolutions": len(stage3), "actions": stage3[:5]},
            "stage4": stage4,
            "cache": self.cache.stats(),
            "stats": self.tlpg.stats(),
        }

    def sync_from_bundles(self, manifest_path: str | Path = None) -> Dict[str, Any]:
        """Live Sync — mirrors bundles/manifest.json into TLPG Agent/Workflow/Skill/Bundle nodes."""
        from .sync_bundles import sync_from_manifest
        if manifest_path is None:
            # default: workspace/bundles/manifest.json when using workspace=,
            # else resolve from store.base upward
            try:
                # store.base is .../bundles/memory/contacts_harness — go up 2 to bundles/
                candidate = self.store.base.parent.parent / "manifest.json"
                if candidate.exists():
                    manifest_path = candidate
            except:
                pass
        manifest_path = manifest_path or (Path.home() / "workspace" / "bundles" / "manifest.json")
        res = sync_from_manifest(self.tlpg, manifest_path=manifest_path, base_for_log=self.store.base)
        return res

    # ---------------- Goal Slip-Proof ----------------
    def goal_healthcheck(self) -> List[Dict[str, Any]]:
        """
        Returns list of {goal, status, tasks, projects, message}
        status: ok | needs_tasks | no_project | stale
        """
        from datetime import datetime, timezone
        goals = self.tlpg.list_nodes(node_class="Goal")
        if not goals:
            # fallback: try infer from GOAL.md files on disk if tlpg empty
            try:
                base = Path.home() / "workspace" / "goals"
                if base.exists():
                    for gm in base.glob("*/GOAL.md"):
                        # lightweight name from dir or title line
                        try:
                            txt = gm.read_text()[:2000]
                            # first heading
                            name = gm.parent.name.replace("-", " ").title()
                            for line in txt.splitlines()[:5]:
                                if line.strip().startswith("#"):
                                    name = line.strip("# ").strip()[:120]
                                    break
                        except:
                            name = gm.parent.name
                        # upsert if not exists already
                        existing = [g for g in goals if g.canonical_name.lower() == name.lower()]
                        if not existing:
                            ng = self.tlpg.add_construct_node(name, kind="Goal", confidence=0.6, source="goal_md_fallback", deadline="2026-08-31")
                            goals.append(ng)
            except Exception:
                pass

        # build id->node map for Task/Project
        id_to_node = {n.id: n for n in self.tlpg.list_nodes()}
        realizes_edges = self.tlpg.list_edges(edge_type="REALIZES")
        tracks_edges = self.tlpg.list_edges(edge_type="TRACKS")

        out = []
        for goal in goals:
            g_realizes = [e for e in realizes_edges if e.source_id == goal.id]
            # filter to real Project nodes
            proj_targets = []
            for e in g_realizes:
                tn = id_to_node.get(e.target_id)
                if tn and tn.node_class == "Project":
                    proj_targets.append(tn)
                elif tn is None:
                    # fallback: if missing, count anyway
                    proj_targets.append(e)

            g_tracks = [e for e in tracks_edges if e.source_id == goal.id]
            task_targets = []
            for e in g_tracks:
                tn = id_to_node.get(e.target_id)
                if tn and tn.node_class == "Task":
                    # exclude placeholders from real task count
                    if tn.attributes.get("placeholder") or e.properties.get("placeholder"):
                        continue
                    task_targets.append(tn)
                elif tn is None:
                    # edge to missing? count if not placeholder prop
                    if not e.properties.get("placeholder"):
                        task_targets.append(e)

            tasks_cnt = len(task_targets)
            projects_cnt = len(proj_targets)

            # status logic
            status = "ok"
            if tasks_cnt == 0:
                status = "needs_tasks"
            elif projects_cnt == 0:
                status = "no_project"
            elif goal.attributes.get("status") == "stale" or goal.attributes.get("stale") is True:
                status = "stale"
            else:
                # stale heuristic: if goal name contains Launched and no tasks -> already captured as needs_tasks, else ok
                pass

            name = goal.canonical_name
            if status == "ok":
                msg = f"Goal '{name}' has {tasks_cnt} task(s) across {projects_cnt} project(s) — on track."
            elif status == "needs_tasks":
                if "launch" in name.lower() or "launched" in name.lower() or "aug 31" in name.lower() or "aug" in name.lower():
                    msg = f"Goal '{name}' has no tasks yet. Add at least 3 tasks to keep Aug 31 launch from slipping."
                else:
                    msg = f"Goal '{name}' has no tasks linked. Create tasks so it doesn't slip."
            elif status == "no_project":
                msg = f"Goal '{name}' tracks {tasks_cnt} task(s) but isn't linked to a project. Link it so work counts."
            else:  # stale
                msg = f"Goal '{name}' looks stale: {tasks_cnt} tasks, {projects_cnt} projects. Review or close it."

            out.append({
                "goal": name,
                "status": status,
                "tasks": tasks_cnt,
                "projects": projects_cnt,
                "message": msg,
                "goal_id": goal.id,
            })
        return out

    def goal_writeback(self) -> Dict[str, Any]:
        """Log health to bundles/memory/goal_health.jsonl and .scout/missions/health/timeline.jsonl"""
        import json, time
        from datetime import datetime, timezone
        from pathlib import Path as _P
        start = time.time()
        health = self.goal_healthcheck()
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

        # ensure memory dir
        mem_path = _P.home() / "workspace" / "bundles" / "memory" / "goal_health.jsonl"
        try:
            mem_path.parent.mkdir(parents=True, exist_ok=True)
            with mem_path.open("a") as f:
                f.write(json.dumps({"ts": ts, "health": health}) + "\n")
        except Exception as e:
            pass

        # ensure .scout missions health dir
        health_dir = _P.home() / "workspace" / ".scout" / "missions" / "health"
        try:
            health_dir.mkdir(parents=True, exist_ok=True)
            tl_path = health_dir / "timeline.jsonl"
            latency_ms = int((time.time()-start)*1000)
            entry = {
                "nodeId": "goal_health",
                "agentId": "operator",
                "attempt": 1,
                "latency_ms": latency_ms,
                "latency": latency_ms,
                "tokens": 0,
                "tokens_est": 0,
                "status": "ok",
                "errorClass": "",
                "ts": ts,
                "health": health,
            }
            with tl_path.open("a") as f:
                f.write(json.dumps(entry)+"\n")
        except Exception as e:
            pass

        return {"ts": ts, "health": health, "logged_to": [str(mem_path), str(health_dir / "timeline.jsonl")]}

    # ---------------- Power Suite wrappers ----------------
    def search_nodes(self, query: str, top_k: int = 5, node_class: str = None) -> List[Dict]:
        return [n.to_dict() for n in self.tlpg.vector_search_nodes(query, top_k=top_k, node_class=node_class)]

    def health_report(self) -> Dict[str, Any]:
        from .tools import health_report as _hr
        # reuse hub-aware logic but pass base
        return _hr(base=str(self.store.base))

    def sync_all(self, manifest_path: str | Path = None) -> Dict[str, Any]:
        from .tools import sync_all as _sa
        return _sa(manifest_path=str(manifest_path) if manifest_path else None, base=str(self.store.base))

    def stats(self):
        base_stats = self.store.stats()
        base_stats["tlpg"] = self.tlpg.stats()
        base_stats["cache"] = self.cache.stats()
        return base_stats

    def tlpg_stats(self):
        return self.tlpg.stats()

    def cache_stats(self):
        return self.cache.stats()
