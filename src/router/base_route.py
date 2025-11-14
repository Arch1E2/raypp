from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os
import time
import logging
import hashlib
import json

from src.core.config import settings
from src.helpers.file_saver import FileSaver
from src.services.history import HistorySaver
from src.services.ingest import Ingestor

# Try to import redis getter helper; fallback if missing
try:
    from src.database.redis_client import get_redis
except Exception:
    get_redis = None

# Configure logger for the module
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("raypp.base_route")

# Qdrant and OpenAI clients
try:
    from qdrant_client import QdrantClient
except Exception:
    QdrantClient = None

try:
    import openai
except Exception:
    openai = None

router = APIRouter(prefix="/api")


@router.post("/documents")
async def documents(request: Request, background_tasks: BackgroundTasks):
    """Accept uploaded files from form-data, save them and schedule ingestion into Qdrant."""
    logger.info("Received document upload request")
    try:
        saver = FileSaver(request, media_root=settings.MEDIA_ROOT)
        saved = await saver.save_all()
        logger.info("Saved %d files", len(saved))

        # Schedule ingestion to Qdrant in the background
        try:
            ingestor = Ingestor(collection_name="default")
            background_tasks.add_task(ingestor.ingest_files, saved)
            logger.info("Scheduled ingestion for %d files into collection %s", len(saved), "default")
        except Exception as ex:
            logger.exception("Failed to schedule ingestion: %s", str(ex))
            # If ingest can't be scheduled, still return saved files
            pass

        return {"status": "ok", "saved": saved}
    except Exception as e:
        logger.exception("Failed to save uploaded files: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save files: {str(e)}")


class AskRequest(BaseModel):
    question: str
    collection_name: str = "default"
    top_k: int = 5
    use_cache: bool = True


# Move build_prompt to module level to allow unit testing
def build_prompt(question: str, contexts: List[str]) -> str:
    prompt = "You are a helpful assistant. Use only the following sources to answer the question. If the answer is not found, say you don't know.\n\n"
    for i, c in enumerate(contexts):
        prompt += f"Source {i+1}:\n{c}\n\n"
    prompt += f"Question: {question}\nAnswer:"
    return prompt


@router.post("/ask")
async def ask(req: AskRequest, background_tasks: BackgroundTasks):
    """Handle a question: retrieve from Qdrant and call OpenAI to generate answer."""
    qid = hashlib.sha256(req.question.encode("utf-8")).hexdigest()[:8]
    logger.info("Ask request id=%s collection=%s top_k=%d", qid, req.collection_name, req.top_k)
    start = time.time()

    # Attempt to get Redis client for caching; non-fatal if unavailable
    redis_client = None
    if get_redis is not None:
        try:
            redis_client = get_redis()
        except Exception as e:
            logger.warning("Unable to get Redis client: %s", str(e))
            redis_client = None

    # Prepare cache key (based on question hash + collection)
    cache_key = f"{settings.CACHE_PREFIX}:{req.collection_name}:{qid}"

    # If caching enabled, try to return cached response early
    if req.use_cache and redis_client is not None:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info("Cache hit for id=%s key=%s", qid, cache_key)
                try:
                    resp_obj = json.loads(cached.decode() if isinstance(cached, (bytes, bytearray)) else cached)
                except Exception:
                    # If cached value is corrupted, delete it and continue
                    try:
                        redis_client.delete(cache_key)
                    except Exception:
                        pass
                    logger.warning("Failed to parse cached value for key=%s, continuing without cache", cache_key)
                else:
                    return resp_obj
            else:
                logger.debug("Cache miss for id=%s key=%s", qid, cache_key)
        except Exception as e:
            logger.warning("Redis get error for id=%s: %s", qid, str(e))

    # Prepare clients
    # Build Qdrant client using URL and optional API key
    if settings.QDRANT_URL or settings.QDRANT_HOST:
        qdrant_host = settings.qdrant_url
        if settings.QDRANT_API_KEY:
            qclient = QdrantClient(url=qdrant_host, api_key=settings.QDRANT_API_KEY)
        else:
            qclient = QdrantClient(url=qdrant_host)
    else:
        qclient = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    # Embedding function: prefer OpenAI embeddings when key is present
    def embed_text(text: str) -> List[float]:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and openai is not None:
            openai.api_key = api_key
            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            try:
                resp = openai.Embedding.create(input=text, model=model)
                vec = resp["data"][0]["embedding"]
                return vec
            except Exception:
                # fallback to dummy embedding
                pass
        # Dummy embedding: length-based
        v = float(len(text)) / 100.0
        return [v] * 384

    # Compute query embedding
    try:
        query_embedding = embed_text(req.question)
    except Exception as e:
        logger.exception("Embedding error for id=%s: %s", qid, str(e))
        raise HTTPException(status_code=500, detail=f"Embedding error: {str(e)}")

    # Query Qdrant
    try:
        hits = qclient.search(collection_name=req.collection_name, query_vector=query_embedding, limit=req.top_k, with_payload=True)
        logger.info("Qdrant search returned %d hits for id=%s", len(hits) if hits is not None else 0, qid)
    except Exception as e:
        logger.exception("Qdrant search error for id=%s: %s", qid, str(e))
        raise HTTPException(status_code=500, detail=f"Qdrant search error: {str(e)}")

    contexts: List[str] = []
    sources: List[str] = []
    for h in hits:
        payload = getattr(h, "payload", {}) or {}
        text = payload.get("text") or payload.get("content") or ""
        contexts.append(text)
        src = payload.get("filename") or payload.get("source") or str(getattr(h, "id", ""))
        sources.append(src)

    prompt = build_prompt(req.question, contexts)
    logger.debug("Prompt for id=%s: %s", qid, prompt[:1000])

    # Call OpenAI ChatCompletion
    try:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        chat_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        resp = openai.ChatCompletion.create(
            model=chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        answer = resp["choices"][0]["message"]["content"].strip()
        usage = resp.get("usage", {})
        tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        logger.info("OpenAI returned answer for id=%s tokens=%s", qid, tokens)
    except Exception as e:
        logger.exception("OpenAI error for id=%s: %s", qid, str(e))
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

    elapsed = (time.time() - start) * 1000.0
    logger.info("Request id=%s completed in %.2fms", qid, elapsed)

    # Cache the response if enabled
    try:
        if req.use_cache and redis_client is not None:
            cache_value = json.dumps({"answer": answer, "sources": sources, "tokens": tokens, "time_ms": elapsed})
            try:
                # setex expects seconds
                redis_client.setex(cache_key, settings.CACHE_TTL_SECONDS, cache_value)
                logger.info("Cached response for id=%s key=%s ttl=%d", qid, cache_key, 3600)
            except Exception as e:
                logger.warning("Failed to set cache for id=%s: %s", qid, str(e))
    except Exception:
        # tolerate any unexpected errors during caching
        logger.exception("Unexpected error while caching for id=%s", qid)

    # Save history in background
    try:
        saver = HistorySaver()
        # use async variant to avoid blocking the event loop
        background_tasks.add_task(saver.save_async, req.question, answer, tokens, sources)
        logger.info("Scheduled history save for id=%s", qid)
    except Exception as ex:
        logger.exception("Failed to schedule history save for id=%s: %s", qid, str(ex))
        pass

    return {"answer": answer, "sources": sources, "tokens": tokens, "time_ms": elapsed}

