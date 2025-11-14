from typing import List, Dict, Optional
from uuid import uuid4
import os

from src.core.config import settings

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
except Exception:
    QdrantClient = None
    rest = None

try:
    import openai
except Exception:
    openai = None


class Ingestor:
    """Ingest documents (saved files) into Qdrant with simple chunking and embeddings.

    Usage:
        ing = Ingestor(collection_name='default')
        ing.ingest_files(saved_files)

    `saved_files` is a list of dicts with keys: filename, path
    """

    def __init__(self, collection_name: str = "default", chunk_size: int = 1000, overlap: int = 200):
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.overlap = overlap

        if QdrantClient is None or rest is None:
            raise RuntimeError("qdrant-client is not installed")

        qdrant_host = settings.qdrant_url
        if settings.QDRANT_API_KEY:
            self.client = QdrantClient(url=qdrant_host, api_key=settings.QDRANT_API_KEY)
        else:
            self.client = QdrantClient(url=qdrant_host)

    def _chunk_text(self, text: str) -> List[str]:
        if not text:
            return []
        chunks = []
        start = 0
        L = len(text)
        while start < L:
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.overlap
            if start < 0:
                start = 0
            if start >= L:
                break
        return chunks

    def _embed(self, text: str) -> List[float]:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and openai is not None:
            openai.api_key = api_key
            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            resp = openai.Embedding.create(input=text, model=model)
            return resp["data"][0]["embedding"]
        # fallback dummy
        v = float(len(text)) / 100.0
        return [v] * 384

    def ingest_files(self, saved_files: List[Dict[str, str]]) -> Dict[str, int]:
        """Read files, chunk, embed and upsert into Qdrant. Returns counts.

        runs synchronously and intended to be used as a BackgroundTasks job.
        """
        if QdrantClient is None or rest is None:
            return {"status": "qdrant_client_missing"}

        total = 0
        for f in saved_files:
            path = f.get("path")
            filename = f.get("filename")
            if not path or not os.path.exists(path):
                continue
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
                text = raw.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            chunks = self._chunk_text(text)
            points = []
            for i, chunk in enumerate(chunks):
                emb = self._embed(chunk)
                pid = uuid4().hex
                payload = {"filename": filename, "chunk_index": i, "text": chunk}
                point = rest.PointStruct(id=pid, vector=emb, payload=payload)
                points.append(point)

                # batch upsert every 64 points
                if len(points) >= 64:
                    self.client.upsert(collection_name=self.collection_name, points=points)
                    total += len(points)
                    points = []

            if points:
                self.client.upsert(collection_name=self.collection_name, points=points)
                total += len(points)

        return {"status": "ok", "inserted": total}
