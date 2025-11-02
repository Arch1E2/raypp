from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.db.database import get_db
from app.db.redis_client import get_redis
from app.db.chroma_client import get_chromadb
from app.models.item import Item

router = APIRouter()


# Constants
EMBEDDING_DIMENSION = 384  # Standard dimension for sentence embeddings


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True


class VectorAddRequest(BaseModel):
    collection_name: str
    documents: List[str]
    ids: List[str]
    embeddings: Optional[List[List[float]]] = None
    
    def model_post_init(self, __context):
        """Validate that documents and ids have the same length"""
        if len(self.documents) != len(self.ids):
            raise ValueError(f"documents and ids must have the same length. Got {len(self.documents)} documents and {len(self.ids)} ids.")


class VectorQueryRequest(BaseModel):
    collection_name: str
    query_texts: Optional[List[str]] = None
    query_embeddings: Optional[List[List[float]]] = None
    n_results: int = 5


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Service is running"}


@router.get("/health/postgres")
def postgres_health(db: Session = Depends(get_db)):
    """Check PostgreSQL connection"""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "postgres"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PostgreSQL error: {str(e)}")


@router.get("/health/redis")
def redis_health():
    """Check Redis connection"""
    try:
        redis_client = get_redis()
        redis_client.ping()
        return {"status": "ok", "service": "redis"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis error: {str(e)}")


@router.get("/health/chromadb")
def chromadb_health():
    """Check ChromaDB connection"""
    try:
        chroma_client = get_chromadb()
        chroma_client.heartbeat()
        return {"status": "ok", "service": "chromadb"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ChromaDB error: {str(e)}")


@router.post("/items", response_model=ItemResponse)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    """Create a new item in PostgreSQL"""
    db_item = Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/items", response_model=List[ItemResponse])
def get_items(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """Get all items from PostgreSQL"""
    items = db.query(Item).offset(skip).limit(limit).all()
    return items


@router.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    """Get item by ID from PostgreSQL"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/cache/{key}")
def set_cache(key: str, value: str, ttl: Optional[int] = None):
    """Set a value in Redis cache"""
    redis_client = get_redis()
    redis_client.set(key, value, ex=ttl)
    return {"key": key, "value": value, "ttl": ttl}


@router.get("/cache/{key}")
def get_cache(key: str):
    """Get a value from Redis cache"""
    redis_client = get_redis()
    value = redis_client.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Key not found in cache")
    return {"key": key, "value": value}


@router.post("/vectors/add")
def add_vectors(request: VectorAddRequest):
    """Add documents to ChromaDB collection
    
    If embeddings are not provided, simple embeddings will be generated based on document length.
    For production use, provide your own embeddings from a proper embedding model.
    """
    try:
        import chromadb.utils.embedding_functions as embedding_functions
        
        chroma_client = get_chromadb()
        
        # Use a simple embedding function that doesn't require internet
        # For production, you should use proper embeddings
        ef = embedding_functions.DefaultEmbeddingFunction()
        
        collection = chroma_client.get_or_create_collection(
            name=request.collection_name,
            embedding_function=ef,
            metadata={"description": "Collection created via API"}
        )
        
        # Determine embeddings to use
        if request.embeddings:
            embeddings_to_add = request.embeddings
        else:
            # Generate simple dummy embeddings based on text length
            # This is just for demonstration - use proper embeddings in production
            embeddings_to_add = [[float(len(doc)) / 100.0] * EMBEDDING_DIMENSION for doc in request.documents]
        
        # Add documents with embeddings
        collection.add(
            documents=request.documents,
            embeddings=embeddings_to_add,
            ids=request.ids
        )
        
        return {
            "status": "ok",
            "collection": request.collection_name,
            "added": len(request.ids),
            "note": "Using simple embeddings. For production, provide your own embeddings." if not request.embeddings else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ChromaDB error: {str(e)}")


@router.post("/vectors/query")
def query_vectors(request: VectorQueryRequest):
    """Query documents from ChromaDB collection
    
    Provide either query_texts or query_embeddings.
    """
    try:
        import chromadb.utils.embedding_functions as embedding_functions
        
        chroma_client = get_chromadb()
        ef = embedding_functions.DefaultEmbeddingFunction()
        
        collection = chroma_client.get_or_create_collection(
            name=request.collection_name,
            embedding_function=ef
        )
        
        if request.query_embeddings:
            results = collection.query(
                query_embeddings=request.query_embeddings,
                n_results=request.n_results
            )
        elif request.query_texts:
            # Generate simple embeddings for query texts
            query_embeddings = [[float(len(text)) / 100.0] * EMBEDDING_DIMENSION for text in request.query_texts]
            results = collection.query(
                query_embeddings=query_embeddings,
                n_results=request.n_results
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either query_texts or query_embeddings"
            )
        
        return {"status": "ok", "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ChromaDB error: {str(e)}")
