from fastapi.testclient import TestClient
from src.main import app
import json


def test_documents_endpoint_schedules_ingest(monkeypatch):
    """POST /api/documents should save uploaded files and schedule ingestion via background task.
    We monkeypatch FileSaver and Ingestor classes imported by the router to avoid disk and external calls.
    """

    saved_list = [{"filename": "a.txt", "path": "/media/a.txt"}]
    ingest_called = {"called": False, "files": None}

    class DummySaver:
        def __init__(self, request, media_root=None):
            pass

        async def save_all(self):
            return saved_list

    class DummyIngestor:
        def __init__(self, collection_name="default"):
            self.collection_name = collection_name

        def ingest_files(self, files):
            # background task will call this synchronously in TestClient
            ingest_called["called"] = True
            ingest_called["files"] = files

    # Patch the symbols used in the router module
    import src.router.base_route as base_route

    monkeypatch.setattr(base_route, "FileSaver", DummySaver)
    monkeypatch.setattr(base_route, "Ingestor", DummyIngestor)

    client = TestClient(app)

    files = {"file": ("a.txt", b"hello world", "text/plain")}
    resp = client.post("/api/documents", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["saved"] == saved_list

    # Background task should have been executed by TestClient and call the dummy ingestor
    assert ingest_called["called"] is True
    assert ingest_called["files"] == saved_list


def test_ask_endpoint_flow_with_mocks(monkeypatch):
    """POST /api/ask should run embedding -> qdrant search -> chat completion and cache the result.
    We replace Redis, QdrantClient, and openai in the router module with simple mocks.
    """

    # Dummy Redis with get/setex behavior
    cache_store = {}

    class DummyRedis:
        def get(self, k):
            return cache_store.get(k)

        def setex(self, k, ttl, v):
            cache_store[k] = v

        def delete(self, k):
            cache_store.pop(k, None)

    # Dummy Qdrant hit object
    class DummyHit:
        def __init__(self, id_, payload):
            self.id = id_
            self.payload = payload

    class DummyQdrantClient:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, collection_name, query_vector, limit, with_payload=True):
            # return two hits with payload text
            return [
                DummyHit(1, {"text": "Context about X", "filename": "a.txt"}),
                DummyHit(2, {"text": "More context about X", "filename": "b.txt"}),
            ]

    # Dummy openai module
    class DummyOpenAI:
        class Embedding:
            @staticmethod
            def create(input, model):
                return {"data": [{"embedding": [0.01] * 384}]}

        class ChatCompletion:
            @staticmethod
            def create(model, messages, temperature, max_tokens):
                return {
                    "choices": [{"message": {"content": "This is the mocked answer."}}],
                    "usage": {"total_tokens": 10},
                }

    # Dummy HistorySaver to avoid DB writes and to capture calls
    history_called = {"called": False, "args": None}

    class DummyHistorySaver:
        def __init__(self):
            pass

        def save_async(self, question, answer, tokens, sources):
            history_called["called"] = True
            history_called["args"] = (question, answer, tokens, sources)

    import src.router.base_route as base_route

    # Patch redis factory used in router; base_route.get_redis may be None or an import
    monkeypatch.setattr(base_route, "get_redis", lambda: DummyRedis())
    # Patch Qdrant and openai symbols in the router module
    monkeypatch.setattr(base_route, "QdrantClient", DummyQdrantClient)
    monkeypatch.setattr(base_route, "openai", DummyOpenAI)
    # Patch HistorySaver
    monkeypatch.setattr(base_route, "HistorySaver", DummyHistorySaver)

    client = TestClient(app)

    payload = {"question": "What is X?", "collection_name": "default", "top_k": 2, "use_cache": True}
    resp = client.post("/api/ask", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert data["answer"] == "This is the mocked answer."
    assert "sources" in data and isinstance(data["sources"], list)

    # Ensure response was cached
    # Build cache key similarly to router logic
    import hashlib
    qid = hashlib.sha256(payload["question"].encode("utf-8")).hexdigest()[:8]
    cache_key = f"{base_route.settings.CACHE_PREFIX}:{payload['collection_name']}:{qid}"
    assert cache_key in cache_store

    # History saver should have been scheduled (and executed by TestClient)
    assert history_called["called"] is True
    assert history_called["args"][0] == payload["question"]

