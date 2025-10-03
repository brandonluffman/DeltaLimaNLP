import re
import spacy
import pandas as pd
from ingest_emails import TEAMS

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