from zrb.llm.config.http_client import create_retrying_http_client


def test_create_retrying_http_client_returns_none_when_disabled():
    """max_attempts <= 1 must disable retrying (no transport wrapping)."""
    assert create_retrying_http_client(max_attempts=0, max_wait=60) is None
    assert create_retrying_http_client(max_attempts=1, max_wait=60) is None


def test_create_retrying_http_client_returns_client_when_enabled():
    """max_attempts > 1 must return a usable httpx AsyncClient."""
    import httpx

    client = create_retrying_http_client(max_attempts=3, max_wait=60)
    assert isinstance(client, httpx.AsyncClient)
