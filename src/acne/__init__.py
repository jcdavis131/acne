"""Public surface — keep it cozy. v0.2.1 cache-optimized 💰 + harness-native"""

from .hub import ContactsHub
from .models import (
    Contact, Trigger, ResolveResult,
    TLPGNode, TLPGEdge, DocumentArtifact, TextChunk,
    ExtractionResult, ResolutionResult,
)
from .store import ContactsStore
from .graph import TLPGStore
from .cache import TokenCache
from .resolver import ContactsResolver

# lazy adapters – import only when asked
def get_langchain_tools(*args, **kwargs):
    from .integrations.langchain_adapter import get_langchain_tools as _fn
    return _fn(*args, **kwargs)

def get_openai_tools(*args, **kwargs):
    from .integrations.openai_adapter import get_openai_tools as _fn
    return _fn(*args, **kwargs)

def get_crewai_tools(*args, **kwargs):
    from .integrations.crewai_adapter import get_crewai_tools as _fn
    return _fn(*args, **kwargs)

def get_hermes_tools(*args, **kwargs):
    from .integrations.hermes_adapter import get_hermes_tools as _fn
    return _fn(*args, **kwargs)

def get_myclaw_tools(*args, **kwargs):
    from .integrations.myclaw_adapter import get_myclaw_tools as _fn
    return _fn(*args, **kwargs)

def get_hatch_tools(*args, **kwargs):
    from .integrations.hatch_adapter import get_hatch_tools as _fn
    return _fn(*args, **kwargs)

def get_claude_tools(*args, **kwargs):
    from .integrations.claude_adapter import get_claude_tools as _fn
    return _fn(*args, **kwargs)

__all__ = [
    "hill_climb_resolve_with_hard_soft","hard_sameas","soft_sameas","decide_sameas","build_edge","CONTACTS_50","seed_50",
    "ContactsHub",
    "Contact", "Trigger", "ResolveResult",
    "TLPGNode", "TLPGEdge", "DocumentArtifact", "TextChunk",
    "ExtractionResult", "ResolutionResult",
    "ContactsStore", "TLPGStore", "ContactsResolver", "TokenCache",
    "get_langchain_tools", "get_openai_tools", "get_crewai_tools",
    "get_hermes_tools", "get_myclaw_tools", "get_hatch_tools", "get_claude_tools",
]

# hard→soft SAME_AS rich alias
try:
    from .sameas_hard_soft import hard_sameas, soft_sameas, decide_sameas, build_edge, hill_climb_resolve_with_hard_soft
except Exception:
    pass

try:
    from .data_seed_50 import CONTACTS_50, seed_50
except Exception:
    CONTACTS_50=[]
    def seed_50(*a,**kw): return {"added":0}

__version__ = "0.3.0-hard-soft-50c"
