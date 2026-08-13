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
        except Exception:
            pass
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
        allowed = {"EMPLOYED_BY","AUTHORED","REFERENCES","EXTRACTED_FROM","SAME_AS","PARTNER_WITH","LOCATED_IN","WORKS_ON","BELONGS_TO","MENTIONS","CITES","ATTENDED","ORGANIZED_BY","RELATED_TO"}
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

    def pipeline_run(self, source: str | Path, title: str = "", author: str = None) -> Dict[str, Any]:
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
        return {
            "document": stage1["document"].to_dict() if hasattr(stage1["document"], "to_dict") else stage1["document"],
            "chunks": stage1.get("chunk_count", stage1.get("chunks", 1)) if isinstance(stage1, dict) else getattr(stage1, "chunk_count", 1),
            "stage2": {"extractions": len(stage2_results), "nodes_created": total_nodes, "edges_created": total_edges, "avg_conf": avg_conf},
            "stage3": {"resolutions": len(stage3), "actions": stage3[:5]},
            "cache": self.cache.stats(),
            "stats": self.tlpg.stats(),
        }

    def stats(self):
        base_stats = self.store.stats()
        base_stats["tlpg"] = self.tlpg.stats()
        base_stats["cache"] = self.cache.stats()
        return base_stats

    def tlpg_stats(self):
        return self.tlpg.stats()

    def cache_stats(self):
        return self.cache.stats()
