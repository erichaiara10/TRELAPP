"""Shared test fixtures.

Iteration 32 added Cloudflare Turnstile enforcement on POST /auth/login and
POST /auth/register. Every legacy test in this suite logs in without a
`turnstile_token`, which now returns 400. Rather than editing 15+ files, we
patch `requests` at the session level to inject Cloudflare's always-passing
sitewide test token for auth calls.

Opt-out: pass the `turnstile_token` key explicitly (even as None or "") in the
JSON body — the patch never overwrites a key that the caller supplied. Negative
tests in test_iter32_turnstile.py rely on this.
"""
import pytest
import requests

TURNSTILE_TEST_TOKEN = "1x0000000000000000000000000000AA"
AUTH_PATHS = ("/auth/login", "/auth/register")


def _inject(url, kwargs):
    if not isinstance(url, str) or not any(p in url for p in AUTH_PATHS):
        return
    body = kwargs.get("json")
    if isinstance(body, dict) and "turnstile_token" not in body:
        body["turnstile_token"] = TURNSTILE_TEST_TOKEN


@pytest.fixture(scope="session", autouse=True)
def turnstile_autotoken():
    original_session_request = requests.Session.request
    original_api_request = requests.api.request

    def session_request(self, method, url, *args, **kwargs):
        _inject(url, kwargs)
        return original_session_request(self, method, url, *args, **kwargs)

    def api_request(method, url, **kwargs):
        _inject(url, kwargs)
        return original_api_request(method, url, **kwargs)

    requests.Session.request = session_request
    requests.api.request = api_request
    requests.request = api_request
    yield
    requests.Session.request = original_session_request
    requests.api.request = original_api_request
    requests.request = original_api_request
