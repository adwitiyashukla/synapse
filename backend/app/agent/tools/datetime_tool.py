"""Current date and time tool with timezone support."""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


async def run(tz: str = "UTC") -> str:
    try:
        zone = ZoneInfo(tz) if tz else timezone.utc
    except ZoneInfoNotFoundError:
        return json.dumps({"error": f"Unknown timezone: {tz}. Use IANA names like Asia/Kolkata."})
    now = datetime.now(zone)
    return json.dumps(
        {
            "timezone": str(zone),
            "iso": now.isoformat(),
            "date": now.strftime("%A, %B %d, %Y"),
            "time": now.strftime("%H:%M:%S"),
        }
    )
