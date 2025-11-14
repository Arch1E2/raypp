import json
import hashlib
import pytest
from fastapi.testclient import TestClient
from src.main import app

# Use TestClient for synchronous testing of FastAPI app
client = TestClient(app)


def test_cache_hit_and_miss(monkeypatch):
    # Prepare a dummy redis client
    class DummyRedis:
        def __init__(self):
            self.store = {}
        def get(self, k):
            return self.store.get(k)
        def setex(self, k, ex, v):
            self.store[k] = v
        def delete(self, k):
            if k in self.store:
                del self.store[k]

    dummy = DummyRedis()

    # Monkeypatch get_redis to return dummy
    from src.database import redis_client

    # base_route was imported at module import time via src.main, so patch it directly too
    import src.router.base_route as br
    monkeypatch.setattr(redis_client, "get_redis", lambda: dummy)
    monkeypatch.setattr(br, "get_redis", lambda: dummy, raising=False)

    q = "What is the meaning of life?"
    payload = {"question": q, "collection_name": "default", "top_k": 0, "use_cache": True}

    # Provide dummy QdrantClient and openai with ChatCompletion
    class DummyQdrant:
        def search(self, *args, **kwargs):
            return []

    monkeypatch.setattr(br, "QdrantClient", lambda *args, **kwargs: DummyQdrant())

    class DummyOpenAI:
        class ChatCompletion:
            @staticmethod
            def create(*args, **kwargs):
                return {"choices": [{"message": {"content": "42"}}], "usage": {"total_tokens": 10}}

        class Embedding:
            @staticmethod
            def create(*args, **kwargs):
                return {"data": [{"embedding": [0.1] * 384}]}

    monkeypatch.setattr(br, "openai", DummyOpenAI())

    # First request should produce and cache response
    r1 = client.post("/api/ask", json=payload)
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["answer"] == "42"

    # Compute expected cache key
    expected_key = f"{br.settings.CACHE_PREFIX}:default:{hashlib.sha256(q.encode('utf-8')).hexdigest()[:8]}"
    assert expected_key in dummy.store

    # Second request should hit cache — to test, replace openai with a failing one to ensure cache returned
    class FailingOpenAI:
        class ChatCompletion:
            @staticmethod
            def create(*args, **kwargs):
                raise RuntimeError("should not be called")
        class Embedding:
            @staticmethod
            def create(*args, **kwargs):
                return {"data": [{"embedding": [0.1] * 384}]}

    monkeypatch.setattr(br, "openai", FailingOpenAI())

    r2 = client.post("/api/ask", json=payload)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["answer"] == "42"
