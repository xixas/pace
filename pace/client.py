"""hrms-api client: the Entra → HRMS token exchange, refresh, and the two Pace endpoints. No GTK."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date

from pace import profile


class Offline(Exception):
    """hrms-api or the network is unreachable: keep the last good numbers."""


class WalletLocked(Offline):
    """The keyring (KWallet, GNOME Keyring) hasn't answered yet, usually locked at login: keep the numbers, retry like offline."""


class SignedOut(Exception):
    """The HRMS session is gone and can't be refreshed: the person signs in again."""


class Client:
    """store: load() / save() of {"access", "refresh"}. transport(method, url, headers, body) → (status, json body)."""

    def __init__(self, base_url: str, store, transport):
        self.base, self.store, self.transport = base_url.rstrip("/"), store, transport

    def my_hours(self, start: date, end: date, fresh: bool = False) -> list[dict]:
        """fresh=True skips hrms-api's cache (it allows one such call a minute)."""
        return self.get(f"/billing-report/my-hours/?from={start}&to={end}{'&fresh=1' if fresh else ''}")

    def my_days(self, start: date, end: date) -> list[dict]:
        return self.get(f"/calendar/my-days/?from={start}&to={end}")

    def get(self, path: str) -> list[dict]:
        status, body = self.send("GET", path)
        if status == 401:
            self.refresh()
            status, body = self.send("GET", path)
        return body["data"]

    def send(self, method: str, path: str, body: dict | None = None, auth: bool = True) -> tuple[int, dict]:
        headers = {"Authorization": f"Bearer {self.tokens()['access']}"} if auth else {}
        try:
            status, reply = self.transport(method, self.base + path, headers, body)
        except OSError as e:
            raise Offline(str(e)) from e
        if status >= 500:
            raise Offline(f"{status} {reply.get('message', '')}")
        return status, reply

    def tokens(self) -> dict:
        tokens = self.store.load()
        if not tokens:
            raise SignedOut("no HRMS session saved")
        return tokens

    def sign_in(self, entra_token: str) -> None:
        """Swap the Entra access_as_user token for an HRMS session (access 8 h, refresh 30 d). This reply has an envelope."""
        status, body = self.send("POST", "/auth/microsoft/", {"token": entra_token}, auth=False)
        if status != 200:
            raise SignedOut(body.get("message", f"sign-in returned {status}"))
        self.store.save({"access": body["data"]["access"], "refresh": body["data"]["refresh"]})
        profile.write(body["data"].get("user"))

    def refresh(self) -> None:
        """Refresh tokens rotate: the old one is blacklisted, so save the new pair every time. The body is bare."""
        status, body = self.send("POST", "/auth/refresh/", {"refresh": self.tokens()["refresh"]}, auth=False)
        if status != 200:
            raise SignedOut(body.get("message", f"refresh returned {status}"))
        self.store.save({"access": body["access"], "refresh": body["refresh"]})


def urllib_transport(method: str, url: str, headers: dict, body: dict | None, timeout: float = 20) -> tuple[int, dict]:
    """The real transport: JSON in, (status, JSON body) out, HTTP errors included. Network failures raise OSError."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data, {**headers, "Content-Type": "application/json", "Accept": "application/json"}, method=method
    )
    return urllib_send(req, timeout)


def urllib_send(req: urllib.request.Request, timeout: float = 20) -> tuple[int, dict]:
    """(status, JSON body) for any reply, HTTP errors included. Network failures raise OSError."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
