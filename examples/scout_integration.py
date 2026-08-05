"""Scout-style integration - how we wired it into scout-cli."""
from acne import ContactsHub
from pathlib import Path
import json

# Scout keeps contacts alongside its memory lattice (34 nodes / 41 edges)
hub = ContactsHub(workspace=Path.home() / "workspace")

# enrich from what Scout already knows - local only
cands = hub.enrich_from_memory()
print(f"Found {len(cands)} candidates in MEMORY.md")

# Calendar frequency = higher confidence
fake_events = [
    {"attendees": [{"displayName": "Jordan Park"}]},
    {"attendees": [{"displayName": "Jordan Park"}]},
]
cands2 = hub.enrich_from_calendar(fake_events)
print(f"Calendar suggests {cands2}")

# Resolve for OODA loop
result = hub.resolve("the client call")
print(json.dumps(result.to_dict(), indent=2))
