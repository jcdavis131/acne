"""
Claude Code + agentic-contacts — native, 2 ways.

1) MCP (recommended — 2 lines in claude_desktop_config.json):
   {"mcpServers":{"agentic-contacts":{"command":"agentic-contacts","args":["mcp","serve"]}}}

2) Native tools — Claude-native {name,description,input_schema}:

    from acne.integrations.claude_adapter import get_claude_tools
    tools = get_claude_tools()   # 6 tools, Claude-native
    # client.messages.create(model="...", tools=tools, messages=[...])

Same local store as Scout, LangChain, Hatch — no cloud.
"""

from pathlib import Path
from acne import ContactsHub

hub = ContactsHub(base=Path.home() / "workspace" / "bundles" / "memory" / "contacts_harness")
hub.add_contact(name="Alex Rivera", email="alex@studio.com", role="designer", trigger="my designer")

# Native Claude tools
from acne.integrations.claude_adapter import get_claude_tools, get_claude_code_skill

tools = get_claude_tools()
print(f"Claude-native tools: {[t['name'] for t in tools]}")  # ['contacts_resolve', 'contacts_add', ...]
print("first tool shape:", list(tools[0].keys()))  # name, description, input_schema

skill = get_claude_code_skill()
print(f"skill {skill['name']} v{skill['version']} MCP {skill['mcp_command']}")

# Simulate dispatch like Claude would after tool_use
from acne.integrations.claude_adapter import dispatch
res = dispatch("contacts_resolve", {"query": "my designer"}, hub=hub)
print("resolve my designer →", res)

# GraphRAG compressed — same budget logic, saves tokens on repeats
small = hub.graphrag("Who is Acme partnered with?", compressed=True, budget_tokens=600)
print("compressed GraphRAG:", small.get("saving"), "facts", len(small.get("facts", [])))
