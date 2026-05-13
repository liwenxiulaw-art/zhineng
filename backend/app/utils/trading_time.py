from datetime import time


def is_a_share_continuous_auction_time(value) -> bool:
    """Return whether a local datetime-like value is inside regular A-share trading sessions.

    This intentionally starts with a simple weekday/time-window approximation. A real
    exchange calendar can replace this helper later without changing the quote health API.
    """

    if value.weekday() >= 5:
        return False
    current = value.time()
    morning_open = time(9, 30)
    morning_close = time(11, 30)
    afternoon_open = time(13, 0)
    afternoon_close = time(15, 0)
    return morning_open <= current <= morning_close or afternoon_open <= current <= afternoon_close
