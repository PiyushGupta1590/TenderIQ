"""TenderIQ Pydantic Models — Evaluation & Reports"""
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class Verdict(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class AuditEntry(BaseModel):
    """Immutable record of every automated decision — required for govt procurement audit."""
    timestamp: str
    bidder_id: str
    bidder_name: str
    rule_id: str
    rule_label: str
    rule_mandatory: bool
    verdict: Verdict
    confidence: float
    found_value: Optional[str] = None
    required_value: Optional[str] = None
    source_document: Optional[str] = None
    source_page: Optional[int] = None
    decision_basis: str                  # free-text explanation of why this verdict was issued
    automated: bool = True               # False if officer manually overrode


class RuleResult(BaseModel):
    rule_id: str
    rule_label: str
    rule_description: str
    rule_mandatory: bool = True          # propagated from TenderRule.mandatory
    required_value: Optional[float] = None
    required_unit: Optional[str] = None
    found_value: Optional[float] = None
    found_raw: Optional[str] = None
    verdict: Verdict
    confidence: float
    source_document: Optional[str] = None
    source_page: Optional[int] = None
    explanation: str
    needs_officer_action: bool = False
    officer_note: Optional[str] = None


class BidderResult(BaseModel):
    bidder_id: str
    bidder_name: str
    overall_verdict: Verdict
    mandatory_verdict: Verdict           # verdict considering ONLY mandatory rules
    rule_results: List[RuleResult]
    eligible_count: int
    not_eligible_count: int
    manual_review_count: int
    mandatory_fail_count: int = 0        # rules that are mandatory and failed
    officer_override: Optional[Verdict] = None
    officer_override_note: Optional[str] = None


class EvaluationReport(BaseModel):
    report_id: str
    tender_id: str
    tender_name: str
    tender_ref: str
    generated_at: str
    total_bidders: int
    eligible_count: int
    not_eligible_count: int
    manual_review_count: int
    bidder_results: List[BidderResult]
    ai_confidence_avg: float
    audit_log: List[AuditEntry] = []     # complete decision trail
    finalized: bool = False
    finalized_at: Optional[str] = None
    evaluator: str = "Officer"
