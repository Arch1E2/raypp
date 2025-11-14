from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from src.database.database import Base


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    tokens = Column(Integer, nullable=True)
    sources = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
