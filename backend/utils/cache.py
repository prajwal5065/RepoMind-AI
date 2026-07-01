import time
from typing import Any, Optional

class SimpleCache:
    def __init__(self):
        # Store as {key: (value, expiry_timestamp)}
        self._store = {}
        self.default_ttl = 24 * 3600  # 24 hours

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self._store[key] = (value, expiry)

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expiry = self._store[key]
            if time.time() < expiry:
                return value
            else:
                # Expired
                del self._store[key]
        return None

    def invalidate_session(self, session_id: str):
        keys_to_delete = [k for k in self._store.keys() if k.startswith(f"{session_id}:")]
        for k in keys_to_delete:
            del self._store[k]

    def status(self, session_id: str) -> dict:
        keys = [k for k in self._store.keys() if k.startswith(f"{session_id}:")]
        return {
            "session_id": session_id,
            "cached_keys": keys,
            "count": len(keys)
        }

cache = SimpleCache()
