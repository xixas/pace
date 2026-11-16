"""paced: the headless daemon (Gio only, no GTK). Paints the cached week at login, then polls hrms-api, publishes and nudges."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from pace import profile
from pace.files import read_json, state_dir, write_json
from pace.notify import due, signed_out
from pace.poll import last_week_summary, poll, verdict_status
from pace.settings import Settings
from pace.status import PINESTEM_URL, write_status
from pace.targets import load as load_targets

FRESH_EVERY = timedelta(minutes=1)  # hrms-api allows one fresh fetch a minute
FIRST_RETRY = 30  # seconds: offline at login usually means the network is still coming up


class Daemon:
    """api: pace.client.Client. send(nudge) shows a notification; sign_in() runs the blocking browser flow."""

    def __init__(
        self,
        api,
        clock: Callable[[], datetime] = datetime.now,
        settings: Settings | None = None,
        send: Callable | None = None,
        sign_in: Callable[[], None] | None = None,
        open_url: Callable[[str], None] | None = None,
        spawn: Callable[[list[str]], None] | None = None,
    ):
        self.api, self.clock, self.settings = api, clock, settings or Settings()
        self.send, self.sign_in_flow = send, sign_in
        self.open_url, self.spawn = open_url or open_in_browser, spawn or spawn_pace
        self.state_path = state_dir() / "state.json"
        self.state = read_json(self.state_path) or {}
        self.listeners: list[Callable[[dict], None]] = []  # called with every status written (D-Bus signal, tray)
        self.on_quit: Callable[[], None] = lambda: None
        self.on_signed_in: Callable[[], None] = lambda: None
        self.problem: str | None = None
        self.status: dict | None = None
        self.last_fresh: datetime | None = None
        self.offline_tries = 0
        self.signing_in = False

    def boot(self) -> None:
        """First paint from the saved week, before any network call, so the panel has a number at login."""
        if self.state.get("as_of"):
            self.render()

    def tick(self, fresh: bool = False, backoff: bool = True) -> None:
        """backoff=False: an extra poll (the network came up) that must not push the next retry further out."""
        now = self.clock()
        if not profile.pinestem_mapped():
            self.publish(poll_unmapped(self.settings.data))
            return
        retry = timedelta(seconds=self.offline_delay(self.offline_tries))
        s, self.state = poll(self.api, self.state, now, self.settings.data, load_targets(), fresh, retry)
        self.problem = (s["problem"] or {}).get("kind")
        if self.problem != "offline":
            self.offline_tries = 0
        elif backoff or not self.offline_tries:
            self.offline_tries += 1
        self.save()
        self.publish(s)
        self.nudge(s, now)

    def offline_delay(self, tries: int) -> int:
        """Seconds before retry number tries+1: 30 s doubling up to the refresh interval."""
        return min(FIRST_RETRY * 2**tries, self.settings.data["refresh_minutes"] * 60)

    def next_poll_in(self) -> int:
        """Seconds to the next poll: backing off while offline, else the refresh interval."""
        if self.offline_tries:
            return self.offline_delay(self.offline_tries - 1)
        return self.settings.data["refresh_minutes"] * 60

    def refresh(self) -> None:
        """The panel's Refresh: ask hrms-api to skip its cache, but only once a minute."""
        now = self.clock()
        fresh = self.last_fresh is None or now - self.last_fresh >= FRESH_EVERY
        self.last_fresh = now if fresh else self.last_fresh
        self.tick(fresh=fresh)

    def render(self) -> None:
        """Rebuild the status from the saved week alone (snooze or a settings change): no network."""
        if self.state.get("as_of"):
            self.publish(
                verdict_status(
                    self.state, datetime.fromisoformat(self.state["as_of"]), self.problem, self.settings.data, load_targets()
                )
            )

    def publish(self, s: dict) -> None:
        write_status(s)
        self.status = s
        for listener in self.listeners:
            listener(s)

    def save(self) -> None:
        write_json(self.state_path, self.state)

    def snooze(self) -> None:
        midnight = (self.clock() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.state["snoozed_until"] = midnight.isoformat()
        self.save()
        self.render()

    def unsnooze(self) -> None:
        self.state.pop("snoozed_until", None)
        self.save()
        self.render()

    def nudge(self, s: dict, now: datetime) -> None:
        if not self.send:
            return
        if s["state"] == "signed_out":
            n = signed_out(s, self.settings.data, self.state.get("signed_out_sent", False), paused_at=self.paused_at())
            if n:
                self.state["signed_out_sent"] = True
                self.send(n)
            self.save()
            return
        self.state.pop("signed_out_sent", None)
        today = now.date().isoformat()
        sent = {today: self.state.get("sent", {}).get(today, [])}
        summary = last_week_summary(self.state, now) if self.state.get("days") else None  # no data yet on a first offline start
        for n in due(s, self.settings.data, now, sent, summary):
            sent[today].append(n.key)
            self.send(n)
        self.state["sent"] = sent
        self.save()

    def paused_at(self) -> datetime | None:
        return datetime.fromisoformat(self.state["as_of"]) if self.state.get("as_of") else None

    def action(self, name: str) -> None:
        """A notification button or tray menu entry."""
        {
            "pinestem": lambda: self.open_url(PINESTEM_URL),
            "snooze": self.snooze,
            "unsnooze": self.unsnooze,
            "refresh": self.refresh,
            "dashboard": lambda: self.spawn(["pace"]),
            "widget": self.show_widget,
            "signin": self.sign_in,
            "quit": self.quit,
        }.get(name, lambda: None)()

    def show_widget(self) -> None:
        self.spawn(["pace", "widget"])

    def quit(self) -> None:
        self.on_quit()

    def sign_in(self) -> None:
        """The browser flow blocks for up to five minutes, so it runs off the main loop; polling resumes when it ends."""
        if self.sign_in_flow and not self.signing_in:  # a second click while the browser is open starts nothing
            self.signing_in = True
            threading.Thread(target=self.run_sign_in, daemon=True).start()

    def run_sign_in(self) -> None:
        try:
            self.sign_in_flow()
        except Exception:  # the person closed the tab or Microsoft said no: the signed-out notice stays
            return
        finally:
            self.signing_in = False
        self.on_signed_in()


def poll_unmapped(settings: dict) -> dict:
    from pace.status import Ctx, status

    return status(None, None, problem="no_mapping", ctx=Ctx(refresh_minutes=settings["refresh_minutes"]))


def open_in_browser(url: str) -> None:
    from gi.repository import Gio

    Gio.AppInfo.launch_default_for_uri(url, None)


def spawn_pace(argv: list[str]) -> None:
    """Start `pace ...`. The session's PATH may lack ~/.local/bin, where pip --user installs it."""
    exe = shutil.which(argv[0]) or str(Path.home() / ".local" / "bin" / argv[0])
    subprocess.Popen([exe, *argv[1:]], start_new_session=True, env=os.environ)
