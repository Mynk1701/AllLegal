"""
SQLAlchemy ORM models for AllLegal database.
Defines tables for cases and search logs.
"""
from sqlalchemy import Column, String, Integer, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class CaseMetadata(Base):
    """
    Table for storing legal case metadata.
    From PDFs or direct uploads.
    """
    __tablename__ = "cases"

    case_id = Column(String(100), primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    court = Column(String(200), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    judge = Column(String(200), nullable=True)
    summary = Column(Text, nullable=False)
    case_number = Column(String(100), nullable=False, unique=True)
    pdf_filename = Column(String(255), nullable=True)  # Original PDF filename
    pdf_url = Column(String(500), nullable=True)  # URL to stored PDF
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CaseMetadata(case_id='{self.case_id}', title='{self.title}')>"


class SearchLog(Base):
    """
    Table for logging all user searches.
    Used for analytics and debugging.
    """
    __tablename__ = "search_logs"

    search_id = Column(String(100), primary_key=True, index=True)
    query = Column(String(500), nullable=False, index=True)
    results_count = Column(Integer, default=0)
    search_time_ms = Column(Float, nullable=True)  # Time taken to search
    filters_applied = Column(String(500), nullable=True)  # JSON string of filters
    user_id = Column(String(100), nullable=True, index=True)  # From JWT token
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SearchLog(search_id='{self.search_id}', query='{self.query}', results={self.results_count})>"
