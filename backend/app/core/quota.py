"""Global daily quota for the public demo.

Per-IP limits stop a single visitor from monopolising the demo. This adds a
second, absolute ceiling so the shared provider key cannot be drained in a day
no matter how many distinct visitors (or proxies) arrive.
"""

from datetime import date


class DailyQuota:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._day: date | None = None
        self._used = 0

    def _roll(self) -> None:
        today = date.today()
        if self._day != today:
            self._day = today
            self._used = 0

    @property
    def used(self) -> int:
        self._roll()
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def try_consume(self, amount: int = 1) -> bool:
        """Consume quota. Returns False when the daily ceiling is reached."""
        self._roll()
        if self._used + amount > self.limit:
            return False
        self._used += amount
        return True

    def reset(self) -> None:
        self._day = date.today()
        self._used = 0
