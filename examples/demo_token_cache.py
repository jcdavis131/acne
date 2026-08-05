"""
demo_token_cache.py — Why agentic-contacts makes expensive agents cheap 💰
Run this to see doc dedup + query cache + compressed packs + $ saved.
"""

from pathlib import Path
import shutil
from acne.hub import ContactsHub

tmp = Path("/tmp/demo-token-cache")
shutil.rmtree(tmp, ignore_errors=True)
hub = ContactsHub(base=tmp)

sample = """
From: Alice Chen <alice@acme-corp.com>
Alice Chen from Acme Corp authored Q4 Technical Architecture on 2025-11-10.
Acme Corp partnered with Beta Labs. Bob Jones from Beta Labs wrote notes mentioning Alice C. and A. Chen both refer to Alice Chen.
References doi:10.1109/mcp.2025 and https://example.com/paper.pdf Meeting at San Francisco City.
Project: vector-hub, scout-harness v3.3 system map 34 nodes 41 edges.
"""

print("🐱✨ agentic-contacts v0.2.1 — Token-Cache Optimizer Demo\n")

print("1) Cold pipeline run (no cache yet)")
p1 = hub.pipeline_run(sample, title="Email from Alice")
print(f"   → {p1['chunks']} chunks, {p1['stage2']['nodes_created']} nodes, {p1['stage2']['edges_created']} edges")
print(f"   cache: {p1['cache']['cache_entries']}")

print("\n2) First GraphRAG — hybrid dense + multi-hop")
g1 = hub.graphrag("Find all research citations authored by partners of Acme Corp")
print(f"   → seeds: {[s['canonical_name'] for s in g1['seeds'][:3]]}")
print(f"   nodes {len(g1['nodes'])} edges {len(g1['edges'])} provenance {len(g1['provenance_chunks'])} chunk(s)")
print(f"   chars: {len(str(g1))} (big model would pay for all)")

print("\n3) Same query again — should be cache hit, zero extra work")
g2 = hub.graphrag("Find all research citations authored by partners of Acme Corp")
print(f"   → len identical? {len(g2['nodes'])==len(g1['nodes'])} — no re-search needed ✨")

print("\n4) Compressed pack for expensive agents (GPT-4 / Opus)")
tiny = hub.graphrag("Acme Corp partners who authored citations?", compressed=True)
print(f"   → {len(tiny['facts'])} facts, ~{len(str(tiny))} chars vs {len(str(g1))} full")
print(f"   saving {(1-len(str(tiny))/len(str(g1)))*100:.0f}% tokens — {tiny['why_cheap']}")

print("\n5) Duplicate doc ingest — dedup cache")
p2 = hub.pipeline_run(sample, title="Email from Alice (duplicate forward)")
print(f"   → extractions {p2['stage2']['extractions']} — cached ingest skipped re-work")

print("\n6) 💰 ROI")
st = hub.cache_stats()
print(f"   doc hits {st['doc_hits']} query hits {st['query_hits']} ext hits {st['ext_hits']} emb hits {st['emb_hits']}")
print(f"   tokens saved ~{st['tokens_saved']} → ${st['money_saved']} @ $0.015/1k")
print(f"   hit_rate {st['hit_rate_est']} entries {st['cache_entries']}")
print(f"\n   Scale this to 100 heartbeats/day × 30 days × 3 agents = {st['tokens_saved']*3000/1000/1000:.1f}M tokens saved ≈ ${(st['money_saved']*3000):.0f} month")
print("\n✨ Drop this into your harness and every loop gets cheaper — that's why it's popular.")
