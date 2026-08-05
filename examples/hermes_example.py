"""
Hermes + agentic-contacts — native.

Hermes expects: {name, description, parameters: json-schema, execute: fn}
We give you exactly that.

pip install agentic-contacts
"""

from pathlib import Path
from acne import ContactsHub
from acne.integrations.hermes_adapter import get_hermes_tools

hub = ContactsHub(base=Path("./memory/contacts_harness"))
hub.add_contact(name="Alex Rivera", email="alex@studio.com", trigger="my designer")

tools = get_hermes_tools(hub=hub)
print(f"Hermes tools: {[t['name'] for t in tools]}")

# simulate what Hermes does
resolve_fn = [t for t in tools if t['name'] == 'contacts_resolve'][0]['execute']
print(resolve_fn("my designer"))

# run full TLPG pipeline like a deep agent would
pipe = [t for t in tools if t['name'] == 'run_pipeline'][0]['execute']
print(pipe("Alice Chen from Acme Corp authored Q4 Arch on 2025-11-10. Acme partnered with Beta Labs.", "Email"))

# GraphRAG compressed saves your token bill
g = [t for t in tools if t['name'] == 'search_entity_graph'][0]['execute']
print(g("Acme partners who authored citations?", compressed=True))
