import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.private_preview import COOKIE, PrivatePreviewMiddleware, install_private_preview, safe_next

KEY = "controlled-test-key-with-at-least-32-characters"


def client(key=KEY):
    app = FastAPI()
    @app.get("/{path:path}")
    def content(path):
        return {"private": path}
    app.add_middleware(PrivatePreviewMiddleware, access_key=key)
    return TestClient(app, base_url="https://testserver")


def test_html_static_and_api_are_private_and_missing_secret_fails_closed():
    with client() as c:
        for path in ("/", "/add-property", "/static/js/main.js", "/api/", "/docs", "/openapi.json"):
            response = c.get(path)
            assert response.status_code == 401
            assert response.headers["cache-control"] == "no-store"
        assert c.get("/_preview/health").json() == {"ok": True}
    with client("") as c:
        assert c.get("/_preview/health").status_code == 503
        assert c.get("/add-property").status_code == 503


def test_cookie_access_preserves_bearer_auth_and_safe_return_path():
    with client() as c:
        assert c.post("/_preview/login", data={"access_key": "wrong"}).status_code == 401
        response = c.post("/_preview/login", data={"access_key": KEY, "next": "/add-property?auth=login"}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/add-property?auth=login"
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "Secure" in response.headers["set-cookie"]
        assert c.get("/api/private", headers={"Authorization": "Bearer account-token"}).json() == {"private": "api/private"}


def test_forged_expired_and_rotated_cookies_are_rejected():
    for cookie in ("99999999999.forged", "invalid", ""):
        with client() as c:
            c.cookies.set(COOKIE, cookie)
            assert c.get("/add-property").status_code == 401
    middleware = PrivatePreviewMiddleware(None, KEY)
    expires = str(int(time.time()) - 1)
    with client() as c:
        c.cookies.set(COOKIE, f"{expires}.{middleware.signature(expires)}")
        assert c.get("/add-property").status_code == 401
    with client() as c:
        c.post("/_preview/login", data={"access_key": KEY})
        cookie = c.cookies.get(COOKIE)
    with client(KEY + "rotated") as c:
        c.cookies.set(COOKIE, cookie)
        assert c.get("/add-property").status_code == 401


def test_login_rejects_cross_origin_and_external_redirects():
    with client() as c:
        assert c.post("/_preview/login", data={"access_key": KEY}, headers={"Origin": "https://other.test"}).status_code == 403
    for path in ("https://other.test", "//other.test", "/\\other.test", "/\nother"):
        assert safe_next(path) == "/"


def test_gate_is_required_on_test_app_and_does_not_change_production(monkeypatch):
    monkeypatch.delenv("TREL_PRIVATE_PREVIEW", raising=False)
    monkeypatch.delenv("TREL_PREVIEW_ACCESS_KEY", raising=False)
    monkeypatch.setenv("FLY_APP_NAME", "trelweb")
    app = FastAPI()
    install_private_preview(app)
    assert not app.user_middleware
    monkeypatch.setenv("FLY_APP_NAME", "trelweb-test")
    install_private_preview(app)
    with TestClient(app) as c:
        assert c.get("/").status_code == 503
