import pandas as pd
from transformers import pipeline as hf_pipeline
from nlp_preprocessing import strip_html

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