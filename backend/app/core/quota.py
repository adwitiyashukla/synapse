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
        self._roll()
        if self._used + amount > self.limit:
            return False
        self._used += amount
        return True

    def reset(self) -> None:
        self._day = date.today()
        self._used = 0
