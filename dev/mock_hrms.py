"""Stand-in for hrms-api's four Pace endpoints, until feat/pace-my-hours-my-days reaches dev.

    python3 dev/mock_hrms.py --data snapshot.json [--port 8001]

snapshot.json is {"hours": [my-hours rows], "days": [my-days rows]}, e.g. pulled from the PineStem and
DhiHRMS MCPs. Keep it outside the repo: it is personal billing data.

Sign-in takes a real Entra token and checks the claims hrms-api checks (tid, aud, azp, scp), but not
the signature: this is a local dev tool, never a server. Sessions are random strings held in memory.
"""

import argparse
import base64
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

TENANT = "95ca85cb-20c9-45c5-bbfc-be2d0ac2e657"
API = "97152fbf-dde7-4077-a876-ea74e8b40b0f"
PACE = "8c8d68c3-01e3-4e4b-aeab-975858570bf9"


def claims(jwt: str) -> dict:
    p = jwt.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))


def refused(c: dict) -> str | None:
    if c.get("tid") != TENANT:
        return "wrong tenant"
    if c.get("aud") not in (API, f"api://{API}"):
        return "wrong audience"
    if (c.get("azp") or c.get("appid", "")).lower() != PACE:
        return "Client not allowed"
    if "access_as_user" not in c.get("scp", "").split():
        return "missing scope access_as_user"
    return None


def serve(data: dict, port: int):
    sessions = {"access": set(), "refresh": set()}

    def issue():
        pair = {"access": secrets.token_urlsafe(24), "refresh": secrets.token_urlsafe(24)}
        sessions["access"].add(pair["access"])
        sessions["refresh"].add(pair["refresh"])
        return pair

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body):
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/auth/microsoft/":
                try:
                    why = refused(claims(body["token"]))
                except (KeyError, IndexError, ValueError):
                    why = "malformed token"
                if why:
                    return self.reply(403, {"success": False, "message": why})
                return self.reply(200, {"success": True, "message": "Login successful", "data": issue()})
            if self.path == "/api/auth/refresh/":
                if body.get("refresh") not in sessions["refresh"]:
                    return self.reply(401, {"success": False, "message": "blacklisted"})
                sessions["refresh"].discard(body["refresh"])  # refresh tokens rotate
                return self.reply(200, issue())  # bare body, no envelope, like hrms-api
            self.reply(404, {"success": False, "message": "not found"})

        def do_GET(self):
            url = urlsplit(self.path)
            key = {"/api/billing-report/my-hours/": "hours", "/api/calendar/my-days/": "days"}.get(url.path)
            if key is None:
                return self.reply(404, {"success": False, "message": "not found"})
            if self.headers.get("Authorization", "").removeprefix("Bearer ") not in sessions["access"]:
                return self.reply(401, {"success": False, "message": "expired"})
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            rows = [r for r in data[key] if q.get("from", "") <= r["date"] <= q.get("to", "9999")]
            self.reply(200, {"success": True, "count": len(rows), "data": rows})

        def log_message(self, fmt, *args):
            print(f"{self.command} {self.path.split('?')[0]} → {args[1] if len(args) > 1 else ''}", flush=True)

    print(f"mock hrms-api on http://127.0.0.1:{port}/api", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--port", type=int, default=8001)
    a = ap.parse_args()
    with open(a.data) as f:
        serve(json.load(f), a.port)
