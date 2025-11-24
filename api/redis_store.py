import json
import os
from typing import Dict, Any, List, Optional


class RedisStore:
    def __init__(self, url: str):
        import redis  # type: ignore

        self.client = redis.Redis.from_url(url)
        self.key = os.getenv("JOB_STORE_KEY", "job_store")

    def load(self) -> List[Dict[str, Any]]:
        try:
            raw = self.client.get(self.key)
            if not raw:
                return []
            return json.loads(raw)
        except Exception:
            return []

    def save(self, data: List[Dict[str, Any]]):
        try:
            self.client.set(self.key, json.dumps(data))
        except Exception:
            # Ignore write errors to avoid breaking runtime
            pass
