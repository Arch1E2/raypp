import redis
from typing import Optional
from src.core.config import settings


class RedisClient:
    def __init__(self):
        url = None
        if settings.REDIS_PASSWORD:
            url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}"
        else:
            url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def set(self, key: str, value: str, ex: int = None):
        return self.client.set(key, value, ex=ex)

    def delete(self, key: str):
        return self.client.delete(key)

    def ping(self):
        return self.client.ping()


_redis_client: RedisClient | None = None

def get_redis() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
