from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


@dataclass
class SentEmailResult:
    message_id: str
    thread_id: str | None


def load_credentials() -> Credentials:
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if not token_json:
        raise RuntimeError("Missing GMAIL_TOKEN_JSON.")
    token_dict = json.loads(token_json)
    return Credentials.from_authorized_user_info(token_dict)


def build_gmail_service():
    creds = load_credentials()
    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str, pdf_path: str | None = None) -> SentEmailResult:
    service = build_gmail_service()
    
    if pdf_path and Path(pdf_path).exists():
        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject
        message.attach(MIMEText(body))
        
        with open(pdf_path, "rb") as f:
            pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
            pdf_attachment.add_header("Content-Disposition", "attachment", filename="Resume.pdf")
            message.attach(pdf_attachment)
    else:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    message_id = result.get("id")
    if not message_id:
        raise RuntimeError("Gmail API did not return a message id.")
    thread_id_raw = result.get("threadId")
    thread_id = str(thread_id_raw) if isinstance(thread_id_raw, str) else None
    return SentEmailResult(message_id=message_id, thread_id=thread_id)
