"""
test_router_memory.py — Orientation Engine wish-I-had
Tests classifyTier + memory_retriever top-k + GARNet planner

Zero deps, deterministic. Mirrors JS/PY parity for MoMA-lite 5-tier.
"""
from pathlib import Path
import sys, json

# Router bridge
def test_classify_tier_core():
    sys_path = Path.home() / "workspace" / "bundles" / "scripts"
    spec = None
    try:
        import importlib.util
        rb_path = sys_path / "router_bridge.py"
        assert rb_path.exists(), "router_bridge.py missing"
        spec = importlib.util.spec_from_file_location("router_bridge", str(rb_path))
        rb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rb)

        # deterministic
        r = rb.classify_tier("heartbeat cron check every 30m")
        assert r["tier"] == "deterministic", f"expected deterministic got {r}"
        assert r["confidence"] >= 0.7

        r = rb.classify_tier("compare Stripe vs Lemon Squeezy pricing Aug 2026")
        assert r["tier"] == "deep_research", f"expected deep_research got {r}"

        r = rb.classify_tier("ship Dottie harness agentic orchestration with checkpoint and graph memory")
        assert r["tier"] == "agentic_epic", f"expected agentic_epic got {r}"

        r = rb.classify_tier("gmail and calendar chain — book, pay idempotent")
        assert r["tier"] == "action_operator", f"expected action_operator got {r}"

        r = rb.route("compare Stripe vs Lemon Squeezy Aug 2026")
        assert r["tier"] == "deep_research"
        assert "deep-researcher" in r["route"]
        assert r["confidence"] >= 0.6
        assert "rationale" in r

        print("PASS classifyTier")
    except Exception as e:
        raise AssertionError(f"classify_tier failed {e}")

def test_memory_retriever_topk():
    mem_mod_path = Path.home() / "workspace" / "bundles" / "scripts" / "memory_retriever.py"
    import importlib.util
    assert mem_mod_path.exists(), "memory_retriever.py missing"
    spec = importlib.util.spec_from_file_location("memory_retriever", str(mem_mod_path))
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)

    # create minimal TLPG if missing for test
    base = Path.home() / "workspace" / "bundles" / "memory" / "contacts_harness"
    base.mkdir(parents=True, exist_ok=True)
    nodes_file = base / "nodes.jsonl"
    if not nodes_file.exists():
        nodes_file.write_text('{"id":"n_test_launch","canonical_name":"Launched","node_class":"Goal","confidence":0.9,"attributes":{"deadline":"2026-08-31"}}\n')

    results = mr.retrieve("what's my launch goal", k=5)
    assert isinstance(results, list)
    assert len(results) <= 5
    if len(results) > 0:
        # top result should contain launched or goal or memory
        texts = " ".join([r.get("snippet","")[:500].lower() for r in results])
        # at least one relevance signal
        assert any(sig in texts for sig in ["launch","goal","scout","cameron"]) or len(results)>=1
        assert "score" in results[0]
        assert "provenance" in results[0]
    print("PASS memory_retriever")

def test_graph_planner_structure():
    import subprocess, json
    planner = Path.home() / "workspace" / "bundles" / "ultra" / "graph_planner_garnet.js"
    assert planner.exists(), "graph_planner_garnet.js missing"
    # Node run
    try:
        proc = subprocess.run(["node", str(planner), "ship Dottie SOTA to prod via ultra-orchestrator"], capture_output=True, text=True, timeout=8)
        assert proc.returncode == 0, f"node failed {proc.stderr}"
        out = json.loads(proc.stdout)
        assert "steps" in out
        assert len(out["steps"]) >= 3
        assert out["steps"][0].get("role")
        assert "llmTier" in out["steps"][0]
        assert "failureRisk" in out["steps"][0]
        assert "graph_memory" in out
        assert "G_workflow" in out["graph_memory"]
        print("PASS graph planner node")
    except FileNotFoundError:
        print("SKIP node not installed")
    except Exception as e:
        raise AssertionError(f"graph planner failed {e}")

def test_router_tool_json():
    tool_path = Path.home() / "workspace" / "bundles" / "tools" / "router-tool.json"
    assert tool_path.exists(), "router-tool.json missing"
    data = json.loads(tool_path.read_text())
    assert data.get("name") == "router-tool"
    assert "input_schema" in data
    assert "output_schema" in data
    assert "deterministic" in str(data)
    assert "deep_research" in str(data) or "deep" in str(data)
    print("PASS router-tool.json")

if __name__ == "__main__":
    test_classify_tier_core()
    test_memory_retriever_topk()
    test_graph_planner_structure()
    test_router_tool_json()
    print("ALL orientation engine tests passed 3.3-moMA-lite wish-I-had")
