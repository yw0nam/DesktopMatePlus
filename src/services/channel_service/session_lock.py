import asyncio

from cachetools import TTLCache

_SESSION_TTL = 600  # 10分
_locks: TTLCache[str, asyncio.Lock] = TTLCache(maxsize=1024, ttl=_SESSION_TTL)


def session_lock(session_id: str) -> asyncio.Lock:
    """Return an asyncio.Lock for the given session_id.

    Locks are cached with a 10-minute TTL and evicted automatically
    when unused, preventing memory leaks in long-running processes.
    """
    if session_id not in _locks:
        _locks[session_id] = asyncio.Lock()
    return _locks[session_id]
