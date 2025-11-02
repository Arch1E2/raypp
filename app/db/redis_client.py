import redis
import threading
from app.core.config import settings


class RedisClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.client = redis.Redis.from_url(
                        settings.redis_url,
                        decode_responses=True
                    )
        return cls._instance

    def get(self, key: str):
        """Get value from Redis"""
        return self.client.get(key)

    def set(self, key: str, value: str, ex: int = None):
        """Set value in Redis with optional expiration"""
        return self.client.set(key, value, ex=ex)

    def delete(self, key: str):
        """Delete key from Redis"""
        return self.client.delete(key)

    def ping(self):
        """Check Redis connection"""
        return self.client.ping()


def get_redis():
    """Get Redis client instance"""
    return RedisClient()
