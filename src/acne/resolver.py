"""Resolver — cheap MoMA-lite style, plain reasons, no magic."""
from __future__ import annotations
from typing import List, Optional, Dict
import re
from .models import Contact, Trigger, ResolveResult
from .store import ContactsStore

class ContactsResolver:
    """
    Agent-friendly resolver.
    Cheap path: trigger exact / fuzzy for heartbeat, calendar, quick asks.
    Heavy path: role + org + recency + notes scan for epic agentic flows.
    Always returns why in everyday language.
    """
    def __init__(self, store: ContactsStore):
        self.store = store

    def _score_trigger(self, query: str, trig: Trigger) -> float:
        q = query.lower().strip()
        p = trig.phrase.lower().strip()
        if q == p:
            return trig.confidence * 1.0
        if p in q or q in p:
            return trig.confidence * 0.85
        # word overlap
        qw = set(q.split())
        pw = set(p.split())
        if not qw or not pw:
            return 0.0
        overlap = len(qw & pw) / len(pw)
        if overlap >= 0.6:
            return trig.confidence * overlap * 0.7
        return 0.0

    def _score_contact(self, query: str, c: Contact) -> float:
        q = query.lower()
        sc = 0.0
        if q in c.name.lower():
            sc = max(sc, 0.8 * c.confidence)
        for trig in c.triggers:
            if trig.lower() in q or q in trig.lower():
                sc = max(sc, 0.7 * c.confidence)
        if c.role and c.role.lower() in q:
            sc = max(sc, 0.6 * c.confidence)
        if c.org and c.org.lower() in q:
            sc = max(sc, 0.55 * c.confidence)
        return sc

    def resolve(self, query: str, context: Optional[Dict]=None) -> ResolveResult:
        query = query.strip()
        if not query:
            return ResolveResult(query=query, contact=None, confidence=0.0, why="empty query", source="resolver")

        triggers = self.store.list_triggers()
        contacts = self.store.list_contacts()

        best_trig = None
        best_trig_score = 0.0
        for t in triggers:
            s = self._score_trigger(query, t)
            if s > best_trig_score:
                best_trig_score = s
                best_trig = t

        best_c = None
        best_c_score = 0.0
        for c in contacts:
            s = self._score_contact(query, c)
            if s > best_c_score:
                best_c_score = s
                best_c = c

        # Trigger wins if it points to a real contact with decent score
        if best_trig and best_trig_score >= 0.35:
            # find contact it maps to
            mapped = self.store.get_by_name(best_trig.maps_to_name)
            if mapped:
                why = f"matched '{best_trig.phrase}' → {mapped.name} — {best_trig.reason} (confidence {best_trig.confidence})"
                if best_trig.source == "memory_heuristic" and best_trig.confidence < 0.5:
                    why += " — heuristic, worth confirming"
                return ResolveResult(
                    query=query,
                    contact=mapped,
                    confidence=round(min(0.98, best_trig_score), 2),
                    why=why,
                    trigger_matched=best_trig.phrase,
                    source=best_trig.source,
                )
            # trigger without contact yet — still useful
            return ResolveResult(
                query=query,
                contact=None,
                confidence=round(best_trig_score*0.7,2),
                why=f"found trigger '{best_trig.phrase}' that wants {best_trig.maps_to_name} but no contact saved yet — {best_trig.reason}",
                trigger_matched=best_trig.phrase,
                source=best_trig.source,
            )

        if best_c and best_c_score >= 0.3:
            why = f"closest person is {best_c.name} — matched on name/role"
            if best_c.role:
                why += f" ({best_c.role})"
            return ResolveResult(query=query, contact=best_c, confidence=round(best_c_score,2), why=why, source=best_c.source, alternatives=[c for c in contacts if c.id != best_c.id][:3])

        return ResolveResult(
            query=query,
            contact=None,
            confidence=0.0,
            why=f"no close match — we have {len(contacts)} contacts and {len(triggers)} triggers, try adding '{query}' as a new trigger",
            source="resolver",
            alternatives=contacts[:3]
        )

    def suggest_triggers(self, role: str) -> List[str]:
        # tiny helper for agents
        base = {
            "designer": ["my designer", "the designer", "design call"],
            "client": ["the client call", "client standup", "my client"],
            "engineer": ["my eng", "the dev I talk to"],
        }
        return base.get(role.lower(), [f"my {role}"])
