import time
from collections import defaultdict, deque

from fastapi import Header

from app.config import settings
from app.errors import RateLimitError

_hits: dict[str, deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def rate_limit(x_api_token: str = Header(default="")) -> None:
    now = time.monotonic()
    window = _hits[x_api_token]
    while window and now - window[0] >= 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        raise RateLimitError("Trop de requêtes, réessaie dans une minute.")
    window.append(now)