"""Local store — JSONL, no cloud, cozy and fast."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import List, Optional, Dict
from .models import Contact, Trigger

DEFAULT_DIR = Path.home() / ".agentic-contacts"
WORKSPACE_FALLBACK = Path.home() / "workspace" / "bundles" / "memory"

class ContactsStore:
    def __init__(self, base: Optional[Path] = None):
        self.base = Path(base) if base else DEFAULT_DIR
        self.base.mkdir(parents=True, exist_ok=True)
        self.contacts_file = self.base / "contacts.jsonl"
        self.triggers_file = self.base / "triggers.jsonl"

    def _read_jsonl(self, p: Path) -> List[Dict]:
        if not p.exists():
            return []
        out=[]
        for line in p.read_text().splitlines():
            if not line.strip(): continue
            try:
                out.append(json.loads(line))
            except: continue
        return out

    def _write_jsonl(self, p: Path, items: List[Dict]):
        p.write_text("\n".join(json.dumps(x) for x in items) + "\n" if items else "")

    # contacts
    def list_contacts(self) -> List[Contact]:
        return [Contact.from_dict(d) for d in self._read_jsonl(self.contacts_file)]

    def save_contact(self, c: Contact):
        contacts = self.list_contacts()
        contacts = [x for x in contacts if x.id != c.id]
        contacts.append(c)
        self._write_jsonl(self.contacts_file, [x.to_dict() for x in contacts])
        return c

    def get_by_name(self, name: str) -> Optional[Contact]:
        name_l = name.lower()
        for c in self.list_contacts():
            if c.name.lower() == name_l:
                return c
        return None

    def get_by_email(self, email: str) -> Optional[Contact]:
        el = email.lower()
        for c in self.list_contacts():
            if any(e.lower()==el for e in c.emails):
                return c
        return None

    # triggers
    def list_triggers(self) -> List[Trigger]:
        return [Trigger(**d) for d in self._read_jsonl(self.triggers_file)]

    def add_trigger(self, t: Trigger):
        trigs = self.list_triggers()
        # confidence guard: manual high-conf should not be clobbered by low-conf heuristic
        # keep higher-confidence when same phrase lowercased collides and existing is manual
        existing = next((x for x in trigs if x.phrase.lower() == t.phrase.lower()), None)
        if existing:
            if existing.source == "manual" and existing.confidence > t.confidence and t.source != "manual":
                # keep manual, don't overwrite
                return existing
            # if both manual, keep newer (allow explicit update)
        # dedup by phrase lower
        trigs = [x for x in trigs if x.phrase.lower() != t.phrase.lower()]
        trigs.append(t)
        self._write_jsonl(self.triggers_file, [x.to_dict() for x in trigs])
        return t

    def stats(self):
        return {
            "base": str(self.base),
            "contacts": len(self.list_contacts()),
            "triggers": len(self.list_triggers()),
        }
