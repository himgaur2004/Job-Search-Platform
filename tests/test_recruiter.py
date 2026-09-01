from services.recruiter import _extract_email_from_text, _guess_email_patterns


def test_extract_email_from_text():
    text = "Please reach out to jane.doe@example.com for next steps."
    assert _extract_email_from_text(text) == "jane.doe@example.com"


def test_guess_email_patterns():
    guesses = _guess_email_patterns("Jane Doe", "example.com")
    assert guesses[0] == "jane@example.com"
    assert "jane.doe@example.com" in guesses
