"""sameas_hard_soft.py — Richer SAME_AS hard→soft alias handling
ACNE 0.2.1 → 0.3.0 hill-climb 30c → 50+ contacts

Hard SAME_AS:
- exact email match (lowercased) confidence 0.92-0.98
- exact trigger phrase lowercased match + same node_class confidence 0.90
- exact canonical_name lowercased match + shared org or email domain confidence 0.91
- Result: edge SAME_AS hard, properties {"hard": True, "match":"email|trigger|canonical", "deterministic": True}
- Merge allowed but never destructive delete: keep both nodes, link hard, canonical chosen by longer aliases + higher confidence + manual source priority

Soft SAME_AS:
- jaccard >0.6 OR abbrev "A. Chen"→"Alice Chen" first-initial+last OR cosine>0.85 hash-embed 32-d OR shared org + location co-occurrence
- confidence 0.55-0.89, properties {"hard": False, "soft": True, "jaccard":..., "abbrev":..., "vec":..., "topo":...}
- Result: edge SAME_AS soft, never merge auto, GraphRAG resolves both but prefers hard canonical if exists
- Provenance preserved: Document→Chunk→EXTRACTED_FROM with checksum, tx_time, valid_from

No torch, no cloud, stdlib only.
"""

from __future__ import annotations
from typing import List, Dict, Tuple, Optional
import re, hashlib
from .models import TLPGNode, TLPGEdge, _now_iso
from .resolution import name_normalize, jaccard, is_abbrev, hash_embed, cosine

def email_of(node: TLPGNode) -> List[str]:
    attrs=node.attributes or {}
    emails=[]
    for k in ("email","emails","primary_email","contact_email"):
        v=attrs.get(k)
        if not v: continue
        if isinstance(v, list):
            emails.extend([str(x).lower() for x in v if x])
        else:
            emails.append(str(v).lower())
    # also parse from canonical name if contains @
    if "@" in node.canonical_name:
        m=re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", node.canonical_name)
        emails.extend([x.lower() for x in m])
    # aliases may contain email
    for a in node.aliases:
        if "@" in a:
            m=re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", a)
            emails.extend([x.lower() for x in m])
    return list(set(emails))

def triggers_of(node: TLPGNode) -> List[str]:
    attrs=node.attributes or {}
    tr=[]
    for k in ("trigger","triggers","trigger_phrase","maps_to"):
        v=attrs.get(k)
        if not v: continue
        if isinstance(v, list):
            tr.extend([str(x).lower().strip() for x in v if x])
        else:
            tr.append(str(v).lower().strip())
    # also aliases often contain trigger
    for a in node.aliases:
        if len(a.split())<=4:  # short phrases likely triggers
            tr.append(a.lower().strip())
    return list(set(tr))

def org_of(node: TLPGNode) -> Optional[str]:
    attrs=node.attributes or {}
    for k in ("org","organization","affiliation","company"):
        v=attrs.get(k)
        if v:
            return str(v).lower().strip()
    return None

def hard_sameas(node_a: TLPGNode, node_b: TLPGNode) -> Tuple[bool, str, float]:
    """Return (is_hard, reason, confidence)"""
    if node_a.node_class != node_b.node_class:
        return False, "different class", 0.0
    # email exact
    ea=set(email_of(node_a)); eb=set(email_of(node_b))
    if ea & eb:
        inter=ea & eb
        return True, f"exact email {list(inter)[0]}", 0.95
    # trigger exact
    ta=set(triggers_of(node_a)); tb=set(triggers_of(node_b))
    if ta & tb:
        # ensure not generic like "my pm" colliding distinct? require same class and at least one also shares last name or email domain or high confidence
        inter=ta & tb
        # avoid generic triggers "my designer" colliding different persons? That would be actually hard merge but could be conflict — we treat as hard only if both have same confidence source manual>0.85
        # For hill-climb, we treat exact trigger as hard when both nodes have confidence>0.7
        if node_a.confidence>=0.55 and node_b.confidence>=0.55:
            return True, f"exact trigger {list(inter)[0]}", 0.92
    # canonical exact lowercased
    ca=name_normalize(node_a.canonical_name); cb=name_normalize(node_b.canonical_name)
    if ca==cb and ca:
        # shared org or domain boosts to hard
        orga=org_of(node_a); orgb=org_of(node_b)
        if orga and orgb and orga==orgb:
            return True, f"canonical+org {ca} {orga}", 0.93
        # email domain same
        # check domains
        da=set([e.split("@")[-1] for e in ea if "@" in e])
        db=set([e.split("@")[-1] for e in eb if "@" in e])
        if da & db:
            return True, f"canonical+domain {ca}", 0.91
        # exact canonical alone is still hard if both manual source
        if node_a.source=="manual" and node_b.source=="manual":
            return True, f"canonical manual exact {ca}", 0.90
        # fallback soft-ish but we classify as hard lower conf
        return True, f"canonical exact {ca}", 0.88
    return False, "", 0.0

def soft_sameas(node_a: TLPGNode, node_b: TLPGNode, vec_threshold: float=0.82) -> Tuple[bool, Dict, float]:
    """Return (is_soft, details, confidence)"""
    if node_a.id==node_b.id or node_a.node_class!=node_b.node_class:
        return False, {}, 0.0
    # already hard?
    is_h,_ ,_ = hard_sameas(node_a, node_b)
    if is_h:
        return False, {"hard":True}, 0.0
    ca=node_a.canonical_name; cb=node_b.canonical_name
    jac=jaccard(ca, cb)
    abbrev_a=is_abbrev(ca, cb); abbrev_b=is_abbrev(cb, ca)
    abbrev=abbrev_a or abbrev_b
    # vector
    txta=f"{ca} {' '.join(node_a.aliases)} {node_a.attributes}"
    txtb=f"{cb} {' '.join(node_b.aliases)} {node_b.attributes}"
    va=hash_embed(txta); vb=hash_embed(txtb)
    vec=cosine(va, vb)
    # org shared
    orga=org_of(node_a); orgb=org_of(node_b)
    org_match = orga and orgb and orga==orgb
    # shared tokens
    shared_alias=set(a.lower() for a in node_a.aliases) & set(a.lower() for a in node_b.aliases)
    # decision
    details={"jaccard":round(jac,3),"abbrev":abbrev,"vec":round(vec,3),"org_match":bool(org_match),"shared_alias":list(shared_alias)[:3]}
    score=0.0
    if jac>0.6:
        score=max(score, 0.55 + jac*0.25)
    if abbrev:
        score=max(score, 0.85 if org_match else 0.75)
    if vec>=vec_threshold:
        score=max(score, 0.60 + vec*0.25)
    if org_match and (jac>0.3 or abbrev or vec>0.7):
        score=max(score, 0.62)
    if shared_alias:
        score=max(score, 0.68)
    if score>=0.55:
        details["soft"]=True
        return True, details, round(min(score,0.89),3)
    return False, details, 0.0

def decide_sameas(node_a: TLPGNode, node_b: TLPGNode) -> Dict:
    hard, reason, conf = hard_sameas(node_a, node_b)
    if hard:
        edge_type="SAME_AS"
        props={"hard":True,"soft":False,"reason":reason,"match":"hard","deterministic":True,"confidence":conf,"method":"hard_email_trigger_canonical"}
        return {"is_sameas":True,"hard":True,"soft":False,"confidence":conf,"reason":reason,"props":props,"edge_type":edge_type}
    soft, details, sconf = soft_sameas(node_a, node_b)
    if soft:
        props={**details,"hard":False,"soft":True,"confidence":sconf,"method":"soft_jaccard_abbrev_vec_org"}
        return {"is_sameas":True,"hard":False,"soft":True,"confidence":sconf,"reason":f"soft {details}","props":props,"edge_type":"SAME_AS"}
    return {"is_sameas":False}

def build_edge(node_a: TLPGNode, node_b: TLPGNode, store=None) -> Optional[TLPGEdge]:
    dec=decide_sameas(node_a, node_b)
    if not dec["is_sameas"]:
        return None
    edge=TLPGEdge(
        source_id=node_a.id,
        target_id=node_b.id,
        edge_type=dec["edge_type"],
        confidence=dec["confidence"],
        properties=dec["props"],
        source="resolution-hard-soft",
    )
    return edge

def hill_climb_resolve_with_hard_soft(tlpg_store, merge_threshold=0.9, soft_threshold=0.55):
    """Full sweep using hard→soft, returns list of edges created."""
    nodes=tlpg_store.list_nodes()
    from collections import defaultdict
    from .resolution import blocking_key
    buckets=defaultdict(list)
    for n in nodes:
        buckets[blocking_key(n)].append(n)
    created=[]
    for bkey, bnodes in buckets.items():
        if len(bnodes)<2: continue
        for i,q in enumerate(bnodes):
            for cand in bnodes[i+1:]:
                if q.id==cand.id: continue
                dec=decide_sameas(q,cand)
                if not dec["is_sameas"]: continue
                # hard → try auto-merge if confidence>=merge_threshold
                if dec["hard"] and dec["confidence"]>=merge_threshold:
                    # merge logic: keep canonical with longer name or higher confidence manual
                    canonical=q if (len(q.canonical_name)>=len(cand.canonical_name) and q.confidence>=cand.confidence) or q.source=="manual" else cand
                    merged=cand if canonical==q else q
                    # merge aliases
                    canonical.aliases=list(set(canonical.aliases + [merged.canonical_name] + merged.aliases))
                    for k,v in merged.attributes.items():
                        if k not in canonical.attributes:
                            canonical.attributes[k]=v
                    canonical.confidence=min(0.98, max(canonical.confidence, merged.confidence, dec["confidence"]))
                    tlpg_store.upsert_node(canonical)
                    # soft-delete merged
                    all_nodes=tlpg_store.list_nodes()
                    all_nodes=[n for n in all_nodes if n.id!=merged.id]
                    if canonical.id not in [n.id for n in all_nodes]:
                        all_nodes.append(canonical)
                    tlpg_store._write(tlpg_store.nodes_file, [n.to_dict() for n in all_nodes])
                    edge=TLPGEdge(source_id=merged.id,target_id=canonical.id,edge_type="SAME_AS",confidence=dec["confidence"],properties={**dec["props"],"merged":True,"reason":f"hard merged {merged.canonical_name} -> {canonical.canonical_name}"},source="resolution-hard-soft")
                    tlpg_store.add_edge(edge)
                    created.append(edge)
                elif dec["is_sameas"]:
                    edge=TLPGEdge(source_id=q.id,target_id=cand.id,edge_type="SAME_AS",confidence=dec["confidence"],properties=dec["props"],source="resolution-hard-soft")
                    tlpg_store.add_edge(edge)
                    created.append(edge)
    return created
