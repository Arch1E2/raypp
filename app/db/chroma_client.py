import chromadb
from app.core.config import settings


class ChromaDBClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT
            )
        return cls._instance

    def get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection"""
        return self.client.get_or_create_collection(name=name)

    def heartbeat(self):
        """Check ChromaDB connection"""
        return self.client.heartbeat()


def get_chromadb():
    """Get ChromaDB client instance"""
    return ChromaDBClient()
