"""profile.json (contract section 3a): who is signed in. Written at sign-in; the app and the daemon read it."""

from __future__ import annotations

from pace.files import read_json, state_dir, write_json


def write(user: dict | None) -> None:
    """From the `user` object of hrms-api's login reply. Field names are not fixed yet, so every one is optional."""
    user = user or {}
    name = user.get("name") or " ".join(p for p in (user.get("first_name"), user.get("last_name")) if p) or None
    ident = user.get("employee_id") or user.get("id")
    write_json(
        state_dir() / "profile.json",
        {
            "name": name,
            "email": user.get("email"),
            "employee_id": str(ident) if ident is not None else None,
            "pinestem_mapped": user.get("pinestem_mapped") is not False,
        },
    )


def pinestem_mapped() -> bool:
    return (read_json(state_dir() / "profile.json") or {}).get("pinestem_mapped") is not False
