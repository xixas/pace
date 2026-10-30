"""hrms-api client: the Entra → HRMS token exchange, refresh, and the two Pace endpoints. No GTK."""

from __future__ import annotations


class Offline(Exception):
    """hrms-api or the network is unreachable: keep the last good numbers."""


class SignedOut(Exception):
    """The HRMS session is gone and can't be refreshed: the person signs in again."""
