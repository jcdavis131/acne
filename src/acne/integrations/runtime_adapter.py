"""
Generic runtime adapter — public surface for Scout SOTA harness.
Obfuscates internal Hatch name. Implements same tools as hatch_adapter.

This is the recommended import going forward:
  from acne.integrations import get_runtime_tools

Backward compat: hatch_adapter still exists as shim.
"""
from .hatch_adapter import get_hatch_tools, get_tools, get_hatch_skill
# re-export as generic
def get_runtime_tools(*args, **kwargs):
    return get_hatch_tools(*args, **kwargs)

def get_scout_tools(*args, **kwargs):
    return get_hatch_tools(*args, **kwargs)

# keep old names available
__all__ = ["get_runtime_tools", "get_scout_tools", "get_hatch_tools", "get_tools", "get_hatch_skill"]
