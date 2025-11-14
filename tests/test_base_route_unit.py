import asyncio
import json
import hashlib

import pytest
from fastapi import BackgroundTasks

import src.router.base_route as base_route
from src.router.base_route import AskRequest, build_prompt


def test_build_prompt_simple():
    ctx = ["Alpha info", "Beta info"]
    p = build_prompt("What is alpha?", ctx)
    assert "Source 1:" in p
    assert "Source 2:" in p
    assert "Question: What is alpha?" in p


def test_ask_cache_hit(monkeypatch):
    """When Redis has a cached value, ask() should return it without calling Qdrant/OpenAI."""

    # Prepare cached response
    question = "cached?"
    qid = hashlib.sha256(question.encode("utf-8")).hexdigest()[:8]
    cache_key = f"{base_route.settings.CACHE_PREFIX}:default:{qid}"
    cached_value = {"answer": "from cache", "sources": ["s1"], "tokens": 1, "time_ms": 0}

    class DummyRedis:
        def get(self, k):
            assert k == cache_key
            return json.dumps(cached_value).encode()

        def setex(self, k, ttl, v):
            raise AssertionError("setex should not be called on cache hit")

    # Ensure Qdrant/OpenAI would error if called
    monkeypatch.setattr(base_route, "QdrantClient", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Qdrant should not be called")))
    monkeypatch.setattr(base_route, "openai", None)

    monkeypatch.setattr(base_route, "get_redis", lambda: DummyRedis())

    req = AskRequest(question=question, collection_name="default", top_k=1, use_cache=True)
    bg = BackgroundTasks()

    # Call async function directly
    resp = asyncio.run(base_route.ask(req, bg))
    assert resp == cached_value


def test_ask_full_flow_schedules_history_and_caches(monkeypatch):
    """Full ask flow: embedding->qdrant->openai should return answer, set cache and schedule history save."""

    question = "What is X?"

    # Dummy Redis to capture setex
    cache_store = {}

    class DummyRedis:
        def get(self, k):
            return None

        def setex(self, k, ttl, v):
            cache_store[k] = v

        def delete(self, k):
            cache_store.pop(k, None)

    monkeypatch.setattr(base_route, "get_redis", lambda: DummyRedis())

    # Dummy Qdrant hit object
    class DummyHit:
        def __init__(self, id_, payload):
            self.id = id_
            self.payload = payload

    class DummyQdrantClient:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, collection_name, query_vector, limit, with_payload=True):
            return [
                DummyHit(1, {"text": "ctx1", "filename": "a.txt"}),
            ]

    monkeypatch.setattr(base_route, "QdrantClient", DummyQdrantClient)

    class DummyOpenAI:
        class Embedding:
            @staticmethod
            def create(input, model):
                return {"data": [{"embedding": [0.1] * 384}]}

        class ChatCompletion:
            @staticmethod
            def create(model, messages, temperature, max_tokens):
                return {
                    "choices": [{"message": {"content": "Mock answer."}}],
                    "usage": {"total_tokens": 42},
                }

    monkeypatch.setattr(base_route, "openai", DummyOpenAI)

    # Replace HistorySaver with dummy that records schedule
    history_scheduled = {"scheduled": False}

    class DummyHistorySaver:
        def __init__(self):
            pass

        async def save_async(self, question, answer, tokens, sources):
            history_scheduled["scheduled"] = True

    monkeypatch.setattr(base_route, "HistorySaver", DummyHistorySaver)

    req = AskRequest(question=question, collection_name="default", top_k=1, use_cache=True)
    bg = BackgroundTasks()

    resp = asyncio.run(base_route.ask(req, bg))

    assert resp["answer"] == "Mock answer."
    assert isinstance(resp.get("sources"), list)

    # Check cache entry exists
    qid = hashlib.sha256(question.encode("utf-8")).hexdigest()[:8]
    cache_key = f"{base_route.settings.CACHE_PREFIX}:default:{qid}"
    assert cache_key in cache_store

    # BackgroundTasks should have scheduled one task
    assert len(bg.tasks) >= 1


def test_documents_schedules_ingest(monkeypatch):
    """documents() should return saved list and schedule ingestion in background tasks."""

    saved_list = [{"filename": "a.txt", "path": "/media/a.txt"}]

    class DummySaver:
        def __init__(self, request, media_root=None):
            DummySaver.created = True

        async def save_all(self):
            return saved_list

    class DummyIngestor:
        def __init__(self, collection_name="default"):
            DummyIngestor.instantiated = True

        def ingest_files(self, files):
            # will be scheduled in background tasks
            DummyIngestor.files = files

    monkeypatch.setattr(base_route, "FileSaver", DummySaver)
    monkeypatch.setattr(base_route, "Ingestor", DummyIngestor)

    bg = BackgroundTasks()
    # request is not used by DummySaver, can pass None
    resp = asyncio.run(base_route.documents(None, bg))

    assert resp["status"] == "ok"
    assert resp["saved"] == saved_list
    # Background task scheduled
    assert len(bg.tasks) >= 1
