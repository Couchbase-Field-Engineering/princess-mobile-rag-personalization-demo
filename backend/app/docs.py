"""Document ids, channel names and small shared helpers."""
from __future__ import annotations

import datetime as dt

from . import config

STATE = {"export_date": None}  # set by the loader


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> dt.date:
    """The demo's notion of 'today' - see config.DEMO_TODAY."""
    if config.DEMO_TODAY:
        return dt.date.fromisoformat(config.DEMO_TODAY)
    if STATE.get("export_date"):
        return dt.date.fromisoformat(STATE["export_date"])
    return dt.date.today()


def guest_channel(guest_id: str) -> str:
    return f"guest:{guest_id}"


CATALOG_CHANNEL = "catalog"


def profile_id(g):
    return f"profile::{g}"


def offers_id(g):
    return f"offers::{g}"


def bookings_id(g):
    return f"bookings::{g}"


def chat_id(g):
    return f"chat::{g}"


def ctx_id(g, intent):
    return f"ctx::{g}::{intent}"


def inventory_id(sailing_id):
    return f"inv::{sailing_id}"


CATALOG_ID = "catalog::v1"


def days_to_sail(profile: dict) -> int:
    embark = dt.date.fromisoformat(profile["reservation"]["embark_date"])
    return (embark - today()).days


def money(x: float) -> str:
    return f"${x:,.0f}" if float(x).is_integer() or x >= 100 else f"${x:,.2f}"
