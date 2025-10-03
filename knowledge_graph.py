import networkx as nx

def build_graph(entity_df):
    G = nx.Graph()
    for _, row in entity_df.iterrows():
        email_id = row["email_id"]
        case_ids = row["case_ids"]
        participants = row["participants"]
        teams = row["teams"]

        for p in participants:
            if p and p.strip():  # Validate node name
                G.add_node(p, type="Person", color="lightblue")
        for t in teams:
            if t and t.strip():
                G.add_node(t, type="Team", color="orange")
        for c in case_ids:
            if c and c.strip():
                G.add_node(f"Case_{c}", type="Case", color="lightgreen")

        for i, p1 in enumerate(participants):
            if not p1 or not p1.strip():
                continue
            for p2 in participants[i+1:]:
                if not p2 or not p2.strip():
                    continue
                if G.has_edge(p1, p2):
                    G[p1][p2]['weight'] = G[p1][p2].get('weight', 1) + 1
                else:
                    G.add_edge(p1, p2, relation="communicated_in", email=email_id, weight=1)

        for c in case_ids:
            if not c or not c.strip():
                continue
            case_node = f"Case_{c}"
            for p in participants:
                if p and p.strip():
                    G.add_edge(p, case_node, relation="involved_in")
            for t in teams:
                if t and t.strip():
                    G.add_edge(t, case_node, relation="handles")
    return G

def graph_to_json(G):
    """Convert graph to JSON format for React"""
    nodes = [{"id": n, "type": G.nodes[n].get("type")} for n in G.nodes()]
    links = [{"source": s, "target": t, "weight": d.get("weight", 1)} 
             for s, t, d in G.edges(data=True)]
    return {"nodes": nodes, "links": links}