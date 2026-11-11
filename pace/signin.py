"""Entra sign-in for a public client: auth code + PKCE, redirect to a one-shot loopback server (mocks A2-A5). No GTK."""

from __future__ import annotations

import base64
import hashlib
import html
import secrets
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

from pace.client import urllib_send

LOGIN = "https://login.microsoftonline.com"


def challenge(verifier: str) -> str:
    """PKCE S256 (RFC 7636): base64url(sha256(verifier)) without padding."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def authorize_url(*, tenant: str, client_id: str, scope: str, redirect: str, verifier: str, state: str) -> str:
    query = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect,
        "scope": scope,
        "code_challenge": challenge(verifier),
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{LOGIN}/{tenant}/oauth2/v2.0/authorize?{urllib.parse.urlencode(query)}"


def redeem(*, tenant: str, client_id: str, scope: str, redirect: str, code: str, verifier: str, post_form) -> str:
    """Trade the auth code for the Entra access token. Public client: the PKCE verifier stands in for a secret."""
    form = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect,
        "code_verifier": verifier,
        "scope": scope,
    }
    status, body = post_form(f"{LOGIN}/{tenant}/oauth2/v2.0/token", form)
    if status != 200:
        raise SignInError(body.get("error_description") or body.get("error") or f"token endpoint returned {status}")
    return body["access_token"]


def urllib_post_form(url: str, form: dict, timeout: float = 20) -> tuple[int, dict]:
    req = urllib.request.Request(url, urllib.parse.urlencode(form).encode(), {"Accept": "application/json"}, method="POST")
    return urllib_send(req, timeout)


class SignInError(Exception):
    """Microsoft refused, the person cancelled, or the redirect didn't come back from our own request."""


# The page the browser lands on after Microsoft redirects back. Self-contained (no network), light and dark.
PAGE = """<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{title} · Pace</title>
<style>
:root{{--bg:#f5f6f8;--card:#fff;--ink:#1c2430;--sub:#5d6775;--line:#e3e6ea;--ok:#2ea56f;--bad:#d6453d}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16191e;--card:#1f242b;--ink:#eef1f4;--sub:#9aa4b1;--line:#2d343d;--ok:#57d19a;--bad:#ff7b63}}}}
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,"Segoe UI",Inter,Cantarell,system-ui,sans-serif;padding:24px}}
main{{width:100%;max-width:420px;background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:40px 36px 28px;text-align:center;box-shadow:0 12px 40px rgba(0,0,0,.08)}}
.mark{{width:64px;height:64px;margin:0 auto 20px;position:relative}}
.badge{{position:absolute;right:-6px;bottom:-6px;width:28px;height:28px;border-radius:50%;background:var({tone});
border:3px solid var(--card);display:grid;place-items:center}}
h1{{font-size:21px;font-weight:650;margin:0 0 8px;letter-spacing:-.01em}}
p{{margin:0;color:var(--sub)}}
.detail{{margin-top:16px;padding:10px 12px;border-radius:10px;background:var(--bg);font:12.5px/1.45 ui-monospace,monospace;
color:var(--sub);text-align:left;word-break:break-word}}
footer{{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);font-size:12.5px;color:var(--sub)}}
</style>
<main>
<div class=mark>
<svg viewBox="0 0 128 128" width="64" height="64" aria-hidden="true"><rect x="8" y="8" width="112" height="112" rx="26" fill="#1c2a3a"/>
<circle cx="64" cy="64" r="36" fill="none" stroke="#3b4d63" stroke-width="12"/><circle cx="64" cy="64" r="36" fill="none" stroke="#57d19a"
stroke-width="12" stroke-linecap="round" stroke-dasharray="170 226" transform="rotate(-90 64 64)"/><circle cx="64" cy="64" r="6" fill="#fff"/></svg>
<span class=badge><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">{glyph}</svg></span>
</div>
<h1>{title}</h1>
<p>{text}</p>{detail}
<footer>Pace · billed hours and the loss-of-pay line, at a glance</footer>
</main></html>"""
OK_GLYPH = (
    '<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
)
BAD_GLYPH = '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>'


def result_page(query: dict) -> bytes:
    """What the browser shows: signed in, or why not (Microsoft's own words, escaped)."""
    if "error" in query:
        why = html.escape(query.get("error_description") or query["error"])
        return PAGE.format(
            title="Sign-in didn't finish",
            tone="--bad",
            glyph=BAD_GLYPH,
            text="Microsoft didn't complete the sign-in. Go back to Pace and choose Sign in to try again.",
            detail=f"<div class=detail>{why}</div>",
        ).encode()
    return PAGE.format(
        title="You're signed in",
        tone="--ok",
        glyph=OK_GLYPH,
        text="Pace is fetching your hours now. You can close this tab.",
        detail="",
    ).encode()


class Loopback:
    """One-shot redirect catcher on 127.0.0.1 with a free port (mock A5). Use as a context manager."""

    def __enter__(self) -> Loopback:
        self.query: dict = {}
        self.got = threading.Event()
        loopback = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}
                if loopback.got.is_set() or not ({"code", "error"} & query.keys()):  # e.g. the browser's /favicon.ico
                    self.send_error(404)
                    return
                loopback.query = query
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(result_page(query))
                loopback.got.set()

            def log_message(self, *_):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.redirect = f"http://127.0.0.1:{self.server.server_port}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def wait(self, state: str, timeout: float = 300) -> str:
        if not self.got.wait(timeout):
            raise SignInError("no answer from the browser")
        q = self.query
        if "error" in q:
            raise SignInError(q.get("error_description") or q["error"])
        if q.get("state") != state:
            raise SignInError("state mismatch: this redirect wasn't from Pace's own sign-in")
        return q["code"]

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()


@dataclass(frozen=True)
class Config:
    base_url: str  # hrms-api, e.g. https://<host>/api
    tenant: str  # Osmosys Entra tenant id: hrms-api checks the token's tid against it
    client_id: str  # the "Pace" public-client registration (decision 2)
    api_client_id: str  # hrms-api's MS_SSO_CLIENT_ID: the token's audience

    @property
    def scope(self) -> str:
        return f"api://{self.api_client_id}/access_as_user"


def sign_in_flow(cfg: Config, hrms, open_uri, post_form=urllib_post_form, timeout: float = 300) -> None:
    """Browser sign-in (A3-A5), then swap the Entra token for an HRMS session saved by hrms.sign_in."""
    verifier, state = secrets.token_urlsafe(48), secrets.token_urlsafe(16)
    with Loopback() as lb:
        ids = {"tenant": cfg.tenant, "client_id": cfg.client_id, "scope": cfg.scope, "redirect": lb.redirect}
        open_uri(authorize_url(**ids, verifier=verifier, state=state))
        code = lb.wait(state, timeout)
    hrms.sign_in(redeem(**ids, code=code, verifier=verifier, post_form=post_form))
