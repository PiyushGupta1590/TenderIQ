"""SQLAlchemy ORM table definitions for TenderIQ.

Design decisions:
- Complex nested arrays (rules, extracted_fields, bidder_results, audit_log)
  are stored as PostgreSQL JSONB columns — avoids over-normalisation while
  still allowing Postgres JSON operators/GIN indexes later.
- Scalar fields are typed columns for query performance (filtering, sorting).
"""
from sqlalchemy import Column, String, Boolean, Integer, Float
from sqlalchemy.dialects.postgresql import JSONB

from backend.database import Base


class TenderTable(Base):
    __tablename__ = "tenders"

    tender_id         = Column(String, primary_key=True)
    tender_name       = Column(String,  nullable=False, default="")
    tender_ref        = Column(String,  nullable=False, default="")
    uploaded_filename = Column(String,  nullable=False, default="")
    uploaded_at       = Column(String,  nullable=False, default="")
    total_pages       = Column(Integer, nullable=False, default=0)
    rules             = Column(JSONB,   nullable=False, default=list)
    approved          = Column(Boolean, nullable=False, default=False)
    approved_at       = Column(String,  nullable=True)


class BidderTable(Base):
    __tablename__ = "bidders"

    bidder_id           = Column(String,  primary_key=True)
    bidder_name         = Column(String,  nullable=False, default="")
    tender_id           = Column(String,  nullable=False, default="")
    uploaded_files      = Column(JSONB,   nullable=False, default=list)
    uploaded_at         = Column(String,  nullable=False, default="")
    status              = Column(String,  nullable=False, default="queued")
    progress            = Column(Integer, nullable=False, default=0)
    extracted_fields    = Column(JSONB,   nullable=False, default=list)
    ocr_confidence_avg  = Column(Float,   nullable=False, default=0.0)
    processing_notes    = Column(JSONB,   nullable=False, default=list)
    confirmed           = Column(Boolean, nullable=False, default=False)


class ReportTable(Base):
    __tablename__ = "reports"

    report_id            = Column(String,  primary_key=True)
    tender_id            = Column(String,  nullable=False, default="")
    tender_name          = Column(String,  nullable=False, default="")
    tender_ref           = Column(String,  nullable=False, default="")
    generated_at         = Column(String,  nullable=False, default="")
    total_bidders        = Column(Integer, nullable=False, default=0)
    eligible_count       = Column(Integer, nullable=False, default=0)
    not_eligible_count   = Column(Integer, nullable=False, default=0)
    manual_review_count  = Column(Integer, nullable=False, default=0)
    bidder_results       = Column(JSONB,   nullable=False, default=list)
    ai_confidence_avg    = Column(Float,   nullable=False, default=0.0)
    audit_log            = Column(JSONB,   nullable=False, default=list)
    finalized            = Column(Boolean, nullable=False, default=False)
    finalized_at         = Column(String,  nullable=True)
    evaluator            = Column(String,  nullable=False, default="Officer")
