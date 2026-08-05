"""
MyClaw / Dottie + agentic-contacts — native bigbang plugin.

Your claw already knows the scout-cli shape. This is the same manifest.

Add this directory to your bigbang/plugins or import the tools directly.
"""

from pathlib import Path
from acne import ContactsHub
from acne.integrations.myclaw_adapter import get_myclaw_tools, MYCLAW_MANIFEST

print("MyClaw manifest v", MYCLAW_MANIFEST['version'])
print("tools:", MYCLAW_MANIFEST['tools'])
print("token_cache:", MYCLAW_MANIFEST['wallets']['token_cache'])

hub = ContactsHub(base=Path("./memory/contacts_harness"))
tools = get_myclaw_tools(hub=hub)
print(f"\n→ {len(tools)} tools wired for myclaw:")
for t in tools:
    print(f"  - {t['name']}: {t['description'][:70]}")

# direct native imports also work:
from acne.integrations.myclaw_adapter import contacts_resolve, run_pipeline, search_entity_graph

hub.add_contact(name="Alex Rivera", email="alex@studio.com", trigger="my designer")
print("\nresolve:", contacts_resolve("my designer"))

# scout --json contacts ... still works because we share the same hub store
# scout contacts resolve "my designer" --json
# scout contacts pipeline "<blob>" --title "Email"
# scout --json contacts graphrag "Acme partners?" --compressed
# scout --json contacts cache-stats
