import dotenv
import os
from neo4j import GraphDatabase

load_status = dotenv.load_dotenv("Neo4j-9a89c3df-Created-2025-10-09.txt")
if load_status is False:
    raise RuntimeError('Environment variables not loaded.')

URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))

# Test connection
with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()
    print("Connection established.")

def build_graph(entity_df, driver):
    """Build knowledge graph directly in Neo4j"""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        
        for _, row in entity_df.iterrows():
            email_id = row["email_id"]
            case_ids = row["case_ids"]
            participants = row["participants"]
            teams = row["teams"]
            
            # Create Person nodes
            for p in participants:
                if p and p.strip():
                    session.run("""
                        MERGE (person:Person {name: $name})
                        SET person.color = 'lightblue'
                    """, name=p.strip())
            
            # Create Team nodes
            for t in teams:
                if t and t.strip():
                    session.run("""
                        MERGE (team:Team {name: $name})
                        SET team.color = 'orange'
                    """, name=t.strip())
            
            # Create Case nodes
            for c in case_ids:
                if c and c.strip():
                    session.run("""
                        MERGE (case:Case {id: $case_id})
                        SET case.color = 'lightgreen'
                    """, case_id=c.strip())
            
            # Create Person-Person relationships
            for i, p1 in enumerate(participants):
                if not p1 or not p1.strip():
                    continue
                for p2 in participants[i+1:]:
                    if not p2 or not p2.strip():
                        continue
                    session.run("""
                        MATCH (p1:Person {name: $person1})
                        MATCH (p2:Person {name: $person2})
                        MERGE (p1)-[r:COMMUNICATED_IN]->(p2)
                        ON CREATE SET r.weight = 1, r.emails = [$email_id]
                        ON MATCH SET r.weight = r.weight + 1, 
                                    r.emails = r.emails + $email_id
                    """, person1=p1.strip(), person2=p2.strip(), email_id=email_id)
            
            # Create Person-Case relationships
            for c in case_ids:
                if not c or not c.strip():
                    continue
                for p in participants:
                    if p and p.strip():
                        session.run("""
                            MATCH (person:Person {name: $person})
                            MATCH (case:Case {id: $case_id})
                            MERGE (person)-[:INVOLVED_IN]->(case)
                        """, person=p.strip(), case_id=c.strip())
            
            # Create Team-Case relationships
            for c in case_ids:
                if not c or not c.strip():
                    continue
                for t in teams:
                    if t and t.strip():
                        session.run("""
                            MATCH (team:Team {name: $team})
                            MATCH (case:Case {id: $case_id})
                            MERGE (team)-[:HANDLES]->(case)
                        """, team=t.strip(), case_id=c.strip())

def graph_to_json(driver):
    """Export graph from Neo4j to JSON format"""
    with driver.session() as session:
        # Get all nodes
        nodes_result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as type, 
                   COALESCE(n.name, n.id) as name,
                   n.color as color
        """)
        nodes = [{"id": record["name"], 
                 "type": record["type"],
                 "color": record["color"]} 
                for record in nodes_result]
        
        # Get all relationships
        links_result = session.run("""
            MATCH (s)-[r]->(t)
            RETURN COALESCE(s.name, s.id) as source, 
                   COALESCE(t.name, t.id) as target,
                   type(r) as relation,
                   COALESCE(r.weight, 1) as weight
        """)
        links = [{"source": record["source"],
                 "target": record["target"],
                 "relation": record["relation"],
                 "weight": record["weight"]}
                for record in links_result]
        
        return {"nodes": nodes, "links": links}

