"""
mcp_server.py — MCP JSON-RPC 2.0 over Stdio & Streamable HTTP light wrapper
Exposes our TLPG as standard MCP tools/resources. v0.2.1 token-cache aware 💰
"""

from __future__ import annotations
import sys, json, asyncio
from typing import Dict, Any
from pathlib import Path
from .hub import ContactsHub

# MCP SDK agnostic definition - 12 tools for harness-native agents (v0.2.1 fully wired)
TOOLS_DEF = [
    {
        "name": "contacts_resolve",
        "description": "Resolve 'my designer' etc to a real person — local-first, confidence + why",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "contacts_add",
        "description": "Add a person you work with — saves to local harness store",
        "inputSchema": {"type":"object","properties":{"name":{"type":"string"},"email":{"type":"string"},"role":{"type":"string"},"trigger":{"type":"string"}}, "required":["name"]}
    },
    {
        "name": "contacts_list",
        "description": "List your harness contacts — local only",
        "inputSchema": {"type":"object","properties":{"top":{"type":"number","default":20}}}
    },
    {
        "name": "search_entity_graph",
        "description": "Hybrid retrieval combining dense vector embeddings with multi-hop graph traversal — 87% cheaper compressed mode + token-cache hits",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "hops": {"type": "integer", "default": 2}, "top_k": {"type": "integer", "default": 5}, "compressed": {"type": "boolean", "default": False}}, "required": ["query"]}
    },
    {
        "name": "resolve_identity_conflict",
        "description": "Explicitly merges or separates candidate contact nodes via SAME_AS reasoning (Stage 3)",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "disambiguate_entity",
        "description": "Return SAME_AS cluster for ambiguous entity — Stage 3 disambiguation",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "mutate_relationship_edge",
        "description": "Creates, updates, or invalidates directional property edges between entities with temporal attributes",
        "inputSchema": {"type": "object", "properties": {"source_id": {"type": "string"}, "target_id": {"type": "string"}, "edge_type": {"type": "string"}, "confidence": {"type": "number"}, "valid_from": {"type": "string"}, "properties": {"type": "object"}}, "required": ["source_id", "target_id", "edge_type"]}
    },
    {
        "name": "ingest_document",
        "description": "Stage 1: parse and chunk unstructured feed with provenance anchoring — dedup cache avoids re-work",
        "inputSchema": {"type": "object", "properties": {"source": {"type": "string"}, "title": {"type": "string"}, "author": {"type": "string"}}, "required": ["source"]}
    },
    {
        "name": "extract_entities",
        "description": "Stage 2: schema-guided NER+RE into typed TLPG nodes/edges — extraction cache saves ~400 tok per chunk",
        "inputSchema": {"type": "object", "properties": {"document_id": {"type": "string"}, "model": {"type": "string"}}, "required": []}
    },
    {
        "name": "resolve_entities",
        "description": "Stage 3: blocking, vector filtering, topological resolution → SAME_AS or merge",
        "inputSchema": {"type": "object", "properties": {"merge_threshold": {"type": "number"}, "same_as_threshold": {"type": "number"}}, "required": []}
    },
    {
        "name": "run_pipeline",
        "description": "Full 4-stage pipeline: ingest→extract→resolve — cache aware, cheap for repeated harness heartbeats",
        "inputSchema": {"type":"object","properties":{"source":{"type":"string"},"title":{"type":"string"},"author":{"type":"string"}}, "required":["source"]}
    },
    {
        "name": "cache_stats",
        "description": "Show token-cache ROI — hits, tokens saved, $$$ saved. Perfect for proving efficiency to expensive agent users",
        "inputSchema": {"type":"object","properties":{}}
    },
    {
        "name": "cache_clear",
        "description": "Clear all cache layers — docs, embeddings, extractions, queries",
        "inputSchema": {"type":"object","properties":{}}
    },
]

RESOURCES_DEF = [
    {"uri": "mcp://contacts/entities/{entity_id}", "name": "entity", "description": "Complete node state JSON including active edges"},
    {"uri": "mcp://contacts/graph/community/{cluster_id}", "name": "community", "description": "Pre-computed community summary"},
    {"uri": "mcp://contacts/cache/stats", "name": "cache_stats", "description": "Token-cache stats and ROI"},
]

def get_hub():
    return ContactsHub()

def handle_tools_list(_params):
    return {"tools": TOOLS_DEF}

def handle_resources_list(_params):
    return {"resources": RESOURCES_DEF}

def handle_tools_call(params: Dict[str, Any]):
    hub = get_hub()
    name = params.get("name")
    args = params.get("arguments", {})
    if name == "contacts_resolve":
        return hub.resolve(args.get("query","")).to_dict()
    if name == "contacts_add":
        c = hub.add_contact(args.get("name",""), email=args.get("email",""), role=args.get("role",""), trigger=args.get("trigger",""))
        return c.to_dict()
    if name == "contacts_list":
        cs = hub.list_contacts()[:int(args.get("top",20))]
        return {"contacts": [c.to_dict() for c in cs], "count": len(cs)}
    if name == "search_entity_graph":
        return hub.graphrag(args.get("query",""), hops=args.get("hops",2), top_k=args.get("top_k",5), compressed=args.get("compressed", False))
    if name in ["resolve_identity_conflict","disambiguate_entity"]:
        return hub.disambiguate(args.get("query",""))
    if name == "mutate_relationship_edge":
        return hub.mutate_relationship_edge(args["source_id"], args["target_id"], args["edge_type"], confidence=args.get("confidence",0.7), valid_from=args.get("valid_from"), properties=args.get("properties"))
    if name == "ingest_document":
        res = hub.ingest(args["source"], title=args.get("title",""), author=args.get("author"))
        return {"document": res["document"].to_dict(), "chunk_count": res["chunk_count"]}
    if name == "extract_entities":
        return {"extractions": hub.extract(document_id=args.get("document_id"), model=args.get("model","heuristic"))}
    if name == "resolve_entities":
        return {"resolutions": hub.resolve_entities(args.get("merge_threshold",0.82), args.get("same_as_threshold",0.55))}
    if name == "run_pipeline":
        return hub.pipeline_run(args["source"], title=args.get("title",""), author=args.get("author"))
    if name == "cache_stats":
        return hub.cache_stats()
    if name == "cache_clear":
        hub.cache.clear()
        return {"ok": True, "cleared": True}
    raise ValueError(f"unknown tool {name}")

def handle_resources_read(params: Dict[str, Any]):
    hub = get_hub()
    uri = params.get("uri","")
    if uri.startswith("mcp://contacts/entities/"):
        eid = uri.split("/")[-1]
        node = hub.tlpg.get_node(eid)
        if not node:
            found = hub.tlpg.find_nodes_by_name(eid)
            node = found[0] if found else None
        if not node:
            return {"error": f"entity {eid} not found"}
        nb = hub.tlpg.neighbors(node.id, depth=1)
        return {"entity": node.to_dict(), "neighbors": [n.to_dict() for n in nb["nodes"]], "edges": [e.to_dict() for e in nb["edges"]]}
    if "cache/stats" in uri:
        return hub.cache_stats()
    return {"error": "unknown uri"}

def handle_request(req: Dict[str, Any]) -> Dict[str, Any]:
    mid = req.get("id")
    method = req.get("method")
    params = req.get("params", {})
    try:
        if method == "initialize":
            return {"jsonrpc":"2.0","id":mid,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{},"resources":{}},"serverInfo":{"name":"agentic-contacts","version":"0.2.1"}}}
        if method == "tools/list":
            return {"jsonrpc":"2.0","id":mid,"result":handle_tools_list(params)}
        if method == "tools/call":
            return {"jsonrpc":"2.0","id":mid,"result":handle_tools_call(params)}
        if method == "resources/list":
            return {"jsonrpc":"2.0","id":mid,"result":handle_resources_list(params)}
        if method == "resources/read":
            return {"jsonrpc":"2.0","id":mid,"result":handle_resources_read(params)}
        return {"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":f"Method not found: {method}"}}
    except Exception as e:
        return {"jsonrpc":"2.0","id":mid,"error":{"code":-32603,"message":str(e)}}

def main_stdio():
    hub = get_hub()  # warm
    for line in sys.stdin:
        if not line.strip(): continue
        try:
            req = json.loads(line)
        except: continue
        resp = handle_request(req)
        sys.stdout.write(json.dumps(resp)+"\n"); sys.stdout.flush()

if __name__ == "__main__":
    main_stdio()
