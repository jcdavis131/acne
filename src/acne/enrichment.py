"""Enrichment adapters — cozy, local, no cloud unless you say so."""
from __future__ import annotations
from typing import List, Dict
from pathlib import Path
from datetime import datetime
import re
from .models import Contact, Enrichment

def enrich_from_memory(memory_text: str, hub=None) -> List[Dict]:
    """
    Scan daily notes + MEMORY.md for likely people.
    Keeps confidence low — memory is a hint, not truth.
    """
    # look for "talked to X", "called X", "met X", "with X", "from X" patterns first
    pattern_names = re.findall(r"(?:talked to|called|met|with|from|to)\s+([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?)", memory_text)
    skip = {
        "Scout","Cameron","Monday","Tuesday","Wednesday","Thursday","Friday",
        "Google","Execution","Calendar","Style","Keep","Dottie","Memory","Bundle",
        "Manually","Design","Figma","Slack","Github","Notion","Agent","Tools"
    }
    freq = {}
    for raw in pattern_names:
        name = raw.strip()
        if name in skip: continue
        if len(name) < 3: continue
        freq[name] = freq.get(name, 0) + 1

    # fallback: capitalized words, but only if they look like names (not generic nouns)
    if not freq:
        words = re.findall(r"\b[A-Z][a-z]{3,}\b", memory_text)
        for w in words:
            if w in skip: continue
            freq[w] = freq.get(w, 0) + 1

    cands = []
    for name, count in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15]:
        # require at least 1 real mention, keep it quiet
        if count >= 1:
            cands.append({
                "name": name,
                "count": count,
                "kind": "memory",
                "confidence": 0.28 if count < 3 else 0.38,
                "reason": f"saw {name} {count} time(s) in notes — might be someone you know"
            })
    return cands

def enrich_from_calendar_events(events: List[Dict]) -> List[Dict]:
    attendees = {}
    for ev in events:
        for a in ev.get("attendees", []):
            n = a.get("displayName") or a.get("email") or ""
            if not n or "cameron" in n.lower():
                continue
            attendees[n] = attendees.get(n, 0) + 1
    out=[]
    for name, count in sorted(attendees.items(), key=lambda x: x[1], reverse=True)[:15]:
        out.append({
            "name": name,
            "count": count,
            "kind": "calendar",
            "confidence": min(0.92, 0.6 + count*0.08),
            "reason": f"met {count} times in last 30d — calendar",
        })
    return out
