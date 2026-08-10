"""Deduplication: we use place_id as unique in DB. Helpers for suppression sync."""
from .db import add_to_suppression, get_conn


def add_replied_stop_to_suppression(email: str) -> None:
    """Call when user replies 'stop' (handled externally or by you)."""
    add_to_suppression(email, reason="replied_stop")


def ensure_place_id_unique(conn=None) -> None:
    """Leads table already uses place_id UNIQUE. No-op unless you add more dedupe logic."""
    pass
