"""CLI — built so humans and agents both feel at home. v0.2 TLPG edition"""

from __future__ import annotations
import json
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
from .hub import ContactsHub

app = typer.Typer(help="agentic-contacts — contacts for harnesses (TLPG edition)", no_args_is_help=True)
console = Console()

def _hub():
    return ContactsHub()

@app.command("init")
def init_cmd():
    hub = _hub()
    st = hub.stats()
    console.print(f"[green]Ready[/] at {hub.store.base}")
    console.print(f"contacts: {st.get('contacts',0)} triggers: {st.get('triggers',0)}")
    tlpg = st.get("tlpg", {})
    console.print(f"TLPG nodes: {tlpg.get('nodes',0)} edges: {tlpg.get('edges',0)} docs: {tlpg.get('documents',0)} chunks: {tlpg.get('chunks',0)}")

@app.command("add")
def add_cmd(name: str = typer.Option(..., "--name"), email: str = typer.Option("", "--email"), role: str = typer.Option("", "--role"), trigger: str = typer.Option("", "--trigger"), org: str = typer.Option("", "--org"), notes: str = typer.Option("", "--notes")):
    hub = _hub()
    c = hub.add_contact(name=name, email=email, role=role, org=org, trigger=trigger, notes=notes)
    console.print(f"[green]Saved[/] {c.name} <{c.primary_email() or ''}> role {c.role or '-'} trigger '{trigger or '-'}'")

@app.command("resolve")
def resolve_cmd(query: str = typer.Argument(..., help="like 'my designer' or 'the client call'"), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    res = hub.resolve(query)
    if json_out:
        console.print_json(json.dumps(res.to_dict(), indent=2))
        return
    if res.contact:
        console.print(f"[bold]{res.contact.name}[/] <{res.contact.primary_email() or ''}>  [cyan]{res.confidence}[/] — {res.why}")
    else:
        console.print(f"[yellow]No match[/] for '{query}' — {res.why}")

@app.command("list")
def list_cmd(top: int = typer.Option(20, "--top"), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    contacts = hub.list_contacts()[:top]
    if json_out:
        console.print_json(json.dumps([c.to_dict() for c in contacts], indent=2))
        return
    t = Table(title=f"Contacts ({len(contacts)})")
    t.add_column("Name"); t.add_column("Email"); t.add_column("Role"); t.add_column("Triggers")
    for c in contacts:
        t.add_row(c.name, c.primary_email() or "", c.role or "", ", ".join(c.triggers[:3]))
    console.print(t)

@app.command("triggers")
def triggers_cmd(json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    trigs = hub.store.list_triggers()
    if json_out:
        console.print_json(json.dumps([x.to_dict() for x in trigs], indent=2))
        return
    t = Table(title=f"Triggers ({len(trigs)})")
    t.add_column("Phrase"); t.add_column("Maps to"); t.add_column("Conf"); t.add_column("Why")
    for x in trigs[:50]:
        t.add_row(x.phrase, x.maps_to_name, str(x.confidence), x.reason[:60])
    console.print(t)

@app.command("enrich-memory")
def enrich_mem(days: int = typer.Option(30, "--days")):
    hub = _hub()
    cands = hub.enrich_from_memory(days=days)
    console.print(f"[green]Found[/] {len(cands)} candidates from memory")
    for c in cands[:10]:
        console.print(f"  {c['name']} x{c['count']} {c['confidence']} — {c['reason']}")

@app.command("graph")
def graph_cmd(json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    st = hub.tlpg_stats()
    if json_out:
        console.print_json(json.dumps(st, indent=2))
        return
    console.print(f"base {hub.store.base}")
    console.print(f"TLPG {st}")

# ---------------- TLPG pipeline commands ----------------

@app.command("ingest")
def ingest_cmd(source: str = typer.Argument(..., help="File path or raw text"), title: str = typer.Option("", "--title"), author: str = typer.Option("", "--author")):
    hub = _hub()
    p = Path(source)
    src = str(p) if p.exists() else source
    res = hub.ingest(src, title=title, author=author)
    console.print(f"[green]Ingested[/] doc {res['document'].id} '{res['document'].title}' → {res['chunk_count']} chunks ({res['raw_text_len']} chars)")
    for chk in res["chunks"][:3]:
        console.print(f"  chunk {chk.chunk_index} {chk.token_count}tok {chk.text[:90]}...")

@app.command("extract")
def extract_cmd(doc_id: str = typer.Option("", "--doc"), model: str = typer.Option("heuristic", "--model"), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    res = hub.extract(document_id=doc_id or None, model=model)
    if json_out:
        console.print_json(json.dumps(res, indent=2))
        return
    total_nodes = sum(len(r["nodes"]) for r in res)
    total_edges = sum(len(r["edges"]) for r in res)
    console.print(f"[green]Extracted[/] {len(res)} chunks → {total_nodes} nodes, {total_edges} edges")
    for r in res[:3]:
        console.print(f"  chunk {r['chunk_id'][:10]} conf {r['confidence_avg']} nodes {[n['canonical_name'] for n in r['nodes'][:3]]}")

@app.command("resolve-entities")
def resolve_entities_cmd(merge: float = typer.Option(0.82, "--merge"), same: float = typer.Option(0.55, "--same")):
    hub = _hub()
    res = hub.resolve_entities(merge_threshold=merge, same_as_threshold=same)
    console.print(f"[green]Resolved[/] {len(res)} actions")
    for r in res[:10]:
        console.print(f"  {r['reason'][:100]} conf {r['confidence']} method {r['method']}")

@app.command("mutate-edge")
def mutate_edge_cmd(source: str = typer.Option(..., "--source"), target: str = typer.Option(..., "--target"), edge_type: str = typer.Option("RELATED_TO", "--type"), confidence: float = typer.Option(0.7, "--conf"), valid_from: str = typer.Option("", "--valid-from")):
    hub = _hub()
    # allow name lookup to id
    src_node = hub.tlpg.get_node(source) or (hub.tlpg.find_nodes_by_name(source)[0] if hub.tlpg.find_nodes_by_name(source) else None)
    tgt_node = hub.tlpg.get_node(target) or (hub.tlpg.find_nodes_by_name(target)[0] if hub.tlpg.find_nodes_by_name(target) else None)
    src_id = src_node.id if hasattr(src_node, 'id') else source
    tgt_id = tgt_node.id if hasattr(tgt_node, 'id') else target
    res = hub.mutate_relationship_edge(src_id, tgt_id, edge_type, confidence=confidence, valid_from=valid_from or None)
    console.print_json(json.dumps(res, indent=2))

@app.command("disambiguate")
def disambiguate_cmd(query: str = typer.Argument(...), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    res = hub.disambiguate(query)
    if json_out:
        console.print_json(json.dumps(res, indent=2))
        return
    console.print(f"[yellow]Clusters[/] for '{query}' {len(res['clusters'])}")
    for cl in res["clusters"][:5]:
        console.print(f"  {cl['canonical']['canonical_name']} ({cl['canonical']['node_class']}) SAME_AS edges {len(cl['same_as_edges'])}")

@app.command("pipeline")
def pipeline_cmd(source: str = typer.Argument(..., help="File or raw text blob"), title: str = typer.Option("", "--title"), author: str = typer.Option("", "--author"), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    p = Path(source)
    src = str(p) if p.exists() else source
    res = hub.pipeline_run(src, title=title, author=author)
    if json_out:
        console.print_json(json.dumps(res, indent=2))
        return
    console.print(f"[green]Pipeline done[/] doc {res['document']['id']} chunks {res['chunks']} → nodes {res['stage2']['nodes_created']} edges {res['stage2']['edges_created']}")
    console.print(f"  resolutions {res['stage3']['resolutions']} stats {res['stats']}")

@app.command("nodes")
def nodes_cmd(nclass: str = typer.Option("", "--class"), top: int = typer.Option(30, "--top"), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    nodes = hub.tlpg.list_nodes(node_class=nclass or None)[:top]
    if json_out:
        console.print_json(json.dumps([n.to_dict() for n in nodes], indent=2))
        return
    t = Table(title=f"Nodes ({len(nodes)})")
    t.add_column("Class"); t.add_column("Name"); t.add_column("Id"); t.add_column("Conf")
    for n in nodes:
        t.add_row(n.node_class, n.canonical_name[:40], n.id[:10], str(n.confidence))
    console.print(t)

@app.command("edges")
def edges_cmd(etype: str = typer.Option("", "--type"), top: int = typer.Option(50, "--top"), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    edges = hub.tlpg.list_edges(edge_type=etype or None)[:top]
    if json_out:
        console.print_json(json.dumps([e.to_dict() for e in edges], indent=2))
        return
    t = Table(title=f"Edges ({len(edges)})")
    t.add_column("Type"); t.add_column("From → To"); t.add_column("Conf")
    for e in edges:
        t.add_row(e.edge_type, f"{e.source_id[:8]}→{e.target_id[:8]}", str(e.confidence))
    console.print(t)

# MCP-style tool defs for LLM callers — extended v0.2 + cache
@app.command("mcp-def")
def mcp_def():
    defs = [
        {"name": "contacts_resolve", "description": "Resolve a phrase like 'my designer' to a real person", "parameters": {"type":"object","properties":{"query":{"type":"string"}}}},
        {"name": "contacts_add", "description": "Add a person with triggers", "parameters": {"type":"object","properties":{"name":{"type":"string"},"email":{"type":"string"},"role":{"type":"string"},"trigger":{"type":"string"}}}},
        {"name": "contacts_list", "description": "List saved contacts", "parameters": {"type":"object","properties":{"top":{"type":"number"}}}},
        {"name": "ingest_document", "description": "Stage 1: ingest unstructured text/file into TLPG with provenance chunking", "parameters": {"type":"object","properties":{"source":{"type":"string"},"title":{"type":"string"},"author":{"type":"string"}}}},
        {"name": "extract_entities", "description": "Stage 2: schema-guided NER+RE to typed nodes/edges", "parameters": {"type":"object","properties":{"document_id":{"type":"string"},"model":{"type":"string"}}}},
        {"name": "resolve_entities", "description": "Stage 3: dynamic blocking, vector filter, topological resolution -> SAME_AS or merge", "parameters": {"type":"object","properties":{"merge_threshold":{"type":"number"},"same_as_threshold":{"type":"number"}}}},
        {"name": "search_entity_graph", "description": "Stage 4 GraphRAG: hybrid dense+graph traversal with provenance", "parameters": {"type":"object","properties":{"query":{"type":"string"},"hops":{"type":"number"},"top_k":{"type":"number"},"compressed":{"type":"boolean","description":"Return 87% smaller token-optimized pack for expensive agents"}}}},
        {"name": "mutate_relationship_edge", "description": "MCP commit: write/rewrite edge into TLPG with temporal validity", "parameters": {"type":"object","properties":{"source_id":{"type":"string"},"target_id":{"type":"string"},"edge_type":{"type":"string"},"confidence":{"type":"number"},"valid_from":{"type":"string"}}}},
        {"name": "disambiguate_entity", "description": "Return SAME_AS cluster for ambiguous entity", "parameters": {"type":"object","properties":{"query":{"type":"string"}}}},
        {"name": "run_pipeline", "description": "Full 4-stage pipeline: ingest→extract→resolve", "parameters": {"type":"object","properties":{"source":{"type":"string"},"title":{"type":"string"}}}},
        {"name": "cache_stats", "description": "Show token-cache hits, tokens saved, $$$ saved — great for demoing ROI", "parameters": {"type":"object","properties":{}}},
        {"name": "cache_clear", "description": "Clear all cache layers", "parameters": {"type":"object","properties":{}}},
    ]
    console.print_json(json.dumps(defs, indent=2))

@app.command("cache-stats")
def cache_stats_cmd(json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    st = hub.cache_stats()
    if json_out:
        console.print_json(json.dumps(st, indent=2))
        return
    console.print(f"[bold green]💰 Token Cache ROI[/]")
    console.print(f"  query hits {st['query_hits']} / miss {st['query_miss']}  doc hits {st['doc_hits']} / miss {st['doc_miss']}")
    console.print(f"  emb hits {st['emb_hits']} / miss {st['emb_miss']}  ext hits {st['ext_hits']} / miss {st['ext_miss']}")
    console.print(f"  tokens saved ~{st['tokens_saved']} → ${st['money_saved']} @ $0.015/1k")
    console.print(f"  entries {st['cache_entries']} hit_rate {st['hit_rate_est']}")
    console.print(f"  {st['note']}")

@app.command("cache-clear")
def cache_clear_cmd():
    hub = _hub()
    hub.cache.clear()
    console.print("[green]Cache cleared[/] — all layers reset")

@app.command("graphrag")
def graphrag_cmd(query: str = typer.Argument(..., help="e.g. 'Find all citations authored by partners of Acme Corp'"), hops: int = typer.Option(2, "--hops"), top: int = typer.Option(5, "--top"), compressed: bool = typer.Option(False, "--compressed", help="87% smaller pack for expensive LLM agents"), json_out: bool = typer.Option(False, "--json")):
    hub = _hub()
    res = hub.graphrag(query, hops=hops, top_k=top, compressed=compressed)
    if json_out:
        console.print_json(json.dumps(res, indent=2))
        return
    if compressed:
        console.print(f"[bold]GraphRAG compressed[/] '{query}' → {len(res['facts'])} facts, budget {res['budget_tokens']}tok, {res['why_cheap']}")
        for f in res["facts"][:8]:
            console.print(f"  {f['from']} -[{f['type']}]→ {f['to']}")
        return
    console.print(f"[bold]GraphRAG[/] '{query}' → {len(res['nodes'])} nodes, {len(res['edges'])} edges, seeds {len(res['seeds'])}")
    for n in res["seeds"][:5]:
        console.print(f"  seed {n['node_class']}:{n['canonical_name']} conf {n['confidence']}")
    for e in res["edges"][:8]:
        console.print(f"  edge {e['source_id'][:8]} -[{e['edge_type']} {e['confidence']}]→ {e['target_id'][:8]}")

if __name__ == "__main__":
    app()
