"""TenderIQ Pydantic Models — Bidder Data"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum


class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    MANUAL_REVIEW = "manual_review"
    ERROR = "error"


class ExtractedField(BaseModel):
    field: str
    value: Optional[Any] = None
    raw_text: Optional[str] = None
    confidence: float = 0.0
    source_page: int = 1
    source_file: Optional[str] = None   # which uploaded file contained this evidence
    needs_review: bool = False
    note: Optional[str] = None


class BidderData(BaseModel):
    bidder_id: str
    bidder_name: str
    tender_id: str
    uploaded_files: List[str] = []
    uploaded_at: str
    status: ProcessingStatus = ProcessingStatus.QUEUED
    progress: int = 0                 # 0-100
    extracted_fields: List[ExtractedField] = []
    ocr_confidence_avg: float = 0.0
    processing_notes: List[str] = []
    confirmed: bool = False
