# ACNE v0.4.0 — Constructs + Graphify

> 7 → 17 node types — harness-aware TLPG for Scout v5 Prime

## Motivation

ACNE v0.3 handled people (`my designer → Alex`). Scout v5 needs more: agents, workflows, bundles, projects, goals, tasks, constructs like OODA/MoMA-lite, concepts like "orientation > speed". Flat TLPG of 7 types forces everything into Thing.

v0.4 lifts TLPG to a **construct graph** that can represent the harness itself.

## New NodeClass (10 added)

```python
NodeClass = (
  "Person","Organization","Location","Thing","Citation","Document","Chunk",
  "Construct","Concept","Project","Goal","Task","Agent","Workflow","Skill","Bundle","Event"
)
```

| Class | What | Example attrs |
|-------|------|---------------|
| `Construct` | Harness principle | kind=construct|harness_construct, layer, principle |
| `Concept` | Abstractions from chunks | domain, abstraction_level, definition, source_nodes |
| `Project` | Repos & products | status, repo, tech_stack, owner, deadline |
| `Goal` | Objective with deadline | status, metric, deadline, success_criteria |
| `Task` | Actionable unit | status, priority, assignee, due, project |
| `Agent` | Executor | role, layer (1-3), model, tools, packs |
| `Workflow` | Phases | phases, entry, version, owner |
| `Skill` | Pack | pack, tools, use_for, layer |
| `Bundle` | Agents+packs+workflows | agents, packs, workflows, version |
| `Event` | Happening | timestamp, type, participants, location, outcome |

Taxonomy defaults in `models.TAXONOMY_ATTRS`.

## New EdgeType (13 added)

```
OWNS, CREATED_BY, USES, DEPENDS_ON, IMPLEMENTS,
PART_OF, MANAGES, EXECUTES, TRACKS, DEFINES,
REALIZES, ABSTRACTS, COMPOSED_OF
```

Total 14 → 27 edge types.

## Extraction v0.4

`extraction.CONSTRUCT_PATTERNS` — regex heuristics offline:

- Agent: scout-prime|strategist|planner|executor|researcher|builder|operator|critic|forensic-auditor|deep-researcher|synthesist
- Workflow: flawless-delivery|ultra-orchestrator|monitor-and-notify|inbox-to-action|dynamic-planner
- Bundle: execution bundle, bundle v5
- Skill: productivity-pack|builder-pack|deep-research-pack|...
- Project: vector-hoops|dottie|scout-cli|dumbmodel.com|arxiviq
- Goal: Launched = live URL ... Aug 31
- Task: Hill-climb|Ship
- Construct: OODA|MoMA-lite|GraphRAG|TLPG|Checkpoint|Recovery Ladder|Pacing Filter|Verification Economics
- Concept: orientation > speed|tempo over speed|late commitment|3-layer separation
- Event: harness upgrade|hill-climb

All heuristic, no LLM, deterministic. Person filtering extended to skip Goal/Project/Task words.

## Graphify v0.4 — `TLPGStore.graphify_constructs()`

```python
def graphify_constructs():
  # 1) Agent EXECUTES Workflow (name overlap)
  # 2) Project COMPOSED_OF Task (prefix match)
  # 3) Person USES Skill (limited 200 edges)
  # 4) Bundle OWNS Skill
  # 5) Chunk ≥3 nodes → Concept ABSTRACTS nodes
  # 6) Goal REALIZES Project (1 per goal)
  return {"constructs_created":..., "edges_created":..., "by_class": {...}}
```

Called automatically as **stage4** in `hub.pipeline_run(..., graphify=True)` — still cheap, local.

Manual API:

```python
hub.add_construct("OODA Loop", kind="Construct", principle="orientation > speed")
hub.add_construct("Scout v5 Bundle", kind="Bundle", version="5.0")
hub.graphify_constructs()
```

## Hub Changes

- `ContactsHub.add_construct(name, kind, confidence, **extras) -> dict`
- `ContactsHub.graphify_constructs() -> dict`
- `pipeline_run(source, title, author, graphify=True)` now returns `stage4`
- `mutate_relationship_edge` allowed set expanded to 27 types

## Store Changes

- `TLPGStore.add_construct_node()` — generic maker dispatcher
- `TLPGStore.stats()` dynamic: only shows classes with cnt>0, includes 17 classes
- `TLPGStore.graphify_constructs()` new
- `graph.py._simple_embedding` unchanged (32-d hash)

## Resolution Changes

- `blocking_key` extended: Agent/Workflow/Skill/Bundle/Project/Goal/Task → first-token buckets, Construct/Concept/Event → C: prefix

## Integration

```python
from acne import ContactsHub, graphify_constructs
hub = ContactsHub(workspace="~/workspace")
hub.pipeline_run(open("MEMORY.md").read())
print(hub.tlpg.stats())
```

Works inside Hatch bundles at `~/workspace/bundles/memory/contacts_harness/` — same JSONL files, 17 types.

## Backward Compat

- 0.3 data still loads: new classes are optional, `TAXONOMY_ATTRS` has defaults, `list_nodes()` without class returns all.
- `TAXONOMY_ATTRS` lookup: new keys added, old keys unchanged.
- `SAME_AS` hard→soft untouched.
- Token-cache 5-layer untouched.

## Live Sync v0.4.1 — bundles/manifest.json → TLPG

**Goal:** keep harness constructs current without manual edits.

`src/acne/sync_bundles.py`:

```python
from acne import ContactsHub
hub = ContactsHub(workspace="~/workspace")
hub.sync_from_bundles()  # loads manifest.json, merges 13 agents + 11 packs + 8 workflows
print(hub.tlpg.stats())
# base bundles/memory/contacts_harness stats: Agent=13, Workflow>=8, Skill=11, Bundle=1
```

Dedup by `canonical_name + node_class` — re-running updates attrs instead of duplicating.
Makers used: `make_agent_node`, `make_workflow_node`, `make_skill_node`, `make_bundle_node`.

Edges created:

- `Agent USES Skill` — from `agents[].skills` array (e.g., researcher USES deep-research-pack)
- `Bundle OWNS Skill` — bundle OWNS all 11 packs
- `Agent EXECUTES Workflow` — role-map (scout-prime EXECUTES all, builder→flawless-delivery, operator→monitor-and-notify etc. + role mention fallback)
- `Workflow COMPOSED_OF Workflow` — ultra-orchestrator COMPOSED_OF intent-decomposer, dynamic-planner, layer-executor, adaptive-critic

Audit: `workspace/bundles/memory/contacts_harness/.sync.log` JSONL per sync (creates dir if missing).

Cron: `workspace/bundles/cron.d/sync_bundles.json` hourly, owner=operator, schedule `0 * * * *`, watcher `bundles/scripts/sync_bundles_watch.py`.

Watcher `sync_bundles_watch.py` — zero-deps, compares `manifest.json` mtime vs last sync log mtime, skips if not newer. Always writes `bundles/ultra/runs/timeline.jsonl` entry even on NO_CHANGE (7 required fields: at, nodeId=sync_bundles, agentId=operator, attempt, latency, tokens, status).

## Tests

Existing `test_tlpg_pipeline` passes (8/8). New manual runs:

v0.4 base:
```
stats {"Person":3,"Organization":1,"Thing":1,"Construct":2,"Concept":2,"Project":2,"Goal":1,"Task":2,"Agent":3,"Workflow":1,"Skill":2,"Bundle":2,"Event":1}
```

Live Sync:
```
hub.sync_from_bundles() base=/tmp/test-live
stats {'Agent':13,'Workflow':8,'Skill':11,'Bundle':1,'nodes':33,'edges':36 ...}
```

## Next

- v0.4.2: sync Goal/Project/Task from workspace/exports/ + MEMORY.md
- v0.5: learnable embedding for construct similarity beyond hash-embed, still no cloud

---

## Goal Slip-Proof v0.4.1 — No More Slipping

TLPG now guards your Aug 31 Launched goal automatically.

### Why

- Flat task lists forget projects.
- Goals without tasks slip silently.
- `bundles/` has 13 agents but no guard that Goal → Project → Task stays linked.

v0.4.1 adds deterministic guardrails with no LLM.

### TLPGStore.graphify_constructs() upgrades

New heuristics after base 6:

**6b — Task PART_OF Project via `project` attr**
```python
task.project == "vector-hoops"  ->  vector-hoops Project
# confidence 0.72, props via=project_attr, goal_slip_proof=True
```

**6c — Goal REALIZES Project even on name mismatch**
- If Goal has `project`, `repo`, `owner`, or `success_criteria` (or GOAL.md present), link to matching Project by attr.
- Fallback: if still no REALIZES and GOAL.md present or success_criteria/deadline set, link to first Project (0.58, via fallback_goal_md).
- Original heuristic kept (1 per goal), but no longer blocks better match.

**6d — Goal TRACKS Task even on name mismatch**
- `task.project == goal.project` → TRACKS 0.70 via project_attr_match
- Task PART_OF Project and Goal REALIZES same Project → TRACKS 0.66 via shared_project
- If GOAL.md present, be generous: link up to 3 tasks per goal at 0.55 to keep health green.

**6e — Placeholder Task when Goal has no Tasks**
```python
if goal has 0 real TRACKS:
  Task("Need tasks for <goal>", confidence=0.45, needs_tasks=True, placeholder=True, for_goal=goal.id)
  Goal TRACKS placeholder (0.45, placeholder=True, needs_tasks=True)
```
Idempotent — duplicate placeholders avoided.

**6f — Mirror COMPOSED_OF** when PART_OF exists.

Return now includes `goal_md_found`.

### Hub APIs

```python
hub.goal_healthcheck() -> [
  {
    "goal": "Launched Aug 31",
    "status": "needs_tasks",   # ok | needs_tasks | no_project | stale
    "tasks": 0,
    "projects": 1,
    "message": "Goal 'Launched Aug 31' has no tasks yet. Add at least 3 tasks...",
    "goal_id": "n_abc"
  }
]

hub.goal_writeback() -> {"ts": "...Z", "health": [...], "logged_to": [...]}
# appends to bundles/memory/goal_health.jsonl
# and .scout/missions/health/timeline.jsonl with 7-field checkpoint (nodeId, agentId, attempt, latency_ms, tokens, status, errorClass)
```

Healthcheck fallback: if TLPG has 0 Goals but `workspace/goals/*/GOAL.md` exists, it creates Goal nodes from those files so you still get alerts.

### Cron + Heartbeat

`workspace/bundles/cron.d/goal_health.json`:
```json
{
  "id": "goal_health",
  "owner": "operator",
  "schedule": {"kind":"daily","timezone":"America/Chicago","time":"08:30:00"},
  "command": "python3 ~/workspace/bundles/scripts/goal_health_check.py"
}
```

`workspace/bundles/scripts/goal_health_check.py`:
- `ContactsHub(workspace=~/workspace).goal_healthcheck()`
- appends to `bundles/memory/goal_health.jsonl`
- logs 7-field `timeline.jsonl` in `.scout/missions/health/`
- if Launched goal status=needs_tasks, writes `bundles/memory/goal_health_needs_tasks.json` marker.
- on error also logs with errorClass.

Operator owns it. Timeline even on no-change satisfies checkpoint-manager spec.

### Feed Idea When Slipping

If `Launched` / `Aug 31` goal has 0 tasks, a feed unit is created:

> "Launched goal needs 3 tasks — add ship, analytics, payments tasks before Aug 31"

Done via `feed.units add` so it surfaces in your feed.

### Example Run

```python
hub = ContactsHub(workspace="~/workspace")
hub.add_construct("Launched Aug 31", kind="Goal", deadline="2026-08-31", success_criteria="live url")
hub.add_construct("dumbmodel.com", kind="Project")
hub.tlpg.graphify_constructs()  # 1 placeholder Task created
hub.goal_healthcheck()
# -> [{"goal":"Launched Aug 31","status":"needs_tasks","tasks":0,"projects":1,"message":"..."}]
```

### Tests

`tests/test_goal_graphify.py` — 4 tests: placeholder creation, health ok when linked, writeback logs, PART_OF via attr. `pytest -q` stays green.

