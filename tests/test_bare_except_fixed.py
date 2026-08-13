"""Regression test: JSONL/cache readers must not swallow BaseException
subclasses (KeyboardInterrupt, SystemExit). Cycle 1 fixed this for
ContactsStore._read_jsonl; this covers the same defect in TLPGStore and
TokenCache, which used bare `except:` clauses and would otherwise catch
and discard a user's Ctrl+C.
"""
import json
import tempfile
from pathlib import Path

import pytest

from acne.graph import TLPGStore
from acne.cache import TokenCache


def test_tlpg_read_only_swallows_json_errors_not_keyboardinterrupt(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        store = TLPGStore(base=Path(td))
        p = store.nodes_file
        p.write_text("not valid json\n")

        # A malformed line is skipped, not fatal.
        assert store._read(p) == []

        # But a real interrupt during parsing must propagate, not be eaten.
        def boom(*a, **kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(json, "loads", boom)
        with pytest.raises(KeyboardInterrupt):
            store._read(p)


def test_token_cache_load_does_not_swallow_keyboardinterrupt(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        cache = TokenCache(base=base)
        cache.put_doc("chk1", "doc1")

        # Malformed line in a cache file is tolerated.
        with cache.doc_file.open("a") as f:
            f.write("not valid json\n")
        assert TokenCache(base=base).get_doc_for_checksum("chk1") == "doc1"

        def boom(*a, **kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(json, "loads", boom)
        with pytest.raises(KeyboardInterrupt):
            TokenCache(base=base)
