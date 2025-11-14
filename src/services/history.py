import asyncio
from typing import List, Optional

from src.database.database import SessionLocal
from src.models.query_history import QueryHistory


class HistorySaver:
    """History saver using SQLAlchemy ORM sessions.

    Provides both sync .save(...) and async .save_async(...) methods.
    Async variant offloads DB work to a thread so it doesn't block the event loop
    and does not require async DB drivers.
    """

    def __init__(self):
        self.SessionLocal = SessionLocal

    def _save_sync(self, question: str, answer: str, tokens: Optional[int] = None, sources: Optional[List[str]] = None):
        session = self.SessionLocal()
        try:
            qh = QueryHistory(question=question, answer=answer, tokens=tokens, sources=sources or [])
            session.add(qh)
            session.commit()
        except Exception:
            try:
                session.rollback()
            except Exception:
                pass
        finally:
            session.close()

    def save(self, question: str, answer: str, tokens: Optional[int] = None, sources: Optional[List[str]] = None):
        """Sync save; kept for compatibility."""
        self._save_sync(question, answer, tokens, sources)

    async def save_async(self, question: str, answer: str, tokens: Optional[int] = None, sources: Optional[List[str]] = None):
        """Async save that runs DB operations in a thread to avoid blocking the event loop."""
        try:
            await asyncio.to_thread(self._save_sync, question, answer, tokens, sources)
        except Exception:
            # swallow errors - history saving must not break main flow
            pass
