from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.db.database import get_db
from app.db.redis_client import get_redis
from app.db.chroma_client import get_chromadb
from app.models.item import Item

router = APIRouter()


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Service is running"}


@router.get("/health/postgres")
def postgres_health(db: Session = Depends(get_db)):
    """Check PostgreSQL connection"""
    try:
        db.execute("SELECT 1")
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
def add_vectors(collection_name: str, documents: List[str], ids: List[str]):
    """Add documents to ChromaDB collection"""
    try:
        chroma_client = get_chromadb()
        collection = chroma_client.get_or_create_collection(collection_name)
        collection.add(documents=documents, ids=ids)
        return {"status": "ok", "collection": collection_name, "added": len(ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ChromaDB error: {str(e)}")


@router.post("/vectors/query")
def query_vectors(collection_name: str, query_texts: List[str], n_results: int = 5):
    """Query documents from ChromaDB collection"""
    try:
        chroma_client = get_chromadb()
        collection = chroma_client.get_or_create_collection(collection_name)
        results = collection.query(query_texts=query_texts, n_results=n_results)
        return {"status": "ok", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ChromaDB error: {str(e)}")
