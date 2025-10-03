from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="Legal NLP API")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://deltalima.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    # from test import (generate_email_batch, preprocess_emails, build_graph, 
    #               generate_case_summaries, graph_to_json)
    from ingest_emails import generate_email_batch
    from nlp_preprocessing import preprocess_emails
    from knowledge_graph import build_graph, graph_to_json
    from summarization import generate_case_summaries

except ImportError:
    print("ERROR: Cannot find test.py. Make sure test.py is in the same directory as api.py")
    sys.exit(1)


class Store:
    emails = {}
    entities = pd.DataFrame()
    summaries = pd.DataFrame()
    graph_json = {}
    last_update = None

store = Store()

def run_pipeline():
    """Run NLP pipeline"""
    try:
        emails = generate_email_batch(n=20)
        entities = preprocess_emails(emails)
        graph = build_graph(entities)
        
        # Save outputs
        os.makedirs("data", exist_ok=True)
        os.makedirs("static", exist_ok=True)
        entities.to_csv("data/entities.csv", index=False)
        
        cases = list(set(sum(entities["case_ids"].tolist(), [])))
        summaries = generate_case_summaries(emails, cases)
        summaries.to_csv("data/summaries.csv", index=False)
        
        import json
        with open("data/emails.json", "w") as f:
            json.dump(emails, f)
        
        store.emails = emails
        store.entities = entities
        store.summaries = summaries
        store.graph_json = graph_to_json(graph)
        with open("static/graph.json", "w") as f:
            json.dump(store.graph_json, f)
        store.last_update = datetime.utcnow()
        
    except Exception as e:
        raise

def load_existing_data():
    try:
        print('Trying to pass through existing data')
        if not os.path.exists("data/entities.csv"):
            return False
        
        store.entities = pd.read_csv("data/entities.csv")
        store.summaries = pd.read_csv("data/summaries.csv")
        
        import ast, json

        store.entities['case_ids'] = store.entities['case_ids'].apply(ast.literal_eval)
        store.entities['participants'] = store.entities['participants'].apply(ast.literal_eval)
        store.entities['teams'] = store.entities['teams'].apply(ast.literal_eval)

        # Ensure case_id in summaries is a string
        store.summaries['case_id'] = store.summaries['case_id'].astype(str)
        
        # Load emails
        with open("data/emails.json", "r") as f:
            store.emails = json.load(f)
        
        # import networkx as nx
        store.last_update = datetime.fromtimestamp(os.path.getmtime("data/entities.csv"))
        graph = build_graph(store.entities)
        store.graph_json = graph_to_json(graph)


        return True
    except Exception as e:
        print(f"Could not load existing data: {e}")
        return False

@app.get("/")
def home():
    return {
        "status": "running",
        "last_update": store.last_update,
        "cases": len(set(sum(store.entities["case_ids"].tolist(), []))) if not store.entities.empty else 0
    }

@app.get("/cases")
def get_cases():
    """List all cases"""
    if store.entities.empty:
        raise HTTPException(404, "No data. Run /pipeline first")
    
    cases = {}
    for _, row in store.entities.iterrows():
        for case_id in row["case_ids"]:
            if case_id not in cases:
                cases[case_id] = {
                    "case_id": case_id,
                    "participants": set(),
                    "teams": set(),
                    "emails": 0
                }
            cases[case_id]["participants"].update(row["participants"])
            cases[case_id]["teams"].update(row["teams"])
            cases[case_id]["emails"] += 1
    
    for _, row in store.summaries.iterrows():
        cid = str(row["case_id"])
        if cid in cases:
            cases[cid]["summary"] = row["summary"]
    
    return [
        {
            "case_id": k,
            "summary": v.get("summary", "No summary"),
            "participants": list(v["participants"]),
            "teams": list(v["teams"]),
            "emails": v["emails"]
        }
        for k, v in cases.items()
    ]

@app.get("/cases/{case_id}")
def get_case(case_id: str):
    """Get case details"""
    if store.summaries.empty:
        raise HTTPException(404, "No data")
    
    row = store.summaries[store.summaries["case_id"] == case_id]
    if row.empty:
        raise HTTPException(404, f"Case {case_id} not found")
    
    related = store.entities[store.entities["case_ids"].apply(lambda x: case_id in x)]
    
    return {
        "case_id": case_id,
        "summary": row.iloc[0]["summary"],
        "participants": list(set(sum(related["participants"].tolist(), []))),
        "teams": list(set(sum(related["teams"].tolist(), []))),
        "emails": len(related)
    }


@app.get("/graph/json")
def get_graph_json():
    if not store.graph_json:
        raise HTTPException(404, "No graph data")
    return store.graph_json

# @app.post("/pipeline")
# def trigger_pipeline():
#     run_pipeline()
#     return {"status": "done"}

scheduler = BackgroundScheduler()
scheduler.add_job(run_pipeline, 'interval', hours=6)

@app.on_event("startup")
def startup():
    try:
        if load_existing_data():
            pass
        else:
            run_pipeline()
        
        scheduler.start()
    except Exception as e:
        print(f"Startup error: {e}")

        
@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)