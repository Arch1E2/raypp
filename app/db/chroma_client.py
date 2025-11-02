import chromadb
from app.core.config import settings

_client = None


def get_chromadb():
    """Get ChromaDB client instance"""
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT
        )
    return _client

