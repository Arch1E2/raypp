from typing import Any, List, Dict, Callable, Optional
from uuid import uuid4
import asyncio

from src.core.config import settings

# Default embedding dimension for the dummy embedder
EMBEDDING_DIMENSION = 384

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
except Exception:
    QdrantClient = None
    rest = None


class QdrantIngestor:
    """Ingest uploaded files from a FastAPI Request into a Qdrant collection.

    Usage:
        ingestor = QdrantIngestor(request, collection_name='mycol', embedder=my_embed_fn)
        result = await ingestor.ingest_all()

    The embedder callable should accept a string and return a list[float]. If not
    provided, a simple length-based dummy embedding will be used (for demo only).
    """

    def __init__(
        self,
        request: Any,
        collection_name: str = "default",
        embedder: Optional[Callable[[str], List[float]]] = None,
    ) -> None:
        self.request = request
        self.collection_name = collection_name
        self.embedder = embedder or self._dummy_embed

        if QdrantClient is None:
            raise RuntimeError(
                "qdrant-client is not installed. Install with `pip install qdrant-client` to use QdrantIngestor.`"
            )

        # Create client using settings
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    async def ingest_all(self) -> List[Dict[str, Any]]:
        """Read form from request, save each UploadFile-like entry into Qdrant as a point.

        Returns a list of metadata for inserted points: {id, filename, size}
        """
        form = await self.request.form()
        saved = []

        for field, value in form.items():
            # Detect UploadFile-like objects
            if not (hasattr(value, "filename") and hasattr(value, "read")):
                continue

            filename = getattr(value, "filename", "uploaded_file")
            raw = await value.read()
            try:
                text = raw.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            # Compute embedding (sync); run in thread if embedder might be CPU-bound
            embedding = await asyncio.to_thread(self.embedder, text)

            # Ensure collection exists (create if not)
            await asyncio.to_thread(self._ensure_collection, len(embedding))

            point_id = uuid4().hex
            point = rest.PointStruct(id=point_id, vector=embedding, payload={
                "filename": filename,
                "field": field,
                "text": text,
            })

            # Upsert point into Qdrant
            await asyncio.to_thread(self.client.upsert, collection_name=self.collection_name, points=[point])

            saved.append({"id": point_id, "filename": filename, "size": len(raw)})

        return saved

    def _ensure_collection(self, vector_size: int) -> None:
        """Create collection if it does not exist (idempotent)."""
        try:
            # If collection exists, get_collection will succeed; if not, create it
            existing = self.client.get_collection(self.collection_name)
            return
        except Exception:
            # Create collection with cosine distance by default
            params = rest.VectorParams(size=vector_size, distance=rest.Distance.COSINE)
            self.client.recreate_collection(collection_name=self.collection_name, vectors_config=params)

    def _dummy_embed(self, text: str) -> List[float]:
        """Simple deterministic dummy embedding for testing (DO NOT use in production)."""
        value = float(len(text)) / 100.0
        return [value] * EMBEDDING_DIMENSION
