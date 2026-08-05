"""
LangChain deep agents + agentic-contacts — native, no glue.

The contacts tool is just another tool your deep agent can call when
someone says "my designer" or "the client call".

pip install agentic-contacts[langchain] langchain langchain-anthropic

You get 10 native tools: resolve, add, list, pipeline, graphrag (82-87% cheaper compressed),
disambiguate, cache stats, etc. All local-first, token-cache aware.
"""

from pathlib import Path
from acne import ContactsHub
# get_langchain_tools is the only thing you need
from acne.integrations.langchain_adapter import get_langchain_tools

# 1. Your memory lives beside your harness, not in the cloud
hub = ContactsHub(base=Path("./memory/contacts_harness"))

# 2. Seed a few "my xyz" phrases once, your agents remember forever
hub.add_contact(name="Alex Rivera", email="alex@studio.com", role="designer", trigger="my designer")
hub.add_contact(name="Jordan Park", email="jordan@co.com", role="client", trigger="the client call")

# 3. Get tools for LangChain / LangGraph deep agents
tools = get_langchain_tools(hub=hub)
print(f"→ {len(tools)} tools ready for deep agents: {[t.name for t in tools]}")

# 4. Drop into a ReAct / deep agent — example with LangGraph:
try:
    from langchain_anthropic import ChatAnthropic
    from langgraph.prebuilt import create_react_agent

    model = ChatAnthropic(model="claude-3-5-sonnet-latest")
    agent = create_react_agent(model, tools)

    # Now your agent can call contacts_resolve when it hears "my designer"
    # Your deep agent prompt just needs to know the tool exists — LangChain handles the rest
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Who's my designer? Send them the Q4 mock"}]
    })
    print(result)

except Exception as e:
    print(f"(skipping live LLM call in CI — install langchain-anthropic to run: {e})")
    # Prove tools work even without LLM:
    print("\n— Demo without LLM —")
    r = tools[0].invoke({"query": "my designer"})
    print("resolve my designer →", r)
    g = tools[4].invoke({"query": "Acme partners", "compressed": True})
    print("graphrag compressed →", str(g)[:200])

# Same shape works for Hermes and MyClaw:
#   from acne.integrations.hermes_adapter import get_hermes_tools
#   tools = get_hermes_tools(hub=hub)
#   from acne.integrations.myclaw_adapter import get_myclaw_tools
#   tools = get_myclaw_tools(hub=hub)
