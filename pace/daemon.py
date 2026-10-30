"""paced: the headless daemon (Gio only, no GTK). Paints the cached week at login, then polls hrms-api."""

from __future__ import annotations

from datetime import datetime

from pace.files import read_json, state_dir, write_json
from pace.poll import poll, verdict_status
from pace.status import write_status


class Daemon:
    def __init__(self, api, clock=datetime.now):
        self.api, self.clock = api, clock
        self.state_path = state_dir() / "state.json"
        self.state = read_json(self.state_path) or {}

    def boot(self) -> None:
        """First paint from the saved week, before any network call, so the panel has a number at login."""
        if self.state:
            write_status(verdict_status(self.state, self.clock()))

    def tick(self) -> None:
        s, self.state = poll(self.api, self.state, self.clock())
        write_json(self.state_path, self.state)
        write_status(s)
