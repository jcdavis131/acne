"""
Hatch + agentic-contacts — native, no extra glue.

Your Hatch agent already knows how to search your notes, files, and goals.
Now it knows your people the same way.

pip install agentic-contacts
"""

from pathlib import Path
from acne import ContactsHub
from acne.integrations.hatch_adapter import get_hatch_tools

# Same store Scout, LangChain, MyClaw all share
hub = ContactsHub(base=Path("./memory/contacts_harness"))
hub.add_contact(name="Alex Rivera", email="alex@studio.com", role="designer", trigger="my designer")

# 1. Get Hatch-native tools — same shape Hatch expects: {name, description, parameters, execute}
tools = get_hatch_tools(hub=hub)
print(f"→ {len(tools)} Hatch tools: {[t['name'] for t in tools]}")

# 2. What a Hatch agent does under the hood:
# When you say "tell my designer about the Q4 mock", Hatch calls:
resolve = [t for t in tools if t['name'] == 'contacts_resolve'][0]['execute']
who = resolve("my designer")
print("resolve my designer →", who)

# 3. Pipeline is still just one call — ingest → extract → resolve → graph, dedup-cached
pipeline = [t for t in tools if t['name'] == 'run_pipeline'][0]['execute']
print(pipeline("Alice Chen from Acme Corp authored Q4 Arch on 2025-11-10. Acme partnered with Beta Labs.", "Email"))

# 4. GraphRAG compressed saves your token budget — ideal for always-on Hatch agents that run on heartbeats
g = [t for t in tools if t['name'] == 'search_entity_graph'][0]['execute']
print(g("Acme partners who authored citations?", compressed=True))

# 5. As a Hatch Skill (optional):
# Drop get_hatch_skill() into ~/skills/agentic-contacts/SKILL.md and your agent auto-discovers it
from acne.integrations.hatch_adapter import get_hatch_skill
print("skill definition:", get_hatch_skill()['name'], get_hatch_skill()['tools'][:4])
