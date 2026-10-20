"""Seat-position inference from a seat number (spec #13).

Chinese high-speed trains use a stable letter layout: second class is 3+2
(A B C | D F), first class is 2+2 (A C | D F), business class is 2+1, so the
letter alone tells the physical position:

    A / F → window     C / D → aisle     B → middle

Sleeper berths (上铺/中铺/下铺) are reported as ``sleeper``. The existing
``seat_type`` field already stores this vocabulary (see the train form), so no
schema change is needed; callers only fill it when the user did not.
"""

from __future__ import annotations

import re

_SEAT_LETTER = re.compile(r"(\d+)\s*([A-Fa-f])")

_WINDOW = {"A", "F"}
_AISLE = {"C", "D"}
_MIDDLE = {"B"}

_SLEEPER_MARKERS = ("上铺", "中铺", "下铺", "卧铺")


def infer_train_seat_type(seat: str | None) -> str | None:
    """Return window/aisle/middle/sleeper/standing for a train seat, or None."""
    if not seat:
        return None
    text = str(seat).strip()
    if not text:
        return None
    if "无座" in text or text.upper() in {"STANDING", "NO SEAT"}:
        return "standing"
    if any(marker in text for marker in _SLEEPER_MARKERS):
        return "sleeper"

    match = _SEAT_LETTER.search(text)
    if match is None:
        return None
    letter = match.group(2).upper()
    if letter in _WINDOW:
        return "window"
    if letter in _AISLE:
        return "aisle"
    if letter in _MIDDLE:
        return "middle"
    return None
