"""profile.json: who is signed in, written at sign-in from hrms-api's login reply (contract section 3a)."""

from pace.files import read_json, state_dir
from pace.profile import write


def test_the_login_users_name_email_and_id_are_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    write({"first_name": "Vikas", "last_name": "Kyatannawar", "email": "vikas.k@osmosys.co", "employee_id": "E7"})
    assert read_json(state_dir() / "profile.json") == {
        "name": "Vikas Kyatannawar",
        "email": "vikas.k@osmosys.co",
        "employee_id": "E7",
        "pinestem_mapped": True,
    }


def test_a_full_name_field_wins_and_unmapped_is_carried(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    write({"name": "Vikas K", "id": 12, "pinestem_mapped": False})
    p = read_json(state_dir() / "profile.json")
    assert (p["name"], p["employee_id"], p["pinestem_mapped"]) == ("Vikas K", "12", False)


def test_a_missing_user_still_writes_a_profile_of_nulls(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    write(None)
    assert read_json(state_dir() / "profile.json") == {"name": None, "email": None, "employee_id": None, "pinestem_mapped": True}
