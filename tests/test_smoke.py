from agents.state import initial_state


def test_initial_state_has_expected_keys():
    state = initial_state(
        {
            "company": "A",
            "title": "B",
            "url": "https://example.com",
            "jd_text": "jd",
            "source": "src",
        }
    )
    assert state["already_sent"] is False
    assert isinstance(state["errors"], list)
