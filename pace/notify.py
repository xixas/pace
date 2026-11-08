"""Nudges (design C6): which are due, what they say, and sending them over org.freedesktop.Notifications. No GTK, no libnotify.

due() reads only the status dict, so what a nudge says always agrees with what the panel shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from pace.engine import MAXDAY, hours
from pace.status import lop_text

OPEN_PINESTEM = [("pinestem", "Open PineStem"), ("snooze", "Snooze today")]
QUIET_STATES = ("offline", "signed_out", "no_mapping", "on_leave")
OFF_DAYS = ("holiday", "leave", "weekend")


@dataclass(frozen=True)
class Nudge:
    key: str  # at most one per day; also the dedupe key
    title: str
    body: str
    actions: list[tuple[str, str]]


def due(s: dict, settings: dict, now: datetime, sent: dict, summary: dict | None = None) -> list[Nudge]:
    """Nudges to send now. sent is {iso date: [keys]}: what already went out. summary: last week's result (Monday nudge)."""
    if s["state"] in QUIET_STATES or s["snoozed_until"] or not s["days"]:
        return []
    today = day_row(s, now)
    if not today or today["kind"] in OFF_DAYS:
        return []
    done = sent.get(now.date().isoformat(), [])
    out = []
    for kind, rule in RULES.items():
        cfg = settings["notify"][kind]
        if cfg["on"] and now.time() >= time.fromisoformat(cfg["at"]):
            out += [n for n in rule(s, now, today, summary) if n.key not in done]
    return out


def signed_out(s: dict, settings: dict, already: bool, paused_at: datetime | None) -> Nudge | None:
    """The one notification for an expired session; the caller remembers it was sent until the next sign-in."""
    if already or not settings["notify"]["signed_out"]["on"]:
        return None
    body = "Your Microsoft session has expired."
    if paused_at:
        body += f" Numbers are paused at {paused_at:%H:%M}."
    return Nudge("signed_out", "Sign in again", body, [("signin", "Sign in"), ("dismiss", "Later")])


def day_row(s: dict, now: datetime) -> dict | None:
    return next((d for d in s["days"] if d["date"] == now.date().isoformat()), None)


def friday(s, now, today, summary):
    working = [d for d in s["days"] if d["kind"] not in OFF_DAYS]
    left = s["target_min"] - s["logged_min"]
    if s["state"] == "done" or left <= 0 or working[-1]["date"] != today["date"]:
        return []
    name = "Friday" if now.weekday() == 4 else "Last day"
    title = f"{name} check: {hours(left)} h left to reach {hours(s['target_min'])}"
    return [Nudge("friday", title, "Bill your work before you log off.", OPEN_PINESTEM)]


def pay_risk(s, now, today, summary):
    if s["state"] != "pay_risk":
        return []
    need = s["lines"]["lop_min"] - s["logged_min"]
    body = f"{hours(s['logged_min'])} h by {now:%a %H:%M} needs {hours(need)} h today, more than {hours(MAXDAY)}."
    body += f" {s['warning']}." if s["warning"] else ""
    return [Nudge("pay_risk", "Pay at risk: 41 h is out of reach", body + " Bill missing hours now.", OPEN_PINESTEM)]


def daily(s, now, today, summary):
    left = [d for d in s["days"] if d["kind"] in ("future", "half_leave") and d["date"] > today["date"]]
    if s["state"] == "pay_risk" and left:
        need = (s["lines"]["lop_min"] - s["logged_min"]) / len(left)
        name, nxt = now.strftime("%A"), day_name(left[0])
        body = (
            f"{name} has {today['text']} h. Reaching the {hours(s['lines']['lop_min'], trim=True)} h line needs {hours(need)} h on {nxt}, "
            f"more than {hours(MAXDAY)}. Bill the rest of {name} now."
        )
        return [Nudge("daily", "Pay at risk this week", body, OPEN_PINESTEM)]
    title = f"{today['dow']}: {hours(today['min'] or 0)} h billed"
    return [Nudge("daily", title, f"Week {hours(s['logged_min'])} / {hours(s['target_min'])} h.", OPEN_PINESTEM)]


def day_name(d: dict) -> str:
    return datetime.fromisoformat(d["date"]).strftime("%A")


def zero_hour(s, now, today, summary):
    return [
        Nudge(
            f"zero_hour:{d['date']}",
            f"{day_name(d)} has 0 h billed",
            "Forgot to bill? Add it before the week closes.",
            OPEN_PINESTEM,
        )
        for d in s["days"]
        if d["kind"] == "short" and d["min"] == 0 and d["date"] < today["date"]
    ]


def project_behind(s, now, today, summary):
    month = s["month"] or {}
    behind = [p for p in month.get("projects", []) if p["short"]]
    if not behind:
        return []
    p = min(behind, key=lambda p: p["gap_min"])
    rest = [d["dow"] for d in s["days"] if d["kind"] in ("today", "future")]
    body = f"{hours(p['billed_min'])} of {hours(p['target_min'], trim=True)} h."
    if rest and p["need_per_day_min"]:
        span = rest[0] if len(rest) == 1 else f"{rest[0]}–{rest[-1]}"
        body += f" {hours(p['need_per_day_min'])} h/day needed on {span}."
    title = f"{p['name']} is {hours(-p['gap_min'])} h behind for {month['name']}"
    return [Nudge(f"project_behind:{p['code']}", title, body, OPEN_PINESTEM)]


def monday(s, now, today, summary):
    first_working = next(d for d in s["days"] if d["kind"] not in OFF_DAYS)
    if not summary or first_working["date"] != today["date"]:
        return []
    h, target, lop = hours(summary["logged_min"]), hours(summary["target_min"]), summary["lop_days"]
    if lop:
        title, body = f"Last week {h} h · {lop_text(lop)}", "Under the pay line."
    elif summary["logged_min"] >= summary["target_min"]:
        title, body = f"Last week {h} h ✓", f"Above the {target} h target."
    else:
        title, body = f"Last week {h} h", f"Below the {target} h target, pay safe."
    month = s["month"] or {}
    p = next((p for p in month.get("projects", []) if p["target_min"] is not None), None)
    if p:
        body += f" {p['name']} {hours(p['billed_min'])} / {hours(p['target_min'], trim=True)} h for {month['name']}."
    return [Nudge("monday", title, body, [("dashboard", "Open dashboard"), ("dismiss", "Dismiss")])]


RULES = {
    "pay_risk": pay_risk,
    "friday": friday,
    "daily": daily,
    "monday": monday,
    "zero_hour": zero_hour,
    "project_behind": project_behind,
}


class Notifier:
    """Sends nudges over the session bus and reports button clicks to on_action(action_id)."""

    def __init__(self, bus, on_action):
        from gi.repository import Gio

        self.bus, self.on_action, self.Gio = bus, on_action, Gio
        bus.signal_subscribe(
            "org.freedesktop.Notifications",
            "org.freedesktop.Notifications",
            "ActionInvoked",
            "/org/freedesktop/Notifications",
            None,
            Gio.DBusSignalFlags.NONE,
            self.invoked,
        )
        self.ours: set[int] = set()

    def send(self, n: Nudge) -> None:
        from gi.repository import GLib

        flat = [x for action in n.actions for x in action]
        args = GLib.Variant(
            "(susssasa{sv}i)",
            (
                "Pace",
                0,
                "io.github.xixas.Pace",
                n.title,
                n.body,
                flat,
                {"desktop-entry": GLib.Variant("s", "io.github.xixas.Pace")},
                -1,
            ),
        )
        self.bus.call(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "Notify",
            args,
            GLib.VariantType("(u)"),
            self.Gio.DBusCallFlags.NONE,
            -1,
            None,
            self.sent,
        )

    def sent(self, bus, result) -> None:
        try:
            self.ours.add(bus.call_finish(result).unpack()[0])
        except Exception:  # no notification daemon on this desktop: nudges are a courtesy
            pass

    def invoked(self, _bus, _sender, _path, _iface, _signal, params) -> None:
        nid, action = params.unpack()
        if nid in self.ours:
            self.on_action(action)
