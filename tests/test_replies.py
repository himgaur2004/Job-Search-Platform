from services import replies


def test_classify_reply_parses_llm_json(monkeypatch):
    def fake_generate(_: str) -> str:
        return '{"category":"INTERVIEW","confidence":0.91}'

    monkeypatch.setattr(replies.llm, "generate", fake_generate)
    category, confidence = replies.classify_reply("Can we schedule your interview?")
    assert category == "INTERVIEW"
    assert confidence == 0.91


def test_classify_reply_uses_keyword_fallback_without_llm(monkeypatch):
    def raise_llm_config(_: str) -> str:
        raise replies.llm.LLMConfigError("missing key")

    monkeypatch.setattr(replies.llm, "generate", raise_llm_config)
    category, confidence = replies.classify_reply("Unfortunately, we are not moving forward.")
    assert category == "REJECTED"
    assert confidence > 0


def test_process_inbox_replies_marks_error_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        replies,
        "list_unprocessed_inbox_entries",
        lambda limit=50: [{"id": 10, "body": "body", "sender_email": "a@b.com", "received_at": None}],
    )
    monkeypatch.setattr(replies, "mark_inbox_error", lambda entry_id, error: None)
    monkeypatch.setattr(replies, "insert_reply", lambda **kwargs: 1)
    monkeypatch.setattr(replies, "mark_inbox_processed", lambda *args, **kwargs: None)
    monkeypatch.setattr(replies, "resolve_email_id_by_sender", lambda _: None)
    monkeypatch.setattr(replies.llm, "generate", lambda _: "not-json")

    result = replies.process_inbox_replies()
    assert result.processed_entries == 0
    assert len(result.errors) == 1
    assert "classification failed" in result.errors[0]
