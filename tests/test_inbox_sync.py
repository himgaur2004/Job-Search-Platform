from services import inbox_sync


def test_extract_sender_email():
    raw = "Recruiter Name <recruiter@example.com>"
    assert inbox_sync._extract_sender_email(raw) == "recruiter@example.com"


def test_extract_body_uses_snippet_when_no_parts():
    payload = {"headers": []}
    assert inbox_sync._extract_body(payload, "fallback snippet") == "fallback snippet"


def test_sync_inbox_skips_existing_messages(monkeypatch):
    class FakeGetCall:
        def execute(self):
            return {
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Recruiter <recruiter@example.com>"},
                        {"name": "Subject", "value": "Interview"},
                    ],
                    "body": {"data": "SGVsbG8="},
                },
                "threadId": "t-100",
                "internalDate": "1720000000000",
                "snippet": "Hello",
            }

    class FakeMessagesAPI:
        def list(self, userId, q, maxResults):
            class Call:
                def execute(self):
                    return {"messages": [{"id": "m1"}, {"id": "m2"}]}

            return Call()

        def get(self, userId, id, format):
            return FakeGetCall()

    class FakeUsersAPI:
        def messages(self):
            return FakeMessagesAPI()

    class FakeService:
        def users(self):
            return FakeUsersAPI()

    monkeypatch.setattr(inbox_sync, "build_gmail_service", lambda: FakeService())
    monkeypatch.setattr(inbox_sync, "list_known_recruiter_emails", lambda limit=1000: ["recruiter@example.com"])
    monkeypatch.setattr(inbox_sync, "list_known_gmail_threads", lambda limit=1000: ["t-100"])
    monkeypatch.setattr(inbox_sync, "inbox_message_exists", lambda message_id: message_id == "m1")

    inserted: list[str] = []

    def fake_insert_inbox_entry(**kwargs):
        inserted.append(kwargs["gmail_message_id"])
        assert kwargs["gmail_thread_id"] == "t-100"
        return 1

    monkeypatch.setattr(inbox_sync, "insert_inbox_entry", fake_insert_inbox_entry)
    result = inbox_sync.sync_inbox_from_gmail(limit=10)
    assert result.fetched_messages == 2
    assert result.inserted_entries == 1
    assert inserted == ["m2"]
