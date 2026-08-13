"""
sync_bundles.py — Live Sync from bundles/manifest.json → TLPG constructs
Zero-deps, local-first, idempotent.

Loads workspace/bundles/manifest.json (13 agents, 11 packs, 3+5 workflows)
and mirrors them into TLPG as Agent / Workflow / Skill / Bundle nodes.

Dedup by canonical_name + node_class (not random id).
Links:
  Agent USES Skill (from manifest agents[].skills)
  Bundle OWNS Skill (bundle owns all skill_packs)
  Agent EXECUTES Workflow (simple role-based heuristic)
  Workflow COMPOSED_OF Workflow (ultra-orchestrator composed of phases)

Writes audit to contacts_harness/.sync.log (creates dir if needed).

Usage:
  from acne.sync_bundles import sync_from_manifest
  sync_from_manifest(tlpg_store, manifest_path)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import hashlib
import os
from datetime import datetime, timezone

def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def _load_manifest(manifest_path: Path) -> Dict[str, Any]:
    p = Path(manifest_path).expanduser()
    if not p.exists():
        # try workspace/bundles/manifest.json fallback
        alt = Path.home() / "workspace" / "bundles" / "manifest.json"
        if alt.exists():
            p = alt
        else:
            raise FileNotFoundError(f"manifest not found at {manifest_path} or {alt}")
    return json.loads(p.read_text())

def _find_or_make_node(tlpg_store, name: str, node_class: str, maker_fn, **attrs):
    """Dedup by canonical_name.lower() + node_class. Update if exists, else create."""
    existing = None
    # list_nodes may be expensive but okay for 100s nodes
    for n in tlpg_store.list_nodes(node_class=node_class):
        if n.canonical_name.lower() == name.lower():
            existing = n
            break
    if existing:
        # merge attributes (new overwrites but keep old not colliding)
        merged = {**existing.attributes, **attrs}
        existing.attributes = merged
        # bump confidence / source to sync
        existing.source = "sync_bundles"
        existing.tx_time = _now_iso()
        tlpg_store.upsert_node(existing)
        return existing, False  # False = not new
    else:
        node = maker_fn(name, **attrs)
        # ensure source marking
        node.source = "sync_bundles"
        tlpg_store.upsert_node(node)
        return node, True

def _add_edge_once(tlpg_store, src_id: str, dst_id: str, edge_type: str, confidence: float = 0.78, props: Dict[str, Any]=None):
    from .models import TLPGEdge
    # cheap dedup check
    for e in tlpg_store.list_edges(edge_type=edge_type):
        if e.source_id == src_id and e.target_id == dst_id:
            # bump confidence if higher
            if confidence > e.confidence:
                e.confidence = confidence
                tlpg_store.add_edge(e)
            return e, False
    edge = TLPGEdge(source_id=src_id, target_id=dst_id, edge_type=edge_type, confidence=confidence, properties=props or {}, source="sync_bundles")
    tlpg_store.add_edge(edge)
    return edge, True

def sync_from_manifest(tlpg_store, manifest_path: str | Path = None, base_for_log: Path = None) -> Dict[str, Any]:
    """
    Main sync entry. Returns dict {agents, workflows, skills, bundles, edges, ...}
    """
    if manifest_path is None:
        # default workspace location
        manifest_path = Path.home() / "workspace" / "bundles" / "manifest.json"
    else:
        manifest_path = Path(manifest_path).expanduser()

    data = _load_manifest(manifest_path)

    from .models import (
        make_agent_node, make_workflow_node, make_skill_node, make_bundle_node,
        make_edge
    )

    agents_src = data.get("agents", [])
    skill_packs_src = data.get("skill_packs", [])
    workflows_src = data.get("workflows", [])
    ultra_wfs = data.get("ultra_components", {}).get("workflows", []) or data.get("v3_3_components", {}) and []  # fallback empty
    # v3_3_components doesn't have workflow list; use ultra_components
    if not ultra_wfs:
        ultra_wfs = data.get("ultra_components", {}).get("workflows", [])

    # for v3_3, also look inside ultra_components.workflows (5 items) already covered
    all_wf_src = []
    # normalize
    for wf in workflows_src:
        if isinstance(wf, dict):
            all_wf_src.append(wf)
    for wf in ultra_wfs:
        if isinstance(wf, dict) and wf not in all_wf_src:
            # avoid duplicate ids
            if wf.get("id") not in [x.get("id") for x in all_wf_src]:
                all_wf_src.append(wf)

    # storage
    created_agents = []
    updated_agents = []
    created_skills = []
    updated_skills = []
    created_workflows = []
    updated_workflows = []
    created_bundles = []
    edges_made = []

    # --- 1) Skills first (needed for Agent USES, Bundle OWNS) ---
    skill_nodes_by_id: Dict[str, Any] = {}
    for pack in skill_packs_src:
        pid = pack.get("id") or pack.get("file") or "unknown-pack"
        # strip path
        name = pid
        use = pack.get("use","")
        for_agents = pack.get("for_agents", [])
        # also include pack like router-pack
        attrs = {"pack": pid, "use_for": use, "version": data.get("version",""), "file": pack.get("file","")}
        if for_agents:
            attrs["for_agents"] = for_agents
        # attrs already has pack; avoid duplicate kwarg
        packed = attrs.pop("pack", name)
        node, is_new = _find_or_make_node(tlpg_store, name, "Skill", lambda n, **kw: make_skill_node(n, pack=packed, confidence=0.78, **kw), **attrs)
        # restore for future use if needed (not essential)
        attrs["pack"] = packed
        skill_nodes_by_id[pid] = node
        if is_new:
            created_skills.append(pid)
        else:
            updated_skills.append(pid)

    # --- 2) Agents ---
    agent_nodes_by_id: Dict[str, Any] = {}
    for ag in agents_src:
        aid = ag.get("id") or ag.get("file") or "unknown-agent"
        role = ag.get("role","")
        layer_raw = ag.get("layer", 3)
        try:
            layer = int(layer_raw)
        except:
            # handle "2-3"
            try:
                layer = int(str(layer_raw).split("-")[0])
            except:
                layer = 3
        skills = ag.get("skills", [])
        attrs = {
            "role": role,
            "layer": layer,
            "file": ag.get("file",""),
            "always_on": ag.get("always_on", False),
            "v3_2": ag.get("v3_2","") or ag.get("v3_1",""),
        }
        if skills:
            attrs["packs"] = skills
        # clean empty
        attrs = {k:v for k,v in attrs.items() if v not in ("", [], None)}
        node, is_new = _find_or_make_node(tlpg_store, aid, "Agent", lambda n, **kw: make_agent_node(n, role=kw.get("role",""), layer=int(kw.get("layer",3)), confidence=0.82, **{k:v for k,v in kw.items() if k not in ("role","layer")}), **attrs)
        agent_nodes_by_id[aid] = node
        if is_new:
            created_agents.append(aid)
        else:
            updated_agents.append(aid)

    # --- 3) Workflows ---
    wf_nodes_by_id: Dict[str, Any] = {}
    for wf in all_wf_src:
        wid = wf.get("id") or wf.get("file") or "unknown-wf"
        desc = wf.get("use_for") or wf.get("description") or ""
        phases = 0
        if "phases" in wf:
            try:
                phases = int(wf["phases"])
            except:
                phases = 0
        attrs = {"description": desc[:240], "file": wf.get("file",""), "phases": phases, "version": data.get("version","")}
        if wf.get("layer"):
            attrs["layer"] = wf["layer"]
        if wf.get("entry"):
            attrs["entry"] = wf["entry"]
        attrs = {k:v for k,v in attrs.items() if v not in ("", 0, None) or k=="phases"}  # keep phases if 0? remove
        # if phases 0 remove to keep clean
        if attrs.get("phases")==0:
            attrs.pop("phases", None)
        node, is_new = _find_or_make_node(tlpg_store, wid, "Workflow", lambda n, **kw: make_workflow_node(n, confidence=0.77, **kw), **attrs)
        wf_nodes_by_id[wid] = node
        if is_new:
            created_workflows.append(wid)
        else:
            updated_workflows.append(wid)

    # --- 4) Bundle ---
    bundle_name = data.get("name") or "Scout Execution Bundle"
    bundle_version = data.get("version") or "3.3"
    bundle_attrs = {
        "version": bundle_version,
        "agents_count": data.get("agents_count", len(agents_src)),
        "packs_count": data.get("packs_count", len(skill_packs_src)),
        "for": data.get("for",""),
        "by": data.get("by",""),
    }
    bundle_node, is_new_bundle = _find_or_make_node(tlpg_store, bundle_name, "Bundle", lambda n, **kw: make_bundle_node(n, confidence=0.85, **kw), **bundle_attrs)
    created_bundles = [bundle_name] if is_new_bundle else []

    # --- 5) Edges: Agent USES Skill ---
    for ag in agents_src:
        aid = ag.get("id")
        if not aid or aid not in agent_nodes_by_id:
            continue
        src_node = agent_nodes_by_id[aid]
        for sk in ag.get("skills", []):
            if sk in skill_nodes_by_id:
                dst = skill_nodes_by_id[sk]
                _, is_new = _add_edge_once(tlpg_store, src_node.id, dst.id, "USES", confidence=0.80, props={"from_manifest": True})
                if is_new:
                    edges_made.append(f"{aid} USES {sk}")

    # --- 6) Bundle OWNS Skill ---
    for pid, snode in skill_nodes_by_id.items():
        _, is_new = _add_edge_once(tlpg_store, bundle_node.id, snode.id, "OWNS", confidence=0.84, props={"bundle": bundle_name})
        if is_new:
            edges_made.append(f"{bundle_name} OWNS {pid}")

    # --- 7) Agent EXECUTES Workflow (role-based heuristic) ---
    # Mapping kept simple and deterministic
    exec_map: Dict[str, List[str]] = {
        "scout-prime": [wf.get("id") for wf in all_wf_src],  # prime does all
        "strategist": ["ultra-orchestrator", "flawless-delivery-v2", "intent-decomposer", "dynamic-planner"],
        "planner": ["ultra-orchestrator", "dynamic-planner", "flawless-delivery-v2"],
        "executor": ["layer-executor", "flawless-delivery-v2", "ultra-orchestrator", "flawless-delivery"],
        "researcher": ["ultra-orchestrator", "dynamic-planner", "flawless-delivery-v2"],
        "deep-researcher": ["ultra-orchestrator", "dynamic-planner"],
        "synthesist": ["ultra-orchestrator", "adaptive-critic", "flawless-delivery-v2"],
        "builder": ["flawless-delivery", "flawless-delivery-v2"],
        "communicator": ["flawless-delivery", "inbox-to-action"],
        "operator": ["monitor-and-notify", "inbox-to-action", "flawless-delivery-v2"],
        "action-operator": ["inbox-to-action", "monitor-and-notify", "flawless-delivery"],
        "critic": ["adaptive-critic", "ultra-orchestrator", "flawless-delivery-v2"],
        "forensic-auditor": ["adaptive-critic", "ultra-orchestrator"],
    }

    for aid, allowed_wfs in exec_map.items():
        if aid not in agent_nodes_by_id:
            continue
        src = agent_nodes_by_id[aid]
        for wid in allowed_wfs:
            if wid in wf_nodes_by_id:
                dst = wf_nodes_by_id[wid]
                _, is_new = _add_edge_once(tlpg_store, src.id, dst.id, "EXECUTES", confidence=0.76, props={"heuristic":"role-map"})
                if is_new:
                    edges_made.append(f"{aid} EXECUTES {wid}")

    # Also: if role text mentions workflow name, add
    for ag in agents_src:
        aid = ag.get("id")
        if not aid or aid not in agent_nodes_by_id:
            continue
        role_txt = (ag.get("role","") + " " + str(ag.get("v3_2",""))).lower()
        for wid, wnode in wf_nodes_by_id.items():
            if wid.replace("-"," ") in role_txt or wid in role_txt:
                _, is_new = _add_edge_once(tlpg_store, agent_nodes_by_id[aid].id, wnode.id, "EXECUTES", confidence=0.70, props={"heuristic":"role-mention"})
                if is_new:
                    edges_made.append(f"{aid} EXECUTES {wid} (role mention)")

    # --- 8) Workflow COMPOSED_OF Workflow (ultra orchestrator phases) ---
    # ultra-orchestrator owns its 4 child workflows
    if "ultra-orchestrator" in wf_nodes_by_id:
        parent = wf_nodes_by_id["ultra-orchestrator"]
        for child_id in ["intent-decomposer", "dynamic-planner", "layer-executor", "adaptive-critic"]:
            if child_id in wf_nodes_by_id:
                _, is_new = _add_edge_once(tlpg_store, parent.id, wf_nodes_by_id[child_id].id, "COMPOSED_OF", confidence=0.82, props={"orchestration": True})
                if is_new:
                    edges_made.append(f"ultra-orchestrator COMPOSED_OF {child_id}")

    # --- audit log ---
    try:
        if base_for_log is None:
            # try default contacts_harness base
            base_for_log = Path.home() / "workspace" / "bundles" / "memory" / "contacts_harness"
        base_for_log = Path(base_for_log).expanduser()
        base_for_log.mkdir(parents=True, exist_ok=True)
        log_path = base_for_log / ".sync.log"
        entry = {
            "at": _now_iso(),
            "manifest": str(manifest_path),
            "manifest_mtime": os.path.getmtime(manifest_path) if manifest_path.exists() else None,
            "agents_new": len(created_agents),
            "agents_updated": len(updated_agents),
            "skills_new": len(created_skills),
            "workflows_new": len(created_workflows),
            "bundles": 1 if is_new_bundle else 0,
            "edges_new": len(edges_made),
            "by": "sync_bundles"
        }
        with log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    return {
        "agents": len(agent_nodes_by_id),
        "agents_new": len(created_agents),
        "agents_updated": len(updated_agents),
        "workflows": len(wf_nodes_by_id),
        "workflows_new": len(created_workflows),
        "skills": len(skill_nodes_by_id),
        "skills_new": len(created_skills),
        "bundles": 1,
        "bundles_new": len(created_bundles),
        "edges": len(edges_made),
        "edges_created_list": edges_made[:50],
        "stats": tlpg_store.stats(),
    }
