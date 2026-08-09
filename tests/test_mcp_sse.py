"""SSE MCP wrapper: real schemas synthesized from TOOLS_DEF, same dispatch as stdio."""

import json

import pytest

pytest.importorskip("mcp")


def test_build_server_exposes_all_stdio_tools_with_real_schemas(tmp_path, monkeypatch):
    import anyio

    from acne import mcp_server, mcp_sse
    from acne.hub import ContactsHub

    monkeypatch.setattr(mcp_server, "get_hub", lambda: ContactsHub(base=tmp_path))
    server = mcp_sse.build_server()
    tools = anyio.run(server.list_tools)
    assert {t.name for t in tools} == {t["name"] for t in mcp_server.TOOLS_DEF}

    # The wire schema must carry the REAL fields — a caller passing {"query": ...}
    # is validated natively, never silently dropped.
    resolve = next(t for t in tools if t.name == "contacts_resolve")
    assert "query" in resolve.inputSchema["properties"]
    assert "query" in resolve.inputSchema.get("required", [])
    graph = next(t for t in tools if t.name == "search_entity_graph")
    assert {"query", "hops", "top_k", "compressed"} <= set(graph.inputSchema["properties"])


def test_add_then_resolve_roundtrip_with_real_fields(tmp_path, monkeypatch):
    from acne import mcp_server, mcp_sse
    from acne.hub import ContactsHub

    hub = ContactsHub(base=tmp_path)
    monkeypatch.setattr(mcp_server, "get_hub", lambda: hub)

    add = mcp_sse._make_tool(next(t for t in mcp_server.TOOLS_DEF if t["name"] == "contacts_add"))
    out = json.loads(add(name="Alex Rivera", email="alex@studio.com", role="designer", trigger="my designer"))
    assert out["ok"] is True
    assert out["result"]["name"] == "Alex Rivera"

    resolve = mcp_sse._make_tool(next(t for t in mcp_server.TOOLS_DEF if t["name"] == "contacts_resolve"))
    res = json.loads(resolve(query="my designer"))
    assert res["ok"] is True
    assert res["result"]["contact"]["name"] == "Alex Rivera"


def test_optional_params_omitted_not_sent(monkeypatch):
    from acne import mcp_server, mcp_sse

    captured = {}

    def _spy(params):
        captured.update(params)
        return {"spied": True}

    # _make_tool reads the dispatch symbol at synthesis time — patch first.
    monkeypatch.setattr(mcp_sse, "handle_tools_call", _spy)
    tdef = next(t for t in mcp_server.TOOLS_DEF if t["name"] == "contacts_add")
    fn = mcp_sse._make_tool(tdef)
    out = json.loads(fn(name="OnlyName"))
    assert out["ok"] is True
    assert captured["arguments"] == {"name": "OnlyName"}


def test_dispatch_error_is_structured(tmp_path, monkeypatch):
    from acne import mcp_server, mcp_sse
    from acne.hub import ContactsHub

    monkeypatch.setattr(mcp_server, "get_hub", lambda: ContactsHub(base=tmp_path))
    bad = mcp_sse._make_tool(
        {"name": "mutate_relationship_edge",
         "inputSchema": {"type": "object",
                         "properties": {"source_id": {"type": "string"},
                                        "target_id": {"type": "string"},
                                        "edge_type": {"type": "string"}},
                         "required": ["source_id", "target_id", "edge_type"]}}
    )
    out = json.loads(bad(source_id="nope", target_id="nope2", edge_type="NOT_A_REAL_TYPE"))
    assert "ok" in out
