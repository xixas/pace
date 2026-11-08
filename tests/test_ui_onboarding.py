import urllib.parse

import pytest

from pace.client import Offline, SignedOut
from pace.signin import SignInError
from pace.ui import onboarding


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (SignInError("AADSTS65004: The user declined to consent to access the app."), "cancelled"),
        (SignInError("access_denied"), "cancelled"),
        (SignInError("Pace sign-in cancelled"), "cancelled"),
        (SignInError("AADSTS90094: The grant requires admin permission."), "admin"),
        (SignInError("AADSTS65001: The user or administrator has not consented"), "admin"),
        (SignInError("AADSTS700016 ... consent_required"), "admin"),
        (SignInError("no answer from the browser"), "timeout"),
        (SignedOut("token tenant mismatch: not an osmosys account"), "personal"),
        (SignedOut("Invalid tenant"), "personal"),
        (Offline("[Errno -2] Name or service not known"), "offline"),
        (OSError("Network is unreachable"), "offline"),
        (SignInError("something else entirely"), "other"),
    ],
)
def test_classify_failure(exc, kind):
    assert onboarding.classify_failure(exc) == kind


def test_failure_copy_matches_mock_a7():
    f = onboarding.FAILURES
    assert f["cancelled"]["title"] == "You cancelled"
    assert f["cancelled"]["button"] == "Try again"
    assert f["admin"]["title"] == "Your organisation must approve Pace first"
    assert f["admin"]["extra"] == "Copy message for IT"
    assert f["personal"]["body"].startswith("That was a personal Microsoft account.")
    assert f["timeout"]["title"] == "The browser never came back"
    assert f["offline"]["button"] == "Retry"
    assert onboarding.FAILURES["other"]["title"]


def test_it_request_names_app_and_permissions():
    text = onboarding.it_request()
    for needle in ("Pace", "Sign you in", "Read your profile", "Access DhiHRMS as you"):
        assert needle in text


def test_listening_port_from_authorize_url():
    q = urllib.parse.urlencode({"redirect_uri": "http://127.0.0.1:53682/", "client_id": "x"})
    assert onboarding.listening_port(f"https://login.microsoftonline.com/t/oauth2/v2.0/authorize?{q}") == 53682
    assert onboarding.listening_port("https://example.com/") is None


def test_cancel_url_unblocks_the_loopback():
    url = onboarding.cancel_url("http://127.0.0.1:53682/")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert url.startswith("http://127.0.0.1:53682/?") and q["error"] == "access_denied"


def test_desktop_step_by_xdg_current_desktop():
    assert onboarding.topbar_kind("GNOME") == "gnome"
    assert onboarding.topbar_kind("ubuntu:GNOME") == "gnome"
    assert onboarding.topbar_kind("KDE") == "tray"
    assert onboarding.topbar_kind("COSMIC") == "tray"
    assert onboarding.topbar_kind("X-Cinnamon") == "tray"
    assert onboarding.topbar_kind("") == "tray"


def test_summary_rows_from_profile_and_history():
    profile = {"name": "Vikas Kyatannawar", "email": "vikas.k@osmosys.co", "employee_id": "E1", "pinestem_mapped": True}
    s = onboarding.summary(profile, holidays=14, leave_days=1.0)
    assert s["headline"] == "Signed in as Vikas Kyatannawar"
    assert s["email"] == "vikas.k@osmosys.co"
    assert s["rows"] == [
        ("DhiHRMS employee linked", ""),
        ("PineStem account", "linked"),
        ("Holidays 2026", "14"),
        ("Leave this month", "1 day"),
    ]
    s = onboarding.summary({**profile, "pinestem_mapped": False}, holidays=None, leave_days=0.5)
    assert ("PineStem account", "not linked") in s["rows"]
    assert ("Holidays 2026", "–") in s["rows"] and ("Leave this month", "0.5 day") in s["rows"]
    assert onboarding.summary(None, None, None)["headline"] == "Signed in"


def test_no_leave_reads_none_not_zero_day():
    assert ("Leave this month", "none") in onboarding.summary({}, 3, 0)["rows"]
    assert ("Leave this month", "2 days") in onboarding.summary({}, 3, 2.0)["rows"]
