"""Scout adapter — alias for runtime_adapter."""
from .runtime_adapter import *  # noqa: F401,F403
from .runtime_adapter import get_runtime_tools as get_scout_tools
__all__ = ["get_scout_tools", "get_runtime_tools", "get_agent_tools", "get_tools"]
