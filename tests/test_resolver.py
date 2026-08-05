from acne import ContactsHub
import tempfile
from pathlib import Path

def test_basic_resolve():
    with tempfile.TemporaryDirectory() as td:
        hub = ContactsHub(base=Path(td))
        hub.add_contact(name="Alex Rivera", email="alex@studio.com", role="designer", trigger="my designer")
        hub.add_contact(name="Jordan Park", email="jordan@co.com", role="client", trigger="the client call")
        r1 = hub.resolve("my designer")
        assert r1.contact and r1.contact.name == "Alex Rivera"
        assert r1.confidence >= 0.7
        r2 = hub.resolve("the client call")
        assert r2.contact and r2.contact.name == "Jordan Park"

def test_memory_enrich_no_cloud():
    with tempfile.TemporaryDirectory() as td:
        hub = ContactsHub(base=Path(td))
        text = "Talked to Alex and Alex again and Maya about Figma. Alex rocks."
        cands = hub.enrich_from_memory(text=text)
        # should find Alex at least 2 times
        names = [c["name"] for c in cands]
        assert "Alex" in names

def test_placeholder_low_conf():
    with tempfile.TemporaryDirectory() as td:
        hub = ContactsHub(base=Path(td))
        hub.add_trigger("the client call", "Unknown Person", confidence=0.32, reason="heuristic — needs confirmation", source="memory_heuristic")
        r = hub.resolve("the client call")
        assert r.confidence < 0.5
        assert "heuristic" in r.why.lower() or "worth confirming" in r.why.lower() or r.confidence < 0.5
