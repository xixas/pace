"""Pure copy and decisions for the onboarding screens A2-A10 (wording from docs/design.html). No GTK."""

from __future__ import annotations

import urllib.parse

from pace.client import Offline, SignedOut
from pace.signin import SignInError

FAILURES = {
    "cancelled": {
        "icon": "dialog-error-symbolic",
        "title": "You cancelled",
        "body": "Sign-in wasn't completed, so nothing was saved.",
        "button": "Try again",
        "extra": None,
    },
    "admin": {
        "icon": "dialog-warning-symbolic",
        "title": "Your organisation must approve Pace first",
        "body": "An admin needs to allow Pace once for Osmosys. Ask IT.",
        "button": "Try again",
        "extra": "Copy message for IT",
    },
    "personal": {
        "icon": "avatar-default-symbolic",
        "title": "Use your Osmosys account",
        "body": "That was a personal Microsoft account. Sign in with your @osmosys.co address.",
        "button": "Sign in again",
        "extra": None,
    },
    "timeout": {
        "icon": "preferences-system-time-symbolic",
        "title": "The browser never came back",
        "body": "Pace waited 5 minutes for the sign-in to finish.",
        "button": "Try again",
        "extra": None,
    },
    "offline": {
        "icon": "network-offline-symbolic",
        "title": "No network",
        "body": "Pace can't reach Microsoft or DhiHRMS. Check your connection.",
        "button": "Retry",
        "extra": None,
    },
    "other": {
        "icon": "dialog-error-symbolic",
        "title": "Sign-in didn't work",
        "body": "Something went wrong. Try again; if it keeps happening, ask whoever shared Pace with you.",
        "button": "Try again",
        "extra": None,
    },
}
PERMISSIONS = ("Sign you in", "Read your profile", "Access DhiHRMS as you")


def classify_failure(exc: BaseException) -> str:
    """Map what sign_in_flow raised to one of FAILURES (A7 a-e)."""
    text = str(exc).lower()
    if isinstance(exc, SignInError):
        if any(w in text for w in ("access_denied", "declined", "cancel")):
            return "cancelled"
        if any(w in text for w in ("admin", "consent_required", "aadsts65001", "aadsts90094")):
            return "admin"
        if "no answer" in text:
            return "timeout"
        return "other"
    if isinstance(exc, SignedOut):
        return "personal" if any(w in text for w in ("tenant", "personal", "osmosys", "outlook", "live.com")) else "other"
    if isinstance(exc, Offline | OSError):
        return "offline"
    return "other"


def it_request() -> str:
    perms = "\n".join(f"- {p}" for p in PERMISSIONS)
    return (
        'Hi IT, please allow the app "Pace" once for our Osmosys Microsoft tenant, so staff can sign in to it.\n'
        f"It asks for these permissions:\n{perms}\n"
        "Pace only reads the signed-in person's own billed hours, leave and holidays through hrms-api. Thank you."
    )


def listening_port(authorize_url: str) -> int | None:
    """A3 shows "Pace is waiting on 127.0.0.1:<port>": the port is inside the authorize URL's redirect_uri."""
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(authorize_url).query))
    return urllib.parse.urlsplit(query.get("redirect_uri", "")).port


def cancel_url(redirect: str) -> str:
    """Hitting the one-shot loopback with an error makes its wait() raise, which ends sign_in_flow's thread on Cancel."""
    return redirect + "?" + urllib.parse.urlencode({"error": "access_denied", "error_description": "Pace sign-in cancelled"})


def topbar_kind(xdg_current_desktop: str) -> str:
    """A10: GNOME needs its panel extension switched on; everywhere else Pace is a tray icon."""
    return "gnome" if "GNOME" in xdg_current_desktop.upper().split(":") else "tray"


def _days(n: float) -> str:
    return "none" if not n else f"{n:g} day" + ("s" if n > 1 else "")


def summary(profile: dict | None, holidays: int | None, leave_days: float | None, year: int = 2026) -> dict:
    """A6: proof that every data source resolved."""
    name = (profile or {}).get("name")
    return {
        "headline": f"Signed in as {name}" if name else "Signed in",
        "email": (profile or {}).get("email") or "",
        "rows": [
            ("DhiHRMS employee linked", ""),
            ("PineStem account", "linked" if (profile or {}).get("pinestem_mapped") else "not linked"),
            (f"Holidays {year}", "–" if holidays is None else str(holidays)),
            ("Leave this month", "–" if leave_days is None else _days(leave_days)),
        ],
    }
