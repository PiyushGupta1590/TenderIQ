"""TenderIQ Pydantic Models — Tender Rules"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RuleCategory(str, Enum):
    FINANCIAL = "financial"
    TECHNICAL = "technical"
    ADMINISTRATIVE = "administrative"
    COMPLIANCE = "compliance"
    ELIGIBILITY = "eligibility"


class RuleOperator(str, Enum):
    GTE = ">="
    LTE = "<="
    GT = ">"
    LT = "<"
    EQ = "=="
    PRESENT = "present"   # field must exist / be non-empty
    CONTAINS = "contains"


class TenderRule(BaseModel):
    id: str
    category: RuleCategory
    field: str                        # e.g. "annual_turnover"
    label: str                        # Human-readable label
    operator: RuleOperator
    value: Optional[float] = None     # numeric threshold (None for PRESENT)
    unit: Optional[str] = None        # "INR", "USD", "years", etc.
    string_value: Optional[str] = None  # for CONTAINS rules
    source_text: str                  # raw sentence from tender PDF
    source_page: int = 1
    source_section: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    approved: bool = False
    mandatory: bool = True            # True = disqualifying if failed; False = optional/desirable
    is_manual: bool = False           # True = officer-added, not auto-extracted
    notes: Optional[str] = None


class TenderRuleSet(BaseModel):
    tender_id: str
    tender_name: str
    tender_ref: str
    uploaded_filename: str
    uploaded_at: str
    total_pages: int
    rules: List[TenderRule] = []
    approved: bool = False            # True once officer confirms all rules
    approved_at: Optional[str] = None
