"""Entra sign-in for a public client: auth code + PKCE, redirect to a one-shot loopback server (mocks A2-A5). No GTK."""

from __future__ import annotations

import base64
import hashlib
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


DONE_PAGE = b"""<!doctype html><meta charset=utf-8><title>Pace</title>
<body style="font:16px system-ui;margin:4em auto;max-width:28em"><h2>Signed in to Pace</h2><p>You can close this tab.</p>"""


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
                self.wfile.write(DONE_PAGE)
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
