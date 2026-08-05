def test_acne_import():
    import acne
    from acne import ContactsHub
    assert hasattr(acne, "ContactsHub")
    assert hasattr(acne, "__version__")

def test_adapters_importable():
    from acne.integrations.hatch_adapter import get_hatch_tools
    from acne.integrations.claude_adapter import get_claude_tools
    from acne.integrations.hermes_adapter import get_hermes_tools
    assert len(get_hatch_tools()) >= 6
    assert len(get_claude_tools()) >= 5
