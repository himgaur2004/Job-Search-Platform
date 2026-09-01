from services.resilience import CircuitBreaker


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker("test", failure_threshold=2, reset_timeout_seconds=10)
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.allow() is False
