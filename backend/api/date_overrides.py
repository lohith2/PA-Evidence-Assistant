from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone


_DECEMBER_2025_START = datetime(2025, 12, 1, 9, 0, tzinfo=timezone.utc)


def display_created_at(session_id: str) -> datetime:
    """
    Map a session id to a stable pseudo-random datetime in December 2025.

    This keeps all case content unchanged while making display dates look like
    they occurred throughout the month.
    """
    digest = hashlib.sha256((session_id or "").encode()).digest()
    day_offset = digest[0] % 31
    minute_offset = int.from_bytes(digest[1:3], "big") % (12 * 60)
    return _DECEMBER_2025_START + timedelta(days=day_offset, minutes=minute_offset)
