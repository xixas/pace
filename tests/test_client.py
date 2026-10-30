"""hrms-api client against a fake transport. Contract from hrms-api feat/pace-my-hours-my-days (2026-10-30)."""

from datetime import date

import pytest

from pace.client import Client, Offline, SignedOut

BASE = "https://hrms.example/api"


class Store:
    def __init__(self, tokens=None):
        self.tokens = tokens

    def load(self):
        return self.tokens

    def save(self, tokens):
        self.tokens = tokens


class Transport:
    """Answers (method, path) from a script of (status, body) replies and records every request."""

    def __init__(self, replies):
        self.replies, self.requests = replies, []

    def __call__(self, method, url, headers, body):
        self.requests.append((method, url, headers.get("Authorization"), body))
        path = url.removeprefix(BASE).split("?")[0]
        return self.replies[(method, path)].pop(0)


def test_my_hours_sends_the_hrms_access_token_and_returns_the_rows():
    rows = [{"date": "2026-11-02", "project_id": 7, "project_name": "TWE", "billable_min": 510, "non_billable_min": 0}]
    t = Transport({("GET", "/billing-report/my-hours/"): [(200, {"success": True, "count": 1, "data": rows})]})
    c = Client(BASE, Store({"access": "A1", "refresh": "R1"}), t)
    assert c.my_hours(date(2026, 10, 26), date(2026, 11, 8)) == rows
    assert t.requests == [("GET", f"{BASE}/billing-report/my-hours/?from=2026-10-26&to=2026-11-08", "Bearer A1", None)]


def test_expired_access_refreshes_once_saves_the_rotated_pair_and_retries():
    store = Store({"access": "A1", "refresh": "R1"})
    t = Transport(
        {
            ("GET", "/calendar/my-days/"): [
                (401, {"success": False, "message": "expired"}),
                (200, {"success": True, "count": 0, "data": []}),
            ],
            ("POST", "/auth/refresh/"): [(200, {"access": "A2", "refresh": "R2"})],  # bare body, no envelope
        }
    )
    assert Client(BASE, store, t).my_days(date(2026, 10, 26), date(2026, 11, 8)) == []
    assert [(m, a, b) for m, _, a, b in t.requests] == [
        ("GET", "Bearer A1", None),
        ("POST", None, {"refresh": "R1"}),
        ("GET", "Bearer A2", None),
    ]
    assert store.tokens == {"access": "A2", "refresh": "R2"}


def test_rejected_refresh_or_no_tokens_is_signed_out():
    t = Transport(
        {
            ("GET", "/calendar/my-days/"): [(401, {})],
            ("POST", "/auth/refresh/"): [(401, {"success": False, "message": "blacklisted"})],
        }
    )
    with pytest.raises(SignedOut):
        Client(BASE, Store({"access": "A1", "refresh": "R1"}), t).my_days(date(2026, 10, 26), date(2026, 11, 8))
    with pytest.raises(SignedOut):
        Client(BASE, Store(None), Transport({})).my_days(date(2026, 10, 26), date(2026, 11, 8))


@pytest.mark.parametrize("reply", [OSError("no route to host"), (502, {"success": False, "message": "bad gateway"})])
def test_network_error_or_server_error_is_offline(reply):
    def transport(*_):
        if isinstance(reply, Exception):
            raise reply
        return reply

    with pytest.raises(Offline):
        Client(BASE, Store({"access": "A1", "refresh": "R1"}), transport).my_hours(date(2026, 10, 26), date(2026, 11, 8))


def test_sign_in_exchanges_the_entra_token_for_an_hrms_session():
    store = Store()
    login = {
        "success": True,
        "message": "Login successful",
        "data": {"access": "A1", "refresh": "R1", "user": {}, "role_info": {}},
    }
    t = Transport({("POST", "/auth/microsoft/"): [(200, login)]})
    Client(BASE, store, t).sign_in("entra-jwt")
    assert t.requests == [("POST", f"{BASE}/auth/microsoft/", None, {"token": "entra-jwt"})]
    assert store.tokens == {"access": "A1", "refresh": "R1"}


def test_refused_sign_in_carries_the_servers_message():
    t = Transport({("POST", "/auth/microsoft/"): [(403, {"success": False, "message": "Client not allowed"})]})
    with pytest.raises(SignedOut, match="Client not allowed"):
        Client(BASE, Store(), t).sign_in("entra-jwt")


def test_urllib_transport_sends_json_and_returns_status_and_body_even_on_errors():
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from pace.client import urllib_transport

    class Echo(BaseHTTPRequestHandler):
        def do_POST(self):
            got = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            reply = json.dumps({"got": got, "auth": self.headers.get("Authorization")}).encode()
            self.send_response(401 if got.get("fail") else 200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(reply)

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/x"
    try:
        assert urllib_transport("POST", url, {"Authorization": "Bearer A1"}, {"a": 1}) == (
            200,
            {"got": {"a": 1}, "auth": "Bearer A1"},
        )
        assert urllib_transport("POST", url, {}, {"fail": True}) == (401, {"got": {"fail": True}, "auth": None})
    finally:
        server.shutdown()
