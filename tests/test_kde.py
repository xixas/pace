"""KDE Plasma support: the panel applet replaces the tray, the GTK mini widget is pinned by a KWin rule, and a locked
KWallet no longer blocks paced (docs/architecture.md, "Frontends")."""

import threading
import time

import pytest

from pace import kwin, plasma
from pace.cli import tray_wanted
from pace.client import Offline, WalletLocked
from pace.tokens import BackgroundStore

APPLETSRC = """[Containments][2][Applets][24]
immutability=1
plugin=org.kde.plasma.kickoff

[Containments][2][Applets][47]
immutability=1
plugin={plugin}
"""


# ---- the applet replaces the tray ---------------------------------------------------------------------------------


def test_applet_on_a_panel_is_found_in_plasma_config(tmp_path):
    rc = tmp_path / "plasma-org.kde.plasma.desktop-appletsrc"
    assert plasma.applet_on_panel(rc) is False  # no file yet
    rc.write_text(APPLETSRC.format(plugin="org.kde.plasma.digitalclock"))
    assert plasma.applet_on_panel(rc) is False
    rc.write_text(APPLETSRC.format(plugin="io.github.xixas.Pace"))
    assert plasma.applet_on_panel(rc) is True


@pytest.mark.parametrize(
    "desktop, watcher, applet, wanted",
    [
        ("KDE", True, False, True),  # KDE without the applet keeps the tray ring
        ("KDE", True, True, False),  # the applet draws the panel instead
        ("GNOME", True, False, False),
        ("XFCE", True, True, True),  # only Plasma reads the applet config
    ],
)
def test_the_tray_steps_aside_for_the_plasma_applet(desktop, watcher, applet, wanted):
    assert tray_wanted(desktop, watcher, applet_on_panel=applet) is wanted


# ---- the KWin rule for the GTK mini widget --------------------------------------------------------------------------


class FakeKConfig:
    """kreadconfig6 / kwriteconfig6 over a dict, plus a log of the KWin reconfigure call."""

    def __init__(self, order=""):
        self.values = {("General", "Order"): order}
        self.calls = []

    def run(self, argv, **_):
        self.calls.append(argv)
        args = dict(zip(argv[1::2], argv[2::2], strict=False))
        out = ""
        if argv[0] == "kreadconfig6":
            out = self.values.get((args["--group"], args["--key"]), "")
        elif argv[0] == "kwriteconfig6":
            self.values[(args["--group"], args["--key"])] = argv[-1]
        return type("R", (), {"returncode": 0, "stdout": out + "\n"})()


def which(found):
    return lambda name: f"/usr/bin/{name}" if found else None


def test_kwin_rule_pins_the_widget_on_kde(monkeypatch):
    k = FakeKConfig(order="723e10ac,auto-liker-bot")
    assert kwin.ensure_widget_rule("KDE", run=k.run, which=which(True)) is True
    g = kwin.RULE_GROUP
    v = k.values
    assert v[("General", "Order")] == f"723e10ac,auto-liker-bot,{g}"  # existing rules untouched, ours appended
    assert v[(g, "wmclass")] == kwin.APP_ID and v[(g, "title")] == kwin.WIDGET_TITLE
    assert v[(g, "above")] == "true" and v[(g, "aboverule")] == "2"
    assert v[(g, "skiptaskbar")] == "true" and v[(g, "skippager")] == "true"
    assert v[(g, "positionrule")] == "4"  # remember where it was dragged
    assert any("reconfigure" in " ".join(c) for c in k.calls)


def test_kwin_rule_is_written_once(monkeypatch):
    k = FakeKConfig(order="")
    kwin.ensure_widget_rule("KDE", run=k.run, which=which(True))
    writes = len([c for c in k.calls if c[0] == "kwriteconfig6"])
    kwin.ensure_widget_rule("KDE", run=k.run, which=which(True))
    assert len([c for c in k.calls if c[0] == "kwriteconfig6"]) == writes
    assert k.values[("General", "Order")] == kwin.RULE_GROUP


@pytest.mark.parametrize("desktop, tools", [("GNOME", True), ("KDE", False), ("XFCE", True)])
def test_kwin_rule_only_on_kde_with_its_tools(desktop, tools):
    k = FakeKConfig()
    assert kwin.ensure_widget_rule(desktop, run=k.run, which=which(tools)) is False
    assert k.calls == []


# ---- a locked wallet no longer blocks paced -----------------------------------------------------------------------


class SlowStore:
    def __init__(self, delay):
        self.delay, self.saved = delay, None

    def load(self):
        time.sleep(self.delay)
        return {"access": "A", "refresh": "R"}

    def save(self, tokens):
        self.saved = tokens

    def clear(self):
        self.saved = None


def test_a_locked_wallet_raises_wallet_locked_instead_of_blocking():
    gate = threading.Event()
    store = BackgroundStore(lambda: SlowStore(0) if gate.wait(5) else None, wait=0.05)
    started = time.monotonic()
    with pytest.raises(WalletLocked):
        store.load()
    assert time.monotonic() - started < 1  # paced's main loop got control back
    gate.set()  # the person unlocked the wallet
    for _ in range(100):
        try:
            assert store.load() == {"access": "A", "refresh": "R"}
            break
        except WalletLocked:
            time.sleep(0.02)
    else:
        pytest.fail("the store never became ready")


def test_wallet_locked_is_handled_like_offline():
    assert issubclass(WalletLocked, Offline)


def test_background_store_passes_saves_through_once_ready():
    inner = SlowStore(0)
    store = BackgroundStore(lambda: inner, wait=1)
    assert store.load()["access"] == "A"
    store.save({"access": "B", "refresh": "S"})
    assert inner.saved == {"access": "B", "refresh": "S"}


def test_poll_says_waiting_for_the_wallet():
    from datetime import datetime

    from pace.poll import poll

    class Api:
        def my_days(self, *_):
            raise WalletLocked("wallet locked")

    s, _ = poll(Api(), {}, datetime(2026, 11, 23, 9, 0))
    assert s["problem"]["kind"] == "offline"
    assert s["problem"]["message"] == "Waiting for the wallet"


# ---- onboarding: Add to panel ------------------------------------------------------------------------------------


def test_add_to_panel_asks_plasmashell_to_add_the_applet_once():
    calls = []
    ok = plasma.add_to_panel(run=lambda argv, **_: calls.append(argv) or type("R", (), {"returncode": 0})())
    assert ok and calls[0][:3] == ["gdbus", "call", "--session"]
    assert "org.kde.PlasmaShell.evaluateScript" in calls[0]
    script = calls[0][-1]
    assert 'addWidget("io.github.xixas.Pace")' in script and "if (!have" in script  # never a second copy


def test_onboarding_offers_the_panel_on_plasma():
    from pace.ui import onboarding

    assert onboarding.topbar_kind("KDE") == "plasma"
    assert onboarding.topbar_kind("XFCE") == "tray"
