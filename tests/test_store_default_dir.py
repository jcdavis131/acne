"""Regression test: default store dir matches the README (~/.acne), with a
safe fallback to the legacy ~/.agentic-contacts path for pre-existing installs.
"""
import importlib
import tempfile
from pathlib import Path

import acne.store as store_mod


def test_new_install_defaults_to_dot_acne(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        fake_home = Path(td)
        monkeypatch.setattr(store_mod.Path, "home", classmethod(lambda cls: fake_home))
        importlib.reload(store_mod)
        try:
            s = store_mod.ContactsStore()
            assert s.base == fake_home / ".acne"
        finally:
            importlib.reload(store_mod)


def test_legacy_install_keeps_using_agentic_contacts_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        fake_home = Path(td)
        legacy = fake_home / ".agentic-contacts"
        legacy.mkdir()
        (legacy / "contacts.jsonl").write_text("")
        monkeypatch.setattr(store_mod.Path, "home", classmethod(lambda cls: fake_home))
        importlib.reload(store_mod)
        try:
            s = store_mod.ContactsStore()
            assert s.base == legacy
        finally:
            importlib.reload(store_mod)


def test_explicit_base_always_wins(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        explicit = Path(td) / "somewhere-else"
        s = store_mod.ContactsStore(base=explicit)
        assert s.base == explicit
