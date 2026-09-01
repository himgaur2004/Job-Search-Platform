from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from googleapiclient.errors import HttpError

from services.db import (
    inbox_message_exists,
    insert_inbox_entry,
    list_known_gmail_threads,
    list_known_recruiter_emails,
)
from services.gmail import build_gmail_service

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


@dataclass
class InboxSyncResult:
    fetched_messages: int
    inserted_entries: int
    errors: list[str]


def _decode_body_part(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="replace")


def _extract_sender_email(raw_from: str | None) -> str | None:
    if not raw_from:
        return None
    match = _EMAIL_REGEX.search(raw_from)
    return match.group(0).lower() if match else raw_from.strip().lower()


def _extract_headers(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    headers = payload.get("headers", [])
    if not isinstance(headers, list):
        return None, None
    sender: str | None = None
    subject: str | None = None
    for item in headers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).lower()
        value = str(item.get("value", ""))
        if name == "from":
            sender = _extract_sender_email(value)
        elif name == "subject":
            subject = value
    return sender, subject


def _extract_body(payload: dict[str, Any], snippet: str | None) -> str:
    body = payload.get("body", {})
    if isinstance(body, dict) and isinstance(body.get("data"), str):
        decoded = _decode_body_part(body["data"])
        if decoded.strip():
            return decoded

    parts = payload.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            mime = str(part.get("mimeType", ""))
            part_body = part.get("body", {})
            if (
                mime in {"text/plain", "text/html"}
                and isinstance(part_body, dict)
                and isinstance(part_body.get("data"), str)
            ):
                decoded = _decode_body_part(part_body["data"])
                if decoded.strip():
                    return decoded
            nested = part.get("parts")
            if isinstance(nested, list):
                nested_payload = {"parts": nested}
                nested_body = _extract_body(nested_payload, None)
                if nested_body.strip():
                    return nested_body
    return (snippet or "").strip()


def _internal_date_to_iso(internal_date: str | None) -> str | None:
    if not internal_date:
        return None
    millis = int(internal_date)
    dt = datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc)
    return dt.isoformat()


def sync_inbox_from_gmail(limit: int = 50) -> InboxSyncResult:
    if os.getenv("GMAIL_INBOX_SYNC", "true").lower() != "true":
        return InboxSyncResult(fetched_messages=0, inserted_entries=0, errors=[])

    recruiter_emails = set(list_known_recruiter_emails(limit=1000))
    known_threads = set(list_known_gmail_threads(limit=1000))
    try:
        service = build_gmail_service()
    except RuntimeError as exc:
        return InboxSyncResult(
            fetched_messages=0,
            inserted_entries=0,
            errors=[f"gmail inbox sync skipped: {exc}"],
        )

    query = os.getenv("GMAIL_INBOX_QUERY", "in:inbox newer_than:14d -from:me")
    errors: list[str] = []
    fetched_messages = 0
    inserted_entries = 0
    try:
        listing = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=limit)
            .execute()
        )
    except HttpError as exc:
        return InboxSyncResult(
            fetched_messages=0,
            inserted_entries=0,
            errors=[f"gmail inbox list failed: {exc}"],
        )

    messages = listing.get("messages", [])
    if not isinstance(messages, list):
        return InboxSyncResult(
            fetched_messages=0,
            inserted_entries=0,
            errors=["gmail inbox list payload invalid."],
        )

    for message in messages:
        if not isinstance(message, dict):
            continue
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id.strip():
            continue
        fetched_messages += 1
        if inbox_message_exists(message_id):
            continue

        try:
            full_message = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except HttpError as exc:
            errors.append(f"gmail message fetch failed for {message_id}: {exc}")
            continue

        payload = full_message.get("payload", {})
        if not isinstance(payload, dict):
            errors.append(f"gmail message payload invalid for {message_id}.")
            continue

        sender_email, subject = _extract_headers(payload)
        thread_id_raw = full_message.get("threadId")
        thread_id = str(thread_id_raw) if isinstance(thread_id_raw, str) else None
        if known_threads:
            if not thread_id or thread_id not in known_threads:
                continue
        elif recruiter_emails and (not sender_email or sender_email not in recruiter_emails):
            continue

        snippet = full_message.get("snippet")
        body = _extract_body(payload, snippet if isinstance(snippet, str) else None)
        if not body.strip():
            errors.append(f"gmail message body empty for {message_id}.")
            continue

        internal_date = full_message.get("internalDate")
        try:
            received_at = _internal_date_to_iso(internal_date if isinstance(internal_date, str) else None)
        except ValueError as exc:
            errors.append(f"invalid internalDate for {message_id}: {exc}")
            received_at = None

        insert_inbox_entry(
            gmail_message_id=message_id,
            gmail_thread_id=thread_id,
            sender_email=sender_email,
            subject=subject,
            body=body,
            received_at=received_at,
        )
        inserted_entries += 1

    return InboxSyncResult(
        fetched_messages=fetched_messages,
        inserted_entries=inserted_entries,
        errors=errors,
    )
