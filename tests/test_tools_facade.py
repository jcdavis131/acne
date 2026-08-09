"""The five-function facade the scout-cli contacts plugin imports is a contract."""

from acne import tools


def test_facade_exports_the_plugin_contract():
    for fn in ("resolve_contact", "search_nodes", "graphify_query", "health_report", "sync_all"):
        assert callable(getattr(tools, fn))


def test_resolve_contact_normalized_shape(tmp_path):
    from acne.hub import ContactsHub

    hub = ContactsHub(base=tmp_path)
    hub.add_contact("Alex Rivera", email="alex@studio.com", role="designer", trigger="my designer")
    res = tools.resolve_contact("my designer", base=tmp_path)
    for key in ("query", "contact", "confidence", "why", "trigger_matched", "source"):
        assert key in res
    assert res["contact"] is not None
    assert res["contact"]["name"] == "Alex Rivera"
    assert res["confidence"] > 0


def test_resolve_contact_empty_store(tmp_path):
    res = tools.resolve_contact("my designer", base=tmp_path)
    assert res["contact"] is None
    assert res["confidence"] == 0


def test_health_report_composite(tmp_path):
    r = tools.health_report(base=tmp_path)
    assert set(r) >= {"contacts", "tlpg", "cache", "store_base"}


def test_search_and_graphrag_empty_graph(tmp_path):
    assert tools.search_nodes("anything", base=tmp_path) == []
    g = tools.graphify_query("anything", base=tmp_path)
    assert g["nodes"] == []


def test_sync_all_walks_dir_and_reports_manifest_note(tmp_path):
    src = tmp_path / "docs"
    src.mkdir()
    (src / "note.md").write_text(
        "From: Alice Chen <alice@acme-corp.com>\nAlice Chen authored Q4 report on 2025-11-10."
    )
    out = tools.sync_all(source_dir=str(src), base=tmp_path / "store")
    assert out["synced"] == 1
    assert out["errors"] == []
    # manifest compatibility path is honest about what it does
    out2 = tools.sync_all(manifest_path=str(src / "manifest.json"), base=tmp_path / "store2")
    assert "note" in out2


def test_sync_all_missing_dir_is_structured_not_crash(tmp_path):
    out = tools.sync_all(source_dir=str(tmp_path / "nope"), base=tmp_path / "store")
    assert out["synced"] == 0
    assert out["errors"]
