"""A test-only access gate, independent of the application's Bearer tokens."""
import hashlib
import hmac
import html
import os
import time
from urllib.parse import parse_qs, urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

COOKIE = "__Host-trel_preview"
SESSION_SECONDS = 8 * 60 * 60
LOGIN_PATH = "/_preview/login"
HEALTH_PATH = "/_preview/health"


def safe_next(value):
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "/"
    return value if (value.startswith("/") and not value.startswith("//")
                     and not parsed.scheme and not parsed.netloc
                     and not any(ord(c) < 32 or c == "\\" for c in value)) else "/"


class PrivatePreviewMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, access_key):
        super().__init__(app)
        self.key = access_key.encode()

    def signature(self, expires):
        return hmac.new(self.key, f"trel-preview:{expires}".encode(), hashlib.sha256).hexdigest()

    def authenticated(self, request):
        try:
            expires, signature = request.cookies.get(COOKIE, "").split(".", 1)
            timestamp = int(expires)
            return (time.time() < timestamp <= time.time() + SESSION_SECONDS
                    and hmac.compare_digest(signature, self.signature(expires)))
        except (ValueError, TypeError):
            return False

    @staticmethod
    def page(destination, error=""):
        return HTMLResponse(f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private TREL workspace</title><style>
body{{font:17px system-ui;background:#f1f5f9;color:#0f172a;margin:12vh auto;padding:24px;max-width:440px}}
form{{background:white;padding:28px;border-radius:16px}}input,button{{box-sizing:border-box;width:100%;padding:12px;margin-top:12px;font:inherit}}
button{{background:#075c36;color:white;border:0;border-radius:8px}}p{{line-height:1.5}}
</style><form action="{LOGIN_PATH}" method="post"><h1>Private TREL workspace</h1>
<p>Enter your workspace access key to continue.</p>
<p role="alert">{html.escape(error)}</p>
<label>Workspace access key<input type="password" name="access_key" required autocomplete="current-password"></label>
<input type="hidden" name="next" value="{html.escape(destination, quote=True)}">
<button>Open workspace</button></form></html>""", status_code=401,
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow",
                     "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"})

    async def dispatch(self, request, call_next):
        # Fail closed even when a deploy secret was omitted. This endpoint
        # exposes no application content and is used by Fly's health check.
        if len(self.key) < 32:
            return Response("Private workspace access is not configured.", 503,
                            headers={"Cache-Control": "no-store"})
        if request.url.path == HEALTH_PATH and request.method in {"GET", "HEAD"}:
            return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
        if request.url.path == LOGIN_PATH and request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin != f"https://{request.url.netloc}":
                return Response("Invalid origin", 403)
            raw = b""
            async for chunk in request.stream():
                raw += chunk
                if len(raw) > 4096:
                    return Response("Request too large", 413)
            form = parse_qs(raw.decode("utf-8", errors="replace"))
            destination = safe_next(form.get("next", ["/"])[0])
            key = form.get("access_key", [""])[0].encode()
            if not hmac.compare_digest(key, self.key):
                return self.page(destination, "The access key is incorrect.")
            expires = str(int(time.time()) + SESSION_SECONDS)
            response = RedirectResponse(destination, status_code=303)
            response.set_cookie(COOKIE, f"{expires}.{self.signature(expires)}",
                                max_age=SESSION_SECONDS, secure=True, httponly=True,
                                samesite="lax", path="/")
            response.headers["Cache-Control"] = "no-store"
            return response
        if not self.authenticated(request):
            destination = safe_next(request.url.path + (f"?{request.url.query}" if request.url.query else ""))
            return self.page(destination)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response


def install_private_preview(app):
    if (os.getenv("FLY_APP_NAME") == "trelweb-test"
            or os.getenv("TREL_PRIVATE_PREVIEW") == "required"):
        app.add_middleware(PrivatePreviewMiddleware,
                           access_key=os.getenv("TREL_PREVIEW_ACCESS_KEY", ""))
