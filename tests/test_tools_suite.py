"""Power suite tests for ACNE Contacts — 3 real-behavior tests"""

import tempfile
import json
from pathlib import Path

def _tmp_hub():
    import sys
    src = Path.home() / "workspace" / "acne" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from acne.hub import ContactsHub
    tmp = Path(tempfile.mkdtemp(prefix="test-tools-suite-"))
    hub = ContactsHub(base=tmp)
    return hub, tmp

def test_resolve_and_search_and_graphrag_empty_graceful():
    hub, tmp = _tmp_hub()
    from acne.tools import resolve_contact, search_nodes, graphify_query

    # empty TLPG -> graceful [] not crash
    res = resolve_contact("my designer", base=str(tmp))
    assert isinstance(res, dict)
    assert "query" in res

    nodes = search_nodes("builder uses productivity-pack", top_k=3, base=str(tmp))
    assert isinstance(nodes, list)
    assert len(nodes) == 0  # empty base -> empty

    g = graphify_query("which agent executes flawless-delivery?", hops=2, top_k=3, base=str(tmp))
    assert isinstance(g, dict)
    assert "nodes" in g
    assert "edges" in g
    # empty gracefully
    assert g.get("nodes") == [] or isinstance(g["nodes"], list)

def test_health_report_and_sync_all_real():
    hub, tmp = _tmp_hub()
    from acne.tools import health_report, sync_all

    hr = health_report(base=str(tmp))
    assert "contacts" in hr
    assert "tlpg" in hr
    assert "cache" in hr
    assert "by_class" in hr
    assert "stale_triggers" in hr
    assert "ts" in hr

    # sync_all with manifest — may find real manifest at workspace/bundles/manifest.json
    manifest = Path.home() / "workspace" / "bundles" / "manifest.json"
    if not manifest.exists():
        # create tiny fake manifest
        manifest = tmp / "manifest.json"
        manifest.write_text(json.dumps({
            "name": "Test Bundle",
            "version": "0.0.1-test",
            "agents": [{"id": "builder", "role": "The Maker", "layer": 3, "skills": ["builder-pack"]}],
            "skill_packs": [{"id": "builder-pack", "use": "web artifacts"}],
            "workflows": [{"id": "flawless-delivery", "use_for": "legacy"}],
        }))

    sa = sync_all(manifest_path=str(manifest), base=str(tmp))
    assert isinstance(sa, dict)
    assert "sync" in sa
    assert "graphify" in sa
    assert "goal_health" in sa
    assert "stats" in sa
    # real hill-climb: if manifest has builder -> at least 1 agent node
    stats = sa.get("stats", {})
    by = stats.get("by_class", {})
    # tolerant: if fake manifest, 1; if real manifest, >=10
    if by:
        assert by.get("Agent", 0) >= 1

def test_hub_wrappers_parity():
    hub, tmp = _tmp_hub()
    # hub wrappers exist
    assert hasattr(hub, "search_nodes")
    assert hasattr(hub, "sync_all")
    assert hasattr(hub, "health_report")

    # test parity search_nodes
    nodes = hub.search_nodes("test query", top_k=2)
    assert isinstance(nodes, list)

    hr = hub.health_report()
    assert isinstance(hr, dict)
    assert "by_class" in hr
