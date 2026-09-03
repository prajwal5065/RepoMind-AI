"""
Shared in-memory, per-IP sliding-window rate limiter.

Previously this class was defined inline in api/chat.py. It's extracted
here so /api/upload and /api/clone-repo — the two heaviest, most
resource-intensive endpoints — can be rate-limited the same way
/api/chat already was.

Caveat: this is a single-process, in-memory limiter. It resets on
restart and does not coordinate across multiple uvicorn workers or
replicas. If the app is scaled horizontally, replace this with a
shared store (e.g. Redis) keyed the same way.
"""
import time
from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self.clients: dict = {}

    def __call__(self, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        self.clients.setdefault(client_ip, [])
        # Evict old timestamps
        self.clients[client_ip] = [t for t in self.clients[client_ip] if now - t < self.window]
        if len(self.clients[client_ip]) >= self.requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
        self.clients[client_ip].append(now)
