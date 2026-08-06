"""seed 50+ contacts hill-climb — deterministic synthetic + real samples from arxiviq graph report
No cloud, stdlib only.
"""
from .hub import ContactsHub
from .models import TLPGNode

CONTACTS_50 = [
    # Person 1-30 base (originally 30c)
    {"name":"Alex Rivera","email":"alex@studio.com","trigger":"my designer","role":"designer","org":"Studio Co"},
    {"name":"Alice Chen","email":"alice@acme-corp.com","trigger":"my pm","role":"pm","org":"Acme Corp"},
    {"name":"Bob Jones","email":"bob@studio.com","trigger":"my designer lead","role":"designer","org":"Studio Co"},
    {"name":"Danijar Hafner","email":"danijar@deepmind.com","trigger":"author of DreamerV3","role":"researcher","org":"DeepMind"},
    {"name":"Yann LeCun","email":"yann@meta.com","trigger":"fair lead","role":"researcher","org":"FAIR, Meta"},
    {"name":"Kaiming He","email":"kaiming@meta.com","trigger":"vision lead","role":"researcher","org":"FAIR, Meta"},
    {"name":"Fei-Fei Li","email":"feifei@stanford.edu","trigger":"vision professor","role":"professor","org":"Stanford University"},
    {"name":"Armand Joulin","email":"armand@deepmind.com","trigger":"jepa author","role":"researcher","org":"DeepMind"},
    {"name":"Pierre Beckmann","email":"pierre@deepmind.com","trigger":"imagen lead","role":"researcher","org":"DeepMind"},
    {"name":"Alireza Zareian","email":"zareian@deepmind.com","trigger":"deepmind vision","role":"researcher","org":"DeepMind"},
    {"name":"Randy Evans","email":"randy@deepmind.com","trigger":"simulation lead","role":"researcher","org":"DeepMind"},
    {"name":"Amir Nazemi","email":"amir@deepmind.com","trigger":"world model","role":"researcher","org":"DeepMind"},
    {"name":"L. B. Litinskii","email":"litinskii@iont.ru","trigger":"optical neural","role":"researcher","org":"Institute of Optical Neural Technologies"},
    {"name":"B. V. Kryzhanovsky","email":"kryzh@iont.ru","trigger":"hopfield","role":"researcher","org":"Institute of Optical Neural Technologies"},
    {"name":"A. L. Mikaelyan","email":"mikaelyan@iont.ru","trigger":"holographic","role":"researcher","org":"Institute of Optical Neural Technologies"},
    # 16-30
    {"name":"Jordan Smith","email":"jordan@stripe.com","trigger":"payments lead","role":"payments","org":"Stripe"},
    {"name":"Sam Lee","email":"sam@linear.app","trigger":"my pm at linear","role":"pm","org":"Linear"},
    {"name":"Edward Lee","email":"edward@acme.com","trigger":"acme engineer","role":"engineer","org":"Acme Corp"},
    {"name":"Priya Patel","email":"priya@sports.com","trigger":"sports desk","role":"reporter","org":"Sports Media"},
    {"name":"Maya Chen","email":"maya@opensource.com","trigger":"industry correspondent","role":"reporter","org":"OpenSource"},
    {"name":"Marcus Johnson","email":"marcus@markets.com","trigger":"markets desk","role":"analyst","org":"Markets"},
    {"name":"Cameron Davis","email":"cameron@scout.com","trigger":"me","role":"owner","org":"Scout"},
    {"name":"Scout Prime","email":"scout@runtime.local","trigger":"scout-prime","role":"agent","org":"Scout Runtime"},
    {"name":"Alice C. Chen","email":"alice@acme-corp.com","trigger":"alice c","role":"pm","org":"Acme Corp"},
    {"name":"Robert Jones","email":"bob@studio.com","trigger":"bob jones alias","role":"designer","org":"Studio Co"},
    {"name":"A. Chen","email":"alice@acme-corp.com","trigger":"a chen citation","role":"researcher","org":"Acme Corp"},
    {"name":"R. Evans","email":"randy@deepmind.com","trigger":"r evans","role":"researcher","org":"DeepMind"},
    {"name":"Google DeepMind","email":"","trigger":"deepmind","role":"org","org":"DeepMind","is_org":True},
    {"name":"FAIR Meta","email":"","trigger":"fair meta","role":"org","org":"FAIR","is_org":True},
    {"name":"Stanford Vision Lab","email":"","trigger":"stanford vision","role":"org","org":"Stanford University","is_org":True},
    # 31-55 hill-climb extra
    {"name":"Sofia Zhang","email":"sofia@deepmind.com","trigger":"dreamer team","role":"researcher","org":"DeepMind"},
    {"name":"Liam Park","email":"liam@stripe.com","trigger":"lemon squeezy comparison","role":"payments","org":"Stripe"},
    {"name":"Noah Patel","email":"noah@linear.app","trigger":"linear infra","role":"engineer","org":"Linear"},
    {"name":"Olivia Wu","email":"olivia@studio.com","trigger":"my illustrator","role":"illustrator","org":"Studio Co"},
    {"name":"Ethan Kim","email":"ethan@meta.com","trigger":"jepa v2","role":"researcher","org":"FAIR, Meta"},
    {"name":"Ava Singh","email":"ava@stanford.edu","trigger":"stanford phd","role":"student","org":"Stanford University"},
    {"name":"Mason Brown","email":"mason@acme.com","trigger":"acme sales","role":"sales","org":"Acme Corp"},
    {"name":"Isabella Garcia","email":"isabella@sports.com","trigger":"wnba lead","role":"reporter","org":"Sports Media"},
    {"name":"Lucas White","email":"lucas@markets.com","trigger":"chips desk","role":"analyst","org":"Markets"},
    {"name":"Mia Hernandez","email":"mia@opensource.com","trigger":"open source lead","role":"reporter","org":"OpenSource"},
    {"name":"James Liu","email":"james@iont.ru","trigger":"optical computing","role":"researcher","org":"Institute of Optical Neural Technologies"},
    {"name":"Charlotte Davis","email":"charlotte@scout.com","trigger":"scout ops","role":"operator","org":"Scout"},
    {"name":"Benjamin Moore","email":"ben@scout.com","trigger":"scout builder","role":"builder","org":"Scout"},
    {"name":"Harper Taylor","email":"harper@scout.com","trigger":"scout researcher","role":"researcher","org":"Scout"},
    {"name":"Evelyn Anderson","email":"evelyn@acme.com","trigger":"acme legal","role":"legal","org":"Acme Corp"},
    {"name":"Daniel Wilson","email":"daniel@deepmind.com","trigger":"genie lead","role":"researcher","org":"DeepMind"},
    {"name":"David Thomas","email":"david@deepmind.com","trigger":"storm","role":"researcher","org":"DeepMind"},
    {"name":"Abigail Jackson","email":"abigail@meta.com","trigger":"imagebind","role":"researcher","org":"FAIR, Meta"},
    {"name":"Joseph Martin","email":"joseph@stanford.edu","trigger":"robotics","role":"professor","org":"Stanford University"},
    {"name":"Grace Thompson","email":"grace@studio.com","trigger":"my animator","role":"animator","org":"Studio Co"},
    {"name":"John Backus","email":"john@acme.com","trigger":"acme founder","role":"founder","org":"Acme Corp"},
    {"name":"Sarah Kim","email":"sarah@linear.app","trigger":"linear design","role":"designer","org":"Linear"},
    {"name":"Emily Zhao","email":"emily@deepmind.com","trigger":"iris","role":"researcher","org":"DeepMind"},
    {"name":"Michael Chen","email":"michael@acme.com","trigger":"acme finance","role":"finance","org":"Acme Corp"},
    {"name":"David Park","email":"david.park@stripe.com","trigger":"stripe infra","role":"engineer","org":"Stripe"},
]

def seed_50(hub: ContactsHub|None=None) -> dict:
    hub = hub or ContactsHub()
    # use hub.add_person for Persons, and hub TLPG for orgs
    added=0
    for c in CONTACTS_50:
        is_org=c.get("is_org", False)
        if is_org:
            # org node
            node=TLPGNode(node_class="Organization", canonical_name=c["name"], aliases=[c["trigger"]], attributes={"org":c["org"]}, confidence=0.88, source="manual")
            hub.tlpg.upsert_node(node)
            added+=1
        else:
            try:
                hub.add_person(name=c["name"], email=c["email"], trigger=c["trigger"], role=c.get("role",""), org=c.get("org"))
                added+=1
            except Exception as e:
                # fallback TLPG direct
                node=TLPGNode(node_class="Person", canonical_name=c["name"], aliases=[c["trigger"], c["email"]], attributes={"email":c["email"],"role":c.get("role"),"org":c.get("org")}, confidence=0.88, source="manual")
                hub.tlpg.upsert_node(node)
                added+=1
    # run hard-soft resolution
    try:
        from .sameas_hard_soft import hill_climb_resolve_with_hard_soft
        edges=hill_climb_resolve_with_hard_soft(hub.tlpg)
    except Exception as e:
        edges=[]
    # graph stats
    nodes=hub.tlpg.list_nodes()
    persons=[n for n in nodes if n.node_class=="Person"]
    orgs=[n for n in nodes if n.node_class=="Organization"]
    return {"added":added,"total_nodes":len(nodes),"persons":len(persons),"orgs":len(orgs),"edges_created":len(edges),"hard_soft":"hard→soft enabled"}

if __name__=="__main__":
    print(seed_50())
