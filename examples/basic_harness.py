"""Use agentic-contacts inside your own harness - copy-paste ready."""
from pathlib import Path
from acne import ContactsHub

# your harness keeps its own little contacts world - local, no cloud
hub = ContactsHub(base=Path("./my_harness_contacts"))

# teach it once
hub.add_contact(name="Alex Rivera", email="alex@studio.com", role="designer", trigger="my designer")
hub.add_trigger("the client call", "Jordan Park", confidence=0.85, reason="Tue/Thu standup, 6 times", role="client")

# later, when your agent hears vague talk
for phrase in ["my designer", "the client call", "some random person"]:
    result = hub.resolve(phrase)
    if result.contact and result.confidence > 0.6:
        print(f"{phrase!r} → {result.contact.name} ({result.confidence}) — {result.why}")
    else:
        print(f"{phrase!r} → no confident match: {result.why}")
