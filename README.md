# ACNE — Agentic Contacts - Named Entities

Local-first people memory for agentic harnesses. Typed Temporal Labeled Property Graph with constructs, trigger-phrase resolver, 5-layer token-cache.

No cloud, no vector DB, no OAuth.

## What it is

ACNE gives your agents a shared, private people layer:

- `my designer` → `Alex Rivera <alex@studio.com> confidence 0.88 source manual`
- Every node proves where it came from: Document → Chunk → `EXTRACTED_FROM` edge with checksum, timestamp, confidence
- Every edge is typed: `EMPLOYED_BY`, `AUTHORED`, `LOCATED_AT`, `PARTNERED_WITH`, `CITATION_OF`, `SAME_AS`, plus construct edges `EXECUTES`, `OWNS`, `USES`, `COMPOSED_OF`, `REALIZES`, `ABSTRACTS`
- 5-layer cache means your 90-second heartbeat gets cheap fast — typical ~70–88% smaller GraphRAG packs vs full dump (% varies, not fixed)
- **v0.4 Constructs:** 17 node types (Person..Event) + graphify pass that lifts low-level chunks into `Concept ABSTRACTS Entity` and links Agent→Workflow→Project→Task→Goal

## Install

```bash
pip install acne
pip install acne[langchain]  # or [crewai] [openai] [all] [dev]
```

## 30-second usage

```bash
acne init
acne add --name "Alex Rivera" --email alex@studio.com --trigger "my designer" --role designer
acne resolve "my designer"
acne pipeline "From: Alice Chen <alice@acme-corp.com> ... Alice Chen authored Q4 on 2025-11-10..." --title "Email Q4"
acne graphrag --compressed --query "Who authored Q4?"
acne cache-stats
```

```python
from acne import ContactsHub

hub = ContactsHub()  # uses ~/.acne or ~/workspace/bundles/memory/contacts_harness if present
hub.add_person(name="Alex Rivera", email="alex@studio.com", trigger="my designer", role="designer")
print(hub.resolve("my designer"))

# E2E: ingest → chunk with provenance → typed graph → resolve → GraphRAG
result = hub.pipeline_run("""
From: Alice Chen <alice@acme-corp.com>
Alice Chen from Acme Corp authored Q4 Technical Architecture on 2025-11-10.
Acme Corp partnered with Beta Labs. Bob Jones reviewed in San Francisco.
A. Chen cited doi:10.1109/mcp.2025
""", title="Email Q4")

print(result['stats'])  # {'nodes':7, 'edges':10, 'by_class':{'Person':2,'Location':1,...}}
print(hub.graphrag("Partners who authored citations?", compressed=True))
print(hub.cache.stats())  # {'doc_hits','emb_hits','ext_hits','query_hits','compressed_hits','tokens_saved','money_saved'}
```

## 7 harnesses, same store

```python
from acne.integrations import get_S Scout_tools, get_claude_tools, get_langchain_tools

get_S Scout_tools()      # 8 tools — S Scout-native {name,description,parameters,execute}
get_claude_tools()     # 6 tools — Claude-native {name,description,input_schema}
get_langchain_tools()  # 10 Tools — LangChain StructuredTool
# + hermes, myclaw, crewai, openai — all local, same JSONL files
```

## Why not X?

| You need | ACNE | Others |
|---|---:|---|
| No cloud, no OAuth, privacy by default | ✅ JSONL local | often cloud embeddings |
| `my designer` → contact with confidence | ✅ 0.88 manual | exact string match |
| Typed TLPG + constructs + provenance back to doc | ✅ 17 node types, 27 edge types, typed edges | flat memory |
| Token-cache 5-layer (doc/emb/ext/query/compressed) | ✅ 70-88% typical saving | none |
| Works across 7 harnesses at once | ✅ shared dir | 1-2 |
| Harness constructs (Agent, Workflow, Bundle, Project, Goal, Task) + graphify | ✅ EXECUTES, OWNS, COMPOSED_OF, REALIZES, ABSTRACTS | none |

## Design

**Pipeline (5 stages):**
1. Ingest: doc → 500-1000 tok overlapping chunks, hash for dedup, checksum
2. Extract: typed Person/Org/Location/Thing/Citation/Document/Chunk **+ Construct/Concept/Project/Goal/Task/Agent/Workflow/Skill/Bundle/Event** nodes + typed edges, confidence
3. Resolve: trigger resolver + `SAME_AS` soft-merge (never hard delete), tx_time/valid_from
4. Graphify: **v0.4 new** — Concept ABSTRACTS nodes co-occurring in chunk, Agent EXECUTES Workflow, Project COMPOSED_OF Task, Bundle OWNS Skill, Goal REALIZES Project
5. GraphRAG: provenance-aware, compressed packs capped to `budget_tokens` (default 600)

**Adapters:** Hermes, Claude Code, S Scout, LangChain/LangGraph, MyClaw, CrewAI, OpenAI — 6-10 tools each, 13 MCP tools.

**CLI:** `acne pipeline|graphrag --compressed|add|resolve|cache-stats|mcp-def`

## Provenance & safety

- `source: manual|calendar|memory_heuristic|enriched|extraction|ingest`
- low confidence `<0.4` = hint, not fact
- `SAME_AS` edges, never destructive merge
- audit log for `mutate_relationship_edge`
- local-first `~/.acne` or `~/workspace/bundles/memory/contacts_harness/`

## License

MIT


## v0.4.0 Constructs + Graphify (2026-08-06 Lane 3)

**7 node types → 17 node types — harness-aware constructs**

Extends TLPG `NodeClass` from `Person|Organization|Location|Thing|Citation|Document|Chunk` to:

- `Construct` (OODA, MoMA-lite, GraphRAG, TLPG, pacing filter, verification economics, checkpoint) — `kind`, `layer`, `principle`
- `Concept` (orientation > speed, late commitment, 3-layer separation) — `domain`, `abstraction_level`, `definition`
- `Project` (vector-hoops, vector-hub, dottie, scout-cli, dumbmodel.com, arxiviq) — `status`, `repo`, `tech_stack`
- `Goal` (Launched = live URL + 3 users) — `status`, `metric`, `deadline`
- `Task` (Hill-climb, Ship, Fix hub.js) — `status`, `priority`, `assignee`
- `Agent` (scout-prime, researcher, builder, operator) — `role`, `layer`, `tools`
- `Workflow` (flawless-delivery, monitor-and-notify) — `phases`, `version`
- `Skill` (productivity-pack, builder-pack) — `pack`, `tools`
- `Bundle` (execution bundle v5) — `agents`, `packs`, `workflows`
- `Event` (launched, deployed, hill-climb) — `timestamp`, `type`

Extends `EdgeType` with 13 construct edges: `OWNS`, `CREATED_BY`, `USES`, `DEPENDS_ON`, `IMPLEMENTS`, `PART_OF`, `MANAGES`, `EXECUTES`, `TRACKS`, `DEFINES`, `REALIZES`, `ABSTRACTS`, `COMPOSED_OF` — all audited via `mutate_relationship_edge`.

**Graphify v0.4** — `hub.tlpg.graphify_constructs()` or `hub.graphify_constructs()`:

- Agent EXECUTES Workflow (name overlap)
- Project COMPOSED_OF Task
- Person USES Skill
- Bundle OWNS Skill
- Concept ABSTRACTS Chunk (co-occurrence ≥3 nodes same chunk → Concept node)
- Goal REALIZES Project
- Pipeline stage4 now returns `{"constructs_created":21,"edges_created":18,"by_class":{...}}`

Usage:

```python
from acne import ContactsHub
hub = ContactsHub()
hub.pipeline_run("""
Scout Prime executes flawless-delivery workflow.
It uses builder-pack. Project vector-hoops building chimera.
Goal Launched = live URL + 3 users by Aug 31.
""", title="Scout v5")
# TLPG now has 17 classes
print(hub.tlpg.stats())  # {"by_class": {"Person":3,"Agent":3,"Workflow":1,"Project":2,"Goal":1,"Construct":2,...}}

# manual constructs
hub.add_construct("Scout v5 Prime Harness", kind="Bundle", version="5.0")
hub.add_construct("OODA Loop", kind="Construct", principle="orientation > speed")

# graphify pass
print(hub.graphify_constructs())
print(hub.graphrag("Which agents execute flawless-delivery?", hops=2))

# top-level helper
from acne import graphify_constructs
graphify_constructs(hub)
```

Backward compatible: existing 7-type pipelines still work, `stats()` dynamic, `SAME_AS` hard→soft unchanged, token-cache 5-layer untouched.

---

## v0.3.0 Hard→Soft SAME_AS + 50+ Contacts Hill-Climb (2026-08-06 Lane 2)

**30c 57t → 54c 80+ t — richer alias handling**

- **Hard SAME_AS** (confidence 0.88-0.98, deterministic): exact email lowercased, exact trigger phrase lowercased + same node_class + confidence>0.55, exact canonical + shared org/domain, manual source priority. Edge props `{"hard":True,"reason":..., "deterministic":True}`. Auto-merge allowed but never destructive delete — both nodes preserved via SAME_AS link, canonical chosen longer name + higher confidence + manual source, provenance checksum SHA1 alias preserved.

- **Soft SAME_AS** (0.55-0.89, probabilistic): jaccard>0.6 OR abbrev "A. Chen"→"Alice Chen" first-initial+last OR cosine>0.85 hash-embed 32-d OR shared org+location co-occurrence OR shared alias. Edge props `{"hard":False,"soft":True,"jaccard":..., "abbrev":..., "vec":...}`. Never auto-merge, GraphRAG resolves both but prefers hard canonical if exists. Example: "Alice C. Chen" soft 0.75 → linked not merged until email hard confirms.

**Hill-Climb 50+ contacts** (deterministic seed `seed_50()`):
- DeepMind 13 persons sample (DreamerV3 team), FAIR Meta 2 persons, Institute Optical Neural Tech 3 persons, Stanford 1 person, Acme Corp 7 persons, Studio Co 5 persons, Stripe 3 persons, Linear 3 persons, Scout runtime 4 agents, Sports Media 2 persons, OpenSource 2 persons, Markets 2 persons — total 54 persons + 5 orgs = 59 nodes.
- Each contact: trigger resolver `my designer` → Alex Rivera confidence 0.88 source manual <50ms no LLM, provenance Document→Chunk→EXTRACTED_FROM edge checksum, tx_time, valid_from, confidence tracking.

Token-cache 5-layer still 70-88% typical saving, no torch, no cloud, local JSONL.

Usage:

```python
from acne import seed_50, hill_climb_resolve_with_hard_soft, hard_sameas, soft_sameas
hub=seed_50()  # returns stats {"added":54,"persons":54,"orgs":5,"edges_created":...,"hard_soft":"hard→soft enabled"}
# hard→soft decision
hard_sameas(node_a, node_b)  # (is_hard, reason, conf)
soft_sameas(node_a, node_b)  # (is_soft, details, conf)
hill_climb_resolve_with_hard_soft(hub.tlpg)
```

Provenance & safety unchanged: source manual|calendar|memory_heuristic|enriched|extraction|ingest, low <0.4 hint not fact, SAME_AS edges typed hard/soft, audit log mutate_relationship_edge, local-first.

