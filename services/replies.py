from __future__ import annotations

import json
import re
from dataclasses import dataclass

from services import llm
from services.db import (
    insert_reply,
    list_unprocessed_inbox_entries,
    mark_inbox_error,
    mark_inbox_processed,
    resolve_email_id_by_thread,
    resolve_email_id_by_sender,
)

_VALID_CATEGORIES = {"INTERVIEW", "REJECTED", "NEED_INFO", "NO_REPLY", "OTHER"}

_CLASSIFY_PROMPT = """Classify this recruiter email reply into exactly one category:
INTERVIEW, REJECTED, NEED_INFO, NO_REPLY, OTHER.
Respond with ONLY valid JSON: {{"category": "...", "confidence": 0.0-1.0}}

Email:
{email_text}
"""


@dataclass
class ReplyProcessingResult:
    processed_entries: int
    classified_replies: int
    errors: list[str]


def _clean_json_payload(raw: str) -> str:
    return re.sub(r"```json|```", "", raw).strip()


def _keyword_fallback(email_text: str) -> tuple[str, float]:
    text = email_text.lower()
    if any(word in text for word in ("interview", "schedule", "next round", "availability")):
        return "INTERVIEW", 0.6
    if any(word in text for word in ("unfortunately", "rejected", "not moving forward", "declined")):
        return "REJECTED", 0.6
    if any(word in text for word in ("please share", "send", "portfolio", "details", "notice period")):
        return "NEED_INFO", 0.55
    if any(word in text for word in ("no reply", "bounce", "undeliverable")):
        return "NO_REPLY", 0.6
    return "OTHER", 0.4


def classify_reply(email_text: str) -> tuple[str, float]:
    if not email_text.strip():
        return "OTHER", 0.0
    prompt = _CLASSIFY_PROMPT.format(email_text=email_text)
    try:
        raw = llm.generate(prompt)
    except llm.LLMConfigError:
        return _keyword_fallback(email_text)

    cleaned = _clean_json_payload(raw)
    parsed = json.loads(cleaned)
    category = str(parsed.get("category", "OTHER")).upper()
    confidence_raw = parsed.get("confidence", 0.0)
    confidence = float(confidence_raw)
    if category not in _VALID_CATEGORIES:
        return "OTHER", 0.0
    if confidence < 0.0:
        confidence = 0.0
    elif confidence > 1.0:
        confidence = 1.0
    return category, confidence


def process_inbox_replies(limit: int = 50) -> ReplyProcessingResult:
    entries = list_unprocessed_inbox_entries(limit=limit)
    processed_entries = 0
    classified_replies = 0
    errors: list[str] = []

    for entry in entries:
        entry_id = int(entry["id"])
        body = str(entry.get("body", ""))
        gmail_thread_id = entry.get("gmail_thread_id")
        sender_email = entry.get("sender_email")
        received_at = entry.get("received_at")

        try:
            category, confidence = classify_reply(body)
        except (json.JSONDecodeError, RuntimeError, ValueError, TypeError) as exc:
            error = f"inbox entry {entry_id} classification failed: {exc}"
            mark_inbox_error(entry_id, error)
            errors.append(error)
            continue

        email_id = resolve_email_id_by_thread(gmail_thread_id if isinstance(gmail_thread_id, str) else None)
        if email_id is None:
            email_id = resolve_email_id_by_sender(sender_email if isinstance(sender_email, str) else None)
        insert_reply(
            email_id=email_id,
            raw_text=body,
            category=category,
            confidence=confidence,
            received_at=str(received_at) if received_at else None,
        )
        mark_inbox_processed(
            entry_id,
            category=category,
            confidence=confidence,
            email_id=email_id,
        )
        processed_entries += 1
        classified_replies += 1

    return ReplyProcessingResult(
        processed_entries=processed_entries,
        classified_replies=classified_replies,
        errors=errors,
    )
