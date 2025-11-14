import asyncio
from sqlalchemy import create_engine, JSON
from sqlalchemy.orm import sessionmaker

import src.database.database as db_module
from src.models.query_history import QueryHistory
from src.services.history import HistorySaver


def setup_test_db():
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    # SQLite doesn't support PostgreSQL JSONB; switch the column type to generic JSON for tests
    try:
        QueryHistory.sources.type = JSON()
    except Exception:
        # be tolerant if attribute replacement is not possible
        pass

    # Create tables based on the declarative Base used by the project
    db_module.Base.metadata.create_all(engine)
    return engine, SessionLocal


def test_history_save_sync(monkeypatch):
    engine, SessionLocal = setup_test_db()
    # Replace SessionLocal used by HistorySaver with the test sessionmaker
    monkeypatch.setattr(db_module, "SessionLocal", SessionLocal)

    saver = HistorySaver()
    saver.save("Q1", "A1", 5, ["s1"])

    # Verify row inserted
    session = SessionLocal()
    try:
        rows = session.query(QueryHistory).all()
        assert len(rows) == 1
        r = rows[0]
        assert r.question == "Q1"
        assert r.answer == "A1"
        assert r.tokens == 5
        # sources stored as JSON list
        assert r.sources == ["s1"]
    finally:
        session.close()


def test_history_save_async(monkeypatch):
    engine, SessionLocal = setup_test_db()
    monkeypatch.setattr(db_module, "SessionLocal", SessionLocal)

    saver = HistorySaver()
    asyncio.run(saver.save_async("Q2", "A2", 7, ["s2"]))

    session = SessionLocal()
    try:
        rows = session.query(QueryHistory).filter_by(question="Q2").all()
        assert len(rows) == 1
        r = rows[0]
        assert r.answer == "A2"
        assert r.tokens == 7
        assert r.sources == ["s2"]
    finally:
        session.close()
