"""Public surface — keep it cozy. v0.4.0 constructs + graphify 💰 + harness-native"""

from .hub import ContactsHub
from .models import (
    Contact, Trigger, ResolveResult,
    TLPGNode, TLPGEdge, DocumentArtifact, TextChunk,
    ExtractionResult, ResolutionResult,
    # constructs v0.4
    make_construct, make_concept, make_project, make_goal, make_task,
    make_agent_node, make_workflow_node, make_skill_node, make_bundle_node, make_event_node,
    make_person, make_org, make_edge,
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

def get_scout_tools(*args, **kwargs):
    from .integrations.scout_adapter import get_scout_tools as _fn
    return _fn(*args, **kwargs)

def get_claude_tools(*args, **kwargs):
    from .integrations.claude_adapter import get_claude_tools as _fn
    return _fn(*args, **kwargs)

__all__ = [
    "hill_climb_resolve_with_hard_soft","hard_sameas","soft_sameas","decide_sameas","build_edge","CONTACTS_50","seed_50",
    "graphify_constructs",
    "ContactsHub",
    "Contact", "Trigger", "ResolveResult",
    "TLPGNode", "TLPGEdge", "DocumentArtifact", "TextChunk",
    "ExtractionResult", "ResolutionResult",
    "ContactsStore", "TLPGStore", "ContactsResolver", "TokenCache",
    "make_construct","make_concept","make_project","make_goal","make_task",
    "make_agent_node","make_workflow_node","make_skill_node","make_bundle_node","make_event_node",
    "make_person","make_org","make_edge",
    "get_langchain_tools", "get_openai_tools", "get_crewai_tools",
    "get_hermes_tools", "get_myclaw_tools", "get_hatch_tools", "get_scout_tools", "get_claude_tools",
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

def graphify_constructs(hub_or_store=None, **kw):
    """Top-level helper: hub.tlpg.graphify_constructs() or TLPGStore.graphify_constructs()"""
    if hasattr(hub_or_store, "tlpg"):
        return hub_or_store.tlpg.graphify_constructs(**kw)
    if hasattr(hub_or_store, "graphify_constructs"):
        return hub_or_store.graphify_constructs(**kw)
    raise ValueError("pass ContactsHub or TLPGStore")

__version__ = "0.4.0-constructs"
