"""Entra sign-in: auth code + PKCE with a loopback redirect (mocks A2-A5). Microsoft is faked; the loopback is real."""

import urllib.parse

from pace.signin import authorize_url, challenge


def test_pkce_challenge_matches_rfc_7636_appendix_b():
    assert challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_authorize_url_asks_for_the_hrms_scope_with_pkce_and_the_loopback_redirect():
    url = authorize_url(
        tenant="T", client_id="C", scope="api://H/access_as_user", redirect="http://127.0.0.1:5123/", verifier="v" * 43, state="S"
    )
    base, query = url.split("?")
    assert base == "https://login.microsoftonline.com/T/oauth2/v2.0/authorize"
    assert urllib.parse.parse_qs(query) == {
        "client_id": ["C"],
        "response_type": ["code"],
        "redirect_uri": ["http://127.0.0.1:5123/"],
        "scope": ["api://H/access_as_user"],
        "code_challenge": [challenge("v" * 43)],
        "code_challenge_method": ["S256"],
        "state": ["S"],
    }


def browser_returns(query):
    """Stands in for the browser following Microsoft's redirect to the loopback URL."""
    import threading
    import urllib.request

    def open_(url):
        def go():
            try:
                urllib.request.urlopen(url + "?" + urllib.parse.urlencode(query), timeout=5).read()
            except OSError:
                pass

        threading.Thread(target=go, daemon=True).start()

    return open_


def test_loopback_returns_the_code_when_state_matches():
    from pace.signin import Loopback

    with Loopback() as lb:
        assert lb.redirect.startswith("http://127.0.0.1:")
        browser_returns({"code": "C0DE", "state": "S"})(lb.redirect)
        assert lb.wait("S", timeout=5) == "C0DE"


def test_loopback_rejects_a_wrong_state_or_a_microsoft_error():
    import pytest

    from pace.signin import Loopback, SignInError

    with Loopback() as lb:
        browser_returns({"code": "C0DE", "state": "forged"})(lb.redirect)
        with pytest.raises(SignInError, match="state"):
            lb.wait("S", timeout=5)
    with Loopback() as lb:
        browser_returns({"error": "access_denied", "error_description": "AADSTS65004: User declined to consent"})(lb.redirect)
        with pytest.raises(SignInError, match="declined to consent"):
            lb.wait("S", timeout=5)


def test_loopback_ignores_the_browsers_favicon_request():
    import urllib.request

    from pace.signin import Loopback

    with Loopback() as lb:
        try:
            urllib.request.urlopen(lb.redirect + "favicon.ico", timeout=5)
        except OSError:
            pass
        browser_returns({"code": "C0DE", "state": "S"})(lb.redirect)
        assert lb.wait("S", timeout=5) == "C0DE"


def test_redeem_trades_the_code_and_verifier_for_the_access_token():
    from pace.signin import redeem

    sent = []

    def post_form(url, form):
        sent.append((url, form))
        return 200, {"token_type": "Bearer", "access_token": "ENTRA-JWT", "expires_in": 3599}

    token = redeem(
        tenant="T",
        client_id="C",
        scope="api://H/access_as_user",
        redirect="http://127.0.0.1:5123/",
        code="C0DE",
        verifier="V",
        post_form=post_form,
    )
    assert token == "ENTRA-JWT"
    assert sent == [
        (
            "https://login.microsoftonline.com/T/oauth2/v2.0/token",
            {
                "client_id": "C",
                "grant_type": "authorization_code",
                "code": "C0DE",
                "redirect_uri": "http://127.0.0.1:5123/",
                "code_verifier": "V",
                "scope": "api://H/access_as_user",
            },
        )
    ]


def test_sign_in_flow_runs_browser_redirect_redeem_and_hrms_exchange():
    from pace.signin import Config, sign_in_flow

    cfg = Config(base_url="https://hrms.example/api", tenant="T", client_id="C", api_client_id="H")
    seen = {}

    def microsoft(url):  # the browser + Microsoft: check the request, then redirect back with a code
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.split("?")[1]).items()}
        seen["challenge"] = q["code_challenge"]
        browser_returns({"code": "C0DE", "state": q["state"]})(q["redirect_uri"])

    def post_form(url, form):
        seen["verifier_ok"] = challenge(form["code_verifier"]) == seen["challenge"]
        return 200, {"access_token": "ENTRA-JWT"}

    class Hrms:
        def sign_in(self, token):
            seen["hrms_token"] = token

    sign_in_flow(cfg, Hrms(), open_uri=microsoft, post_form=post_form, timeout=5)
    assert seen["verifier_ok"] and seen["hrms_token"] == "ENTRA-JWT"
