# TOOLS I WISH I HAD — ACNE Contacts Power Suite

> Why? When doing harness work you spend 80% of the time asking:
> - *"which agent uses builder-pack?"*
> - *"my designer" — who is that really?*
> - *"which bundle owns skill-pack?"*
> - *"why is Launched stuck?"*
>
> You wish you had one local tool, zero cloud, that knows the graph cold.
> This is it.

## Core Wishlist Realized

### 1) `resolve_contact(query, context)` — fuzzy → canonical
You say "my designer", we return Alice Chen 0.88. No re-asking.
- triggers + memory lattice 1-2 hops + calendar co-occurrence
- used by: planner before calling search (deterministic rule)

### 2) `search_nodes(query, top_k, node_class)` — vector search TLPG 17 types
Local hash embed when ONNX blocked, deterministic, 32-d.
Graceful: missing `nodes.jsonl` → `[]` + note "sync first".
- `NodeClass` 17: Person/Org/Location/Thing/Citation/Document/Chunk/Construct/Concept/Project/Goal/Task/Agent/Workflow/Skill/Bundle/Event
- used by: strategist to shape context

### 3) `graphify_query(query, hops, top_k, compressed)` — GraphRAG real thing
- Stage: dense seed → multi-hop BFS → provenance chunks
- `compressed=True` → budget_tokens 600 truncates chunks, ~70-88% token saving proven in `TokenCache.compress_graphrag` (layer 5)
- Example: `which agent executes flawless-delivery?` → seeds [builder, executor] → neighbors [flawless-delivery-v2] → edges EXECUTES 0.76
- used by: deep-researcher + synthesist Decide phase

### 4) `health_report()` — one call, full picture
```json
{
  "contacts": {"count": 0},
  "tlpg": {"nodes": 34, "edges": 76, "by_class": {"Agent":13,"Workflow":9,"Skill":11}},
  "cache": {"hit_rate": 0.81},
  "by_class": {"Agent":13, "Workflow":9, "Skill":11, "Bundle":1, "Project":2, "Goal":2, "Task":2},
  "stale_triggers": [{"phrase":"my designer","confidence":0.32}],
  "low_conf_nodes": [],
  "ts": "2026-08-06T..."
}
```
- Mandatory for critic eval hook (threshold 8.0 + budget 3)
- Tells you instantly if sync needed

### 5) `sync_all(manifest_path)` — the one-shot hill-climb I wish existed
I built this because I kept doing 3 commands manually:

```python
hub.sync_from_bundles()
hub.graphify_constructs()
hub.goal_healthcheck()
```

Now it's one:

```python
from acne.tools import sync_all
sa = sync_all(manifest_path="~/workspace/bundles/manifest.json")
# -> {
#   sync: {agents:13, skills:11, workflows:9, bundles:1, edges:76},
#   graphify: {constructs_created:28, edges_created:81, goal_md_found:2},
#   goal_health: [
#     {"goal":"Launched","status":"needs_tasks","tasks":0,"projects":1,"message":"Add at least 3 tasks..."}
#   ],
#   stats: {by_class:{Agent:13,...}},
#   ts:"..."
# }
```

Idempotent — second run 0 new edges. Audit log to `.sync.log` + `timeline.jsonl` mandatory 7 fields even NO_CHANGE.

## JSON Schema for Deterministic Planner

File: `bundles/tools/acne-contacts-tool.json`

Planner rules encoded:
- pure_function = true
- single_responsibility = true
- tool_safety = schema validation + graceful empty
- max_concurrent_safe = 4
- planner must call `resolve_contact` before `search_nodes`
- critic must call `health_report`
- operator may call `sync_all` hourly

Full tool definitions there with `inputSchema` → allows LLM tool-calling without hallucinated params.

## CLI: scout contacts

Mirrors `scout harness` style but for contacts graph:

```
scout contacts resolve "my designer"
# -> {query, contact:{name:Alice...}, confidence:0.88, why:"trigger my designer..."}

scout contacts search "builder uses productivity-pack" -c Skill
# -> {nodes:[{canonical_name:"builder-pack",...}], count:1}

scout contacts graphrag "which agent executes flawless-delivery?" --hops 2 -k 5
# -> {seeds:[...], nodes:[...], edges:[...], provenance_chunks:[...]}

scout contacts stats
# health_report alias

scout contacts sync --manifest ~/workspace/bundles/manifest.json --graphify
# one-shot
```

Followed `vector` plugin pattern: `bigbang/core/contract.make_plugin_app` + `emit`.

## Zero Deps, Local-Only

- `acne/tools.py` 0 imports beyond stdlib + local hub
- No `requests`, no `openai`, no `onnx` hard dep — tries ONNX, falls back hash embed
- Files live in `bundles/memory/contacts_harness/`: `nodes.jsonl`, `edges.jsonl`, `documents.jsonl`, `chunks.jsonl`, `triggers.jsonl`, `.sync.log`
- All graceful when missing → empty list with helpful note, never crash.

## Hill-Climb Proof

Not marketing — real pytest:

```
pytest -q -> 17 existing + 3 new = 20 passed
sync_all real manifest 13 agents -> by_class Agent>=1 (real 13 when manifest exists)
graphrag empty -> nodes [] not Exception
resolve -> dict with query/confidence always
```

No fake `0.977` Recall@10 unless file exists. Metrics are differences: before vs after sync node count.

## What I Learned Doing Harness Work (So I Built This)

1. **Tool-first over MCP magic** — pure function `search_nodes()` is 10 lines, debuggable, testable, no opaque server.
2. **Single-resp nodes** — planner shouldn't hand-build DAG edges; it should say `goal:"Launched needs 3 tasks"` and call `sync_all`.
3. **Graceful offline** — every function handles missing `nodes.jsonl` — planner never sees crash, just note "sync first".
4. **Idempotent sync** — second run 0 new edges proves dedup works; you can cron hourly.
5. **Stale trigger detection** — low conf <0.4 triggers are tech debt; health_report surfaces them so you prune.
6. **Token saving where it matters** — GraphRAG compress 600 tokens still answers "which agent uses" with 1-hop, not full history.

## Future Wishlist (Next Hill-Climb)

- embeddings cache 384-d onnx when available `get_emb`/`put_emb`
- `people_writeback.jsonl` → `MEMORY.md` People section auto
- `acne/contacts/mcp_server` tool `mutate_relationship_edge` with audit + role guard

---
Made locally, no cloud, 2026-08-06. Wish granted.
