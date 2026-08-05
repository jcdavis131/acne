"""Backward-compatible shim — use runtime_adapter as primary."""
from .runtime_adapter import get_runtime_tools as get_hatch_tools
from .runtime_adapter import get_runtime_tools as get_scout_tools
from .runtime_adapter import get_runtime_tools as get_agent_tools
from .runtime_adapter import get_tools

def get_hatch_skill():
    return {"name": "contacts", "description": "Resolve people like 'my designer' → names/emails"}

__all__ = ["get_hatch_tools", "get_scout_tools", "get_agent_tools", "get_tools", "get_hatch_skill"]
