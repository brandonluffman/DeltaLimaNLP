
import random
import uuid
import re
import json
from datetime import datetime, timedelta

import spacy
import pandas as pd
import networkx as nx
from pyvis.network import Network
from transformers import pipeline as hf_pipeline
from faker import Faker

# -----------------------------
# Step 1: Fake Graph-like Emails
# -----------------------------

fake = Faker()

LEGAL_TOPICS = [
    "Contract Draft Review", "Missed Filing Deadline",
    "Procurement Dispute", "Case Update",
    "Hearing Preparation", "Confidential Memo",
    "Regulatory Compliance"
]

BODY_TEMPLATES = [
    "Please review the draft related to Case {case_id}. CC: {cc_person} should be kept in the loop.",
    "We missed the filing deadline for Case {case_id}. Escalation may be required. Inform {mentioned_person}.",
    "This is an update on Case {case_id}. Team {team} is expected to provide documents.",
    "Ensure all exhibits for Case {case_id} are filed before {date}. Coordinate with {mentioned_person}.",
    "Leadership requires a briefing on Case {case_id} by {date}. Loop in {cc_person}.",
    "Witness testimony for Case {case_id} has issues. {mentioned_person} should prepare a statement."
]

TEAMS = ["Team A", "Team B", "Leadership", "Litigation", "Compliance"]

def random_user():
    name = fake.name()
    address = name.lower().replace(" ", ".") + "@armylegal.mil"
    return {"emailAddress": {"name": name, "address": address}}

def generate_email(case_id: int):
    sender = random_user()
    to_recipients = [random_user() for _ in range(random.randint(1, 3))]
    cc_recipients = [random_user() for _ in range(random.randint(0, 2))]
    bcc_recipients = [random_user() for _ in range(random.randint(0, 1))]

    subject = f"Case {case_id} - {random.choice(LEGAL_TOPICS)}"
    cc_person = fake.first_name()
    mentioned_person = fake.first_name()
    body_content = random.choice(BODY_TEMPLATES).format(
        case_id=case_id,
        team=random.choice(TEAMS),
        date=fake.date_this_month(),
        cc_person=cc_person,
        mentioned_person=mentioned_person
    )
    body_preview = (body_content[:100] + "...") if len(body_content) > 100 else body_content
    sent_time = datetime.utcnow() - timedelta(days=random.randint(0, 30))
    received_time = sent_time + timedelta(seconds=random.randint(10, 300))

    return {
        "id": str(uuid.uuid4()),
        "conversationId": str(uuid.uuid4()),
        "internetMessageId": f"<{uuid.uuid4()}@armylegal.mil>",
        "subject": subject,
        "bodyPreview": body_preview,
        "body": {"contentType": "html", "content": f"<html><body>{body_content}</body></html>"},
        "from": sender,
        "toRecipients": to_recipients,
        "ccRecipients": cc_recipients,
        "bccRecipients": bcc_recipients,
        "sentDateTime": sent_time.isoformat() + "Z",
        "receivedDateTime": received_time.isoformat() + "Z",
        "hasAttachments": random.choice([False, False, True])
    }

def generate_email_batch(n=10):
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('mockuser')/messages",
        "value": [generate_email(case_id=random.randint(1000, 2000)) for _ in range(n)]
    }

# -----------------------------
# Step 2: Preprocessing (NLP)
# -----------------------------

nlp = spacy.load("en_core_web_sm")

def strip_html(html_content):
    """Remove HTML tags from content"""
    return re.sub(r'<[^>]+>', '', html_content)

def extract_entities(email):
    text = email["subject"] + " " + strip_html(email["body"]["content"])
    doc = nlp(text)

    participants = []
    for field in ["from", "toRecipients", "ccRecipients", "bccRecipients"]:
        val = email.get(field, [])
        if isinstance(val, dict):
            participants.append(val["emailAddress"]["name"])
        elif isinstance(val, list):
            participants.extend([r["emailAddress"]["name"] for r in val])

    case_ids = re.findall(r"Case\s+(\d+)", text)
    teams = [t for t in TEAMS if t in text]
    persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    dates = [ent.text for ent in doc.ents if ent.label_ in ["DATE", "TIME"]]

    return {
        "email_id": email["id"],
        "case_ids": case_ids,
        "participants": list(set(participants + persons)),
        "teams": list(set(teams)),
        "dates": dates
    }

def preprocess_emails(email_json):
    return pd.DataFrame([extract_entities(e) for e in email_json["value"]])

# -----------------------------
# Step 3: Knowledge Graph
# -----------------------------

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

# -----------------------------
# Step 4: Summarization
# -----------------------------

def summarize_case(email_json, case_id):
    print("Loading summarization model (this may take a moment)...")

    summarizer = hf_pipeline("summarization", model="facebook/bart-large-cnn")
    case_texts = []
    for email in email_json["value"]:
        body_text = strip_html(email["body"]["content"])
        if f"Case {case_id}" in email["subject"] or f"Case {case_id}" in body_text:
            case_texts.append(body_text)
    
    if not case_texts:
        return None

    combined = " ".join(case_texts)
    if len(combined) > 1024:
        combined = combined[:1024]
    
    try:
        summary = summarizer(combined, max_length=100, min_length=30, do_sample=False)[0]["summary_text"]
        return summary
    except Exception as e:
        print(f"Error summarizing case {case_id}: {e}")
        return None

def generate_case_summaries(email_json, case_ids):
    summaries = []
    for c in case_ids:
        print(f"Summarizing Case {c}...")
        s = summarize_case(email_json, c)
        if s:
            summaries.append({"case_id": c, "summary": s})
    return pd.DataFrame(summaries) if summaries else pd.DataFrame(columns=["case_id", "summary"])



