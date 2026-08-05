"""Integrations — LangChain, CrewAI, OpenAI tool calling, Hermes, MyClaw, Runtime/Scout, Claude."""

def get_langchain_tools(*args, **kwargs):
    from .langchain_adapter import get_langchain_tools as _impl
    return _impl(*args, **kwargs)

def get_crewai_tools(*args, **kwargs):
    from .crewai_adapter import get_crewai_tools as _impl
    return _impl(*args, **kwargs)

def get_hermes_tools(*args, **kwargs):
    from .hermes_adapter import get_hermes_tools as _impl
    return _impl(*args, **kwargs)

def get_myclaw_tools(*args, **kwargs):
    from .myclaw_adapter import get_myclaw_tools as _impl
    return _impl(*args, **kwargs)

def get_hatch_tools(*args, **kwargs):
    from .hatch_adapter import get_hatch_tools as _impl
    return _impl(*args, **kwargs)

# Public, obfuscated surfaces — preferred going forward
def get_runtime_tools(*args, **kwargs):
    from .runtime_adapter import get_runtime_tools as _impl
    return _impl(*args, **kwargs)

def get_scout_tools(*args, **kwargs):
    from .runtime_adapter import get_scout_tools as _impl
    return _impl(*args, **kwargs)

# Back-compat alias for docs
get_agent_tools = get_runtime_tools

def get_claude_tools(*args, **kwargs):
    from .claude_adapter import get_claude_tools as _impl
    return _impl(*args, **kwargs)

def get_openai_tools(*args, **kwargs):
    from .openai_adapter import get_openai_tools as _impl
    return _impl(*args, **kwargs)

__all__ = ["get_langchain_tools", "get_crewai_tools", "get_hermes_tools", "get_myclaw_tools",
           "get_runtime_tools", "get_scout_tools", "get_agent_tools",
           "get_hatch_tools", "get_claude_tools", "get_openai_tools"]
