
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

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