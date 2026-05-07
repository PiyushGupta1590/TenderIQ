"""
Stage 1 — Tender Processor  (Hybrid Regex + LLM Edition)
=========================================================
Pipeline:
  1. Text extraction (pdfplumber + OCR fallback)
  2. Regex pattern matching (fast, deterministic)
  3. Confidence gateway:
       >= 0.85  -> ACCEPT as-is
       0.60-0.84 -> LLM VERIFY (sanity-check regex result)
       < 0.60   -> LLM EXTRACT (let LLM do the work)
     Additionally, certain trigger conditions force LLM regardless of
     confidence: written numbers, FY patterns, Indian comma format,
     impossibly small/large values.
  4. Merge regex + LLM results
  5. Final validation + safety layer

No API key is *required* — the LLM path is only activated when
GROQ_API_KEY or GEMINI_API_KEY is set in the environment.
"""
from __future__ import annotations

import re
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
import pdfplumber
from backend.models.tender import TenderRule, TenderRuleSet, RuleCategory, RuleOperator
from backend.services.ocr_engine import ocr_image, TESSERACT_AVAILABLE
from backend.services.llm_extractor import (
    extract_with_llm,
    should_use_llm,
    validate_financial_value,
    written_number_to_int,
    parse_indian_number,
    looks_like_financial_year,
    LLM_AVAILABLE,
)

logger = logging.getLogger(__name__)


# -- Mandatory vs Optional detection -----------------------------------------
_MANDATORY_SIGNALS = re.compile(
    r"\b(shall|must|mandatory|required|essential|compulsory|"
    r"will\s+be\s+required|is\s+required|are\s+required|"
    r"should\s+have|needs?\s+to|has\s+to|have\s+to)\b",
    re.IGNORECASE,
)
_OPTIONAL_SIGNALS = re.compile(
    r"\b(preferred|desirable|desirably|optional|may|should|"
    r"would\s+be\s+an\s+advantage|advantageous|if\s+available|"
    r"where\s+possible)\b",
    re.IGNORECASE,
)


def _is_mandatory(line: str) -> bool:
    optional_hit = bool(_OPTIONAL_SIGNALS.search(line))
    mandatory_hit = bool(_MANDATORY_SIGNALS.search(line))
    if optional_hit and not mandatory_hit:
        return False
    return True


# -- Currency / number helpers ------------------------------------------------

_UNIT_MAP = {
    "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5,
    "million": 1e6, "m": 1e6,
    "billion": 1e9, "b": 1e9,
    "thousand": 1e3, "k": 1e3,
}


def _sanitize_ocr_line(line: str) -> str:
    """Fix common OCR mis-reads inside numeric-looking contexts."""
    line = re.sub(r"(?<=[\d])O(?=[\d])", "0", line)
    line = re.sub(r"(?<=[\d])[lI|](?=[\d])", "1", line)
    line = re.sub(r"(?<=[\d])S(?=[\d])", "5", line)
    line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", line)
    return line


def _sanitize_ocr_text(text: str) -> str:
    return "\n".join(_sanitize_ocr_line(l) for l in text.splitlines())


def _parse_currency(text: str) -> Tuple[float, str]:
    """
    Return (numeric_value_in_INR, currency_label).
    Handles:
      - Standard digits with commas: 1,00,000 or 1,000,000
      - Unit words: crore, lakh, thousand, etc.
      - Written-out numbers: Sixteen Lakh
      - DOES NOT match financial years (guarded)

    Returns (0.0, '') on failure.
    """
    try:
        # Guard: if text is dominated by a financial-year pattern, be careful
        if looks_like_financial_year(text):
            non_fy = re.sub(r"\b(19|20)\d{2}[-\u2013\u2014]\d{2,4}\b", "", text)
            if not re.search(r"\d{4,}", non_fy):
                return 0.0, ""

        # Try written-out Indian number first (e.g. "Sixteen Lakh Fifty Thousand")
        written_val = written_number_to_int(text)
        if written_val and written_val > 0:
            currency = "INR"
            return float(written_val), currency

        # Try Indian comma-separated number  e.g. 16,50,000
        indian_val = parse_indian_number(text)
        if indian_val and indian_val > 99:
            unit_m = re.search(
                r"\b(crore|lakh|lac|million|billion|thousand|Cr|L|M|B|K)s?\b",
                text, re.IGNORECASE,
            )
            unit = (unit_m.group(1) or "").lower() if unit_m else ""
            multiplier = _UNIT_MAP.get(unit, 1)
            return indian_val * multiplier, "INR"

        # Standard regex extraction
        m = re.search(
            r"(?:Rs\.?|INR|[\u20b9]|USD|\$|EUR|\u20ac)?\s*"
            r"([\d,]+(?:\.\d+)?)\s*"
            r"(crore|lakh|lac|million|billion|thousand|Cr|L|M|B|K)?",
            text, re.IGNORECASE,
        )
        if not m or not m.group(1):
            return 0.0, ""

        raw_num = m.group(1).replace(",", "").strip()
        if not raw_num or not re.fullmatch(r"\d+(\.\d+)?", raw_num):
            return 0.0, ""

        num = float(raw_num)

        # Guard: reject if num looks like a year and no unit word present
        unit_word = (m.group(2) or "").lower()
        if 1900 <= num <= 2100 and not unit_word:
            return 0.0, ""

        multiplier = _UNIT_MAP.get(unit_word, 1)
        currency = (
            "INR" if re.search(r"Rs\.?|INR|[\u20b9]", text)
            else "USD" if re.search(r"\$|USD", text)
            else "INR"
        )
        return num * multiplier, currency

    except Exception:
        return 0.0, ""


def _parse_integer(text: str) -> int:
    m = re.search(r"\b(\d+)\b", text)
    return int(m.group(1)) if m else 0


# -- Rule extraction patterns -------------------------------------------------

_RULE_PATTERNS = [
    # -- FINANCIAL -------------------------------------------------------------
    {
        "pattern": re.compile(
            r"(?:minimum|annual)\s+(?:average\s+)?(?:turnover|revenue|sales)"
            r"[^.]*?(?:Rs\.?|INR|[\u20b9]|\$|USD)?\s*([\d,]+(?:\.\d+)?)\s*(crore|lakh|lac|million|billion|Cr|L|M)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.FINANCIAL,
        "field": "annual_turnover",
        "label": "Minimum Annual Turnover",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.91,
    },
    {
        "pattern": re.compile(
            r"net\s*worth[^.]*?(?:Rs\.?|INR|[\u20b9]|\$)?\s*([\d,]+(?:\.\d+)?)\s*(crore|lakh|lac|million|Cr|L|M)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.FINANCIAL,
        "field": "net_worth",
        "label": "Minimum Net Worth",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.88,
    },
    {
        "pattern": re.compile(
            r"(?:bid\s+security|earnest\s+money|EMD)[^.]*?(?:Rs\.?|INR|[\u20b9]|\$)?\s*([\d,]+(?:\.\d+)?)\s*(crore|lakh|Cr|L)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.FINANCIAL,
        "field": "bid_security",
        "label": "Bid Security / EMD",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.85,
    },
    # Performance Guarantee: Extract PERCENTAGE only, not timeframes
    # Example: "3% of contract value within 28 days" → extract 3 with unit PERCENT
    {
        "pattern": re.compile(
            r"performance\s+(?:security|guarantee|bond)[^.]*?(\d+(?:\.\d+)?)\s*%",
            re.IGNORECASE,
        ),
        "category": RuleCategory.FINANCIAL,
        "field": "performance_guarantee",
        "label": "Performance Guarantee / Security Deposit (%)",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.88,
    },
    # -- TECHNICAL ------------------------------------------------------------
    {
        "pattern": re.compile(
            r"(?:at\s+least|minimum|minimum\s+of)\s+(\d+)\s+years?\s+(?:of\s+)?experience",
            re.IGNORECASE,
        ),
        "category": RuleCategory.TECHNICAL,
        "field": "experience_years",
        "label": "Minimum Experience (Years)",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.87,
    },
    {
        "pattern": re.compile(
            r"(?:at\s+least|minimum|completed|executed)\s+(\d+)\s+(?:similar|comparable|relevant)?\s*(?:projects?|works?|assignments?|contracts?)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.TECHNICAL,
        "field": "completed_projects",
        "label": "Minimum Similar Projects Completed",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.84,
    },
    {
        "pattern": re.compile(
            r"(?:key\s+)?(?:personnel|staff|manpower|engineers?)[^.]*?(\d+)\s+(?:qualified|experienced|technical)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.TECHNICAL,
        "field": "key_personnel",
        "label": "Minimum Key Personnel",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.76,
    },
    {
        "pattern": re.compile(
            r"(?:similar\s+work|similar\s+nature)[^.]*?(?:Rs\.?|INR|[\u20b9])?\s*([\d,]+(?:\.\d+)?)\s*(crore|lakh|Cr|L)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.TECHNICAL,
        "field": "similar_work_value",
        "label": "Single Similar Work Order Value",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.83,
    },
    {
        "pattern": re.compile(
            r"(?:experience|expertise)\s+(?:in|with|of)\s+(?:security|paramilitary|police|defence|armed\s+forces|CRPF|CISF|BSF|ITBP)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.TECHNICAL,
        "field": "security_force_experience",
        "label": "Experience with Security / Paramilitary Forces",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.80,
    },
    {
        "pattern": re.compile(
            r"(?:warranty|guarantee)\s+(?:period|of)\s+(\d+)\s+(?:year|month)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.TECHNICAL,
        "field": "warranty_period",
        "label": "Warranty / Guarantee Period",
        "operator": RuleOperator.GTE,
        "confidence_base": 0.78,
    },
    # -- COMPLIANCE -----------------------------------------------------------
    {
        "pattern": re.compile(
            r"ISO\s*(9001|14001|27001|45001|22000)[:\s]*(?:certification|certified|standard)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.COMPLIANCE,
        "field": "iso_certification",
        "label": "ISO Certification Required",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.78,
    },
    {
        "pattern": re.compile(
            r"(?:valid\s+)?GST\s+(?:registration|number|certificate|enrolled|registered)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.COMPLIANCE,
        "field": "gst_registration",
        "label": "Valid GST Registration",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.92,
    },
    {
        "pattern": re.compile(
            r"(?:PAN\s+(?:card|number|certificate)|Permanent\s+Account\s+Number)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.COMPLIANCE,
        "field": "pan_card",
        "label": "PAN Card",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.90,
    },
    {
        "pattern": re.compile(
            r"(?:MSME|Udyam|Udyog\s+Aadhar|SSI)\s+(?:registration|certificate|certified|registered)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.COMPLIANCE,
        "field": "msme_registration",
        "label": "MSME / Udyam Registration",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.82,
    },
    {
        "pattern": re.compile(
            r"(?:labour\s+law|EPF|ESIC|provident\s+fund)\s+(?:registration|compliance|certificate)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.COMPLIANCE,
        "field": "labour_compliance",
        "label": "Labour Law Compliance (EPF/ESIC)",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.80,
    },
    # REMOVED: Income Tax Return pattern - not a standard tender requirement
    # -- ADMINISTRATIVE -------------------------------------------------------
    {
        "pattern": re.compile(
            r"(?:registered|registration|enlistment)\s+(?:with|under|in)\s+([^.,]+)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.ADMINISTRATIVE,
        "field": "registration",
        "label": "Firm Registration Requirement",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.80,
    },
    {
        "pattern": re.compile(
            r"(?:company|firm|business)\s+(?:registration|incorporation|certificate\s+of\s+incorporation)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.ADMINISTRATIVE,
        "field": "company_registration",
        "label": "Company / Firm Registration Certificate",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.83,
    },
    {
        "pattern": re.compile(
            r"(?:power\s+of\s+attorney|authorisation\s+letter|letter\s+of\s+authority)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.ADMINISTRATIVE,
        "field": "power_of_attorney",
        "label": "Power of Attorney / Authorisation Letter",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.79,
    },
    # -- ELIGIBILITY ----------------------------------------------------------
    {
        "pattern": re.compile(
            r"(?:not\s+)?(?:blacklisted|debarred|banned|suspended)\s+(?:by|from)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.ELIGIBILITY,
        "field": "blacklist_free",
        "label": "Not Blacklisted / Debarred",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.82,
    },
    {
        "pattern": re.compile(
            r"(?:security\s+clearance|police\s+verification|antecedent\s+verification)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.ELIGIBILITY,
        "field": "security_clearance",
        "label": "Security Clearance / Police Verification",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.85,
    },
    {
        "pattern": re.compile(
            r"(?:no\s+)?(?:criminal|court|litigation)\s+(?:case|proceedings?|history)",
            re.IGNORECASE,
        ),
        "category": RuleCategory.ELIGIBILITY,
        "field": "litigation_free",
        "label": "No Criminal / Litigation History",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.78,
    },
    {
        "pattern": re.compile(
            r"(?:solvency|financial\s+soundness|credit\s+rating)\s+(?:certificate|report)?",
            re.IGNORECASE,
        ),
        "category": RuleCategory.ELIGIBILITY,
        "field": "solvency_certificate",
        "label": "Solvency / Financial Soundness Certificate",
        "operator": RuleOperator.PRESENT,
        "confidence_base": 0.80,
    },
]


# -- Context window builder ---------------------------------------------------

def _get_context_window(page_texts: list, page_num: int, line: str, window: int = 3) -> str:
    """Build a multi-line context window around the matched line for LLM analysis."""
    page_text = page_texts[page_num - 1] if page_num <= len(page_texts) else ""
    lines = page_text.splitlines()
    try:
        idx = next(i for i, l in enumerate(lines) if line.strip() in l)
        start = max(0, idx - window)
        end = min(len(lines), idx + window + 1)
        return "\n".join(lines[start:end])
    except StopIteration:
        return line


# -- Decision gateway & merge logic ------------------------------------------

def _hybrid_extract_financial(
    line: str,
    context: str,
    field: str,
    regex_value: float,
    regex_conf: float,
) -> Tuple[float, float, str]:
    """
    Apply the confidence gateway for a financial field.
    Returns (final_value, final_confidence, extraction_method).

    extraction_method: 'regex' | 'llm' | 'regex+llm_verified' | 'fallback' | 'rejected'
    """
    use_llm, reason = should_use_llm(context, regex_value, regex_conf, field)

    if not use_llm:
        return regex_value, regex_conf, "regex"

    logger.info("LLM triggered for field '%s': %s", field, reason)

    llm_value, llm_conf, _raw = extract_with_llm(context, field, context_hint=reason)

    if llm_value is None:
        logger.info("LLM returned no value for '%s'; falling back to regex", field)
        if regex_value:
            # Validate the regex value before using it as fallback —
            # prevents implausibly small numbers (e.g. ₹3 from "03 financial years")
            # from leaking through when LLM is unavailable.
            regex_valid, reject_reason = validate_financial_value(regex_value, field)
            if regex_valid:
                return regex_value, max(0.35, regex_conf - 0.15), "fallback"
            logger.warning(
                "Regex fallback value for '%s' also failed validation: %s — rejecting.",
                field, reject_reason,
            )
        return 0.0, 0.30, "rejected"

    # Safety validation on LLM output
    is_monetary = field in ("annual_turnover", "net_worth", "bid_security",
                            "performance_guarantee", "similar_work_value")
    if is_monetary:
        valid, rejection_reason = validate_financial_value(llm_value, field)
        if not valid:
            logger.warning(
                "LLM value for '%s' failed safety check: %s (value=%s). Falling back.",
                field, rejection_reason, llm_value,
            )
            if regex_value:
                regex_valid, _ = validate_financial_value(regex_value, field)
                if regex_valid:
                    return regex_value, max(0.40, regex_conf - 0.10), "fallback"
            return 0.0, 0.30, "rejected"

    # Compare LLM and regex results
    if regex_value and regex_conf >= 0.60:
        ratio = llm_value / regex_value if regex_value else float("inf")
        if 0.8 <= ratio <= 1.2:
            # Values agree within 20% -- high confidence
            return llm_value, min(0.95, (llm_conf + regex_conf) / 2 + 0.05), "regex+llm_verified"
        else:
            # Disagreement -- prefer LLM but lower confidence
            return llm_value, min(llm_conf, 0.72), "llm"
    else:
        # Pure LLM extraction
        return llm_value, llm_conf, "llm"


# -- Section extractor --------------------------------------------------------

def _extract_section(full_text: str, line: str) -> str:
    """
    Identify the section/clause number this line belongs to.
    Strategy (in priority order):
      1. Explicit keyword: "Section 3", "Clause 9.1", "Para 4"
      2. Numbered heading at start of line: "9." or "9.1" followed by a word
      3. Find the line in full_text and scan backwards for a numbered heading
    """
    # 1. Explicit section/clause keyword on the same line
    m = re.search(
        r"\b(?:section|clause|para(?:graph)?|article|item)\s+(\d+(?:\.\d+)*)",
        line, re.IGNORECASE,
    )
    if m:
        return f"Section {m.group(1)}"

    # 2. Line itself starts with a number followed by text (e.g. "9. Minimum...")
    m = re.match(r"^(\d+(?:\.\d+)*)[.)]\s+\w", line.strip())
    if m:
        return f"Section {m.group(1)}"

    # 3. Scan backwards through full_text for the nearest numbered heading
    line_pos = full_text.find(line[:60])  # locate line in full document
    if line_pos > 0:
        preceding = full_text[max(0, line_pos - 600): line_pos]
        # Look for "Section X", "Clause X", or standalone "X." headings
        for pattern in (
            r"\b(?:section|clause|para)\s+(\d+(?:\.\d+)*)",
            r"^(\d+(?:\.\d+)*)[.)]",
        ):
            hits = list(re.finditer(pattern, preceding, re.IGNORECASE | re.MULTILINE))
            if hits:
                return f"Section {hits[-1].group(1)}"

    return ""


# -- Main rule extractor -----------------------------------------------------

def _process_match(item: Dict[str, Any], full_text: str, page_texts: list) -> TenderRule:
    """
    Convert a single regex match dict into a TenderRule.
    May call the LLM for financial fields — designed to run in a thread.
    """
    pat_def_copy = dict(item["pat_def"])
    m           = item["match"]
    line        = item["line"]
    page_num    = item["page_num"]
    rule_id     = item["rule_id"]

    operator          = pat_def_copy["operator"]
    field             = pat_def_copy["field"]
    numeric_value: Optional[float] = None
    unit: Optional[str]            = None
    string_val: Optional[str]      = None
    extraction_method              = "regex"

    context = _get_context_window(page_texts, page_num, line)

    # -- Numeric fields -------------------------------------------------------
    if operator == RuleOperator.GTE:
        integer_fields = ("experience_years", "completed_projects",
                          "key_personnel", "warranty_period")

        if field in integer_fields:
            try:
                raw_grp = m.group(1).replace(",", "").strip()
                raw_grp = re.sub(r"[^\d.]", "", raw_grp)
                numeric_value = float(raw_grp) if raw_grp else 0.0
                unit = (
                    "months" if "month" in line.lower() and "warranty" in field
                    else "years" if "years" in field
                    else "count"
                )
            except Exception:
                numeric_value = 0.0
        else:
            # Financial field — hybrid regex + LLM gateway
            # Priority 1: use the captured regex groups directly.
            # The pattern already points group(1) at the number and
            # group(2) at the unit word — far more reliable than
            # re-parsing the full line (which picks up section numbers
            # like "9." at the start of the line as the value).
            try:
                raw_num = m.group(1) if m.lastindex and m.lastindex >= 1 else None
                raw_unit = m.group(2) if m.lastindex and m.lastindex >= 2 else None
            except IndexError:
                raw_num, raw_unit = None, None

            regex_val, regex_cur = 0.0, ""
            if raw_num:
                num_clean = re.sub(r"[^\d.]", "", raw_num)
                if num_clean and re.fullmatch(r"\d+(\.\d+)?", num_clean):
                    unit_key = (raw_unit or "").strip().lower()
                    multiplier = _UNIT_MAP.get(unit_key, 1)
                    regex_val = float(num_clean) * multiplier
                    regex_cur = (
                        "INR" if re.search(r"Rs\.?|INR|[\u20b9]", line)
                        else "USD" if re.search(r"\$|USD", line)
                        else "INR"
                    )

            # Priority 2: fallback — parse from the match start so we skip
            # any leading section-number text before the keyword.
            if regex_val == 0:
                regex_val, regex_cur = _parse_currency(line[m.start():])

            base_conf = pat_def_copy["confidence_base"]
            if "equivalent" in line.lower() or "or similar" in line.lower():
                base_conf -= 0.12
            base_conf = max(0.40, min(base_conf, 0.98))

            numeric_value, final_conf, extraction_method = _hybrid_extract_financial(
                line, context, field, regex_val, base_conf
            )
            unit = regex_cur or "INR"
            pat_def_copy["confidence_base"] = final_conf

    # -- PRESENT fields -------------------------------------------------------
    elif operator == RuleOperator.PRESENT:
        string_val = m.group(0)

    # -- Confidence -----------------------------------------------------------
    conf = pat_def_copy["confidence_base"]
    if "equivalent" in line.lower() or "or similar" in line.lower():
        if extraction_method == "regex":
            conf -= 0.12
    conf = max(0.30, min(conf, 0.98))

    mandatory = _is_mandatory(line)

    notes_parts = []
    if extraction_method == "llm":
        notes_parts.append("Value extracted by LLM (regex failed/low confidence).")
    elif extraction_method == "regex+llm_verified":
        notes_parts.append("Regex result verified by LLM.")
    elif extraction_method == "fallback":
        notes_parts.append("LLM unavailable/failed; regex fallback used — please verify.")
    elif extraction_method == "rejected":
        notes_parts.append("Both regex and LLM extractions failed safety checks — value is 0.")
    if not mandatory:
        notes_parts.append("Ambiguous language — please verify if mandatory.")
    if conf < 0.65:
        notes_parts.append("Low confidence — please verify.")

    return TenderRule(
        id=rule_id,
        category=pat_def_copy["category"],
        field=field,
        label=pat_def_copy["label"],
        operator=operator,
        value=numeric_value,
        unit=unit,
        string_value=string_val,
        source_text=line[:300],
        source_page=page_num,
        source_section=_extract_section(full_text, line),
        confidence=round(conf, 2),
        approved=False,
        mandatory=mandatory,
        is_manual=False,
        notes=" ".join(notes_parts) if notes_parts else None,
    )


def _extract_rules_from_text(full_text: str, page_texts: list) -> List[TenderRule]:
    """
    Two-pass extraction:
      Pass 1 — fast regex scan, collect all matches (no I/O)
      Pass 2 — process each match in parallel threads
                (LLM HTTP calls overlap instead of queuing)
    """
    # ── Pass 1: collect regex matches ────────────────────────────────────────
    matched_items: List[Dict[str, Any]] = []
    seen_fields: set = set()
    rule_counter = 1

    for page_num, page_text in enumerate(page_texts, start=1):
        for line in page_text.split("\n"):
            line = line.strip()
            if len(line) < 20:
                continue
            for pat_def in _RULE_PATTERNS:
                m = pat_def["pattern"].search(line)
                if not m:
                    continue
                field = pat_def["field"]
                if field in seen_fields:
                    continue
                seen_fields.add(field)
                matched_items.append({
                    "pat_def":  pat_def,
                    "match":    m,
                    "line":     line,
                    "page_num": page_num,
                    "rule_id":  f"R{rule_counter}",
                })
                rule_counter += 1
                break  # one rule per line

    if not matched_items:
        return []

    # ── Pass 2: process matches in parallel (LLM calls overlap) ─────────────
    # Use up to 6 workers — LLM calls are network I/O bound, so threads help.
    max_workers = min(6, len(matched_items))
    ordered: List[Optional[TenderRule]] = [None] * len(matched_items)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_process_match, item, full_text, page_texts): idx
            for idx, item in enumerate(matched_items)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                ordered[idx] = future.result()
            except Exception as exc:
                logger.warning("Rule extraction failed for item %d: %s", idx, exc)

    return [r for r in ordered if r is not None]


# -- Page renderer -----------------------------------------------------------

def _page_to_pil(page):
    try:
        img_obj = page.to_image(resolution=150)  # 150 DPI: 44% fewer pixels, faster render+OCR
        return img_obj.original
    except Exception as exc:
        logger.warning("Page render failed: %s", exc)
        return None


# -- Public entrypoint -------------------------------------------------------

def process_tender_pdf(file_path: str, filename: str) -> TenderRuleSet:
    """
    Extract eligibility rules from a tender PDF.

    Strategy:
      1. Open PDF once → sequential text extraction only (fast single pass)
      2. Parallel render+OCR per blank page (each thread opens its own PDF handle,
         renders the page at 150 DPI, then OCRs the PIL image outside the context)
      3. Hybrid regex+LLM rule extraction with safety validation
    """
    ocr_used = False

    # ── Step 1: single open, sequential text extraction ──────────────────────
    # extract_text() is fast even for large PDFs; rendering is the slow part,
    # so we defer it to a parallel phase below.
    blank_page_indices: list = []
    page_texts: list = []

    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append(_sanitize_ocr_text(text))
            else:
                page_texts.append("")  # placeholder — filled by OCR below
                if TESSERACT_AVAILABLE:
                    blank_page_indices.append(page_idx)
                else:
                    logger.warning("Page %d/%d: no text + Tesseract unavailable.",
                                   page_idx + 1, total_pages)

    # ── Step 2: parallel render + OCR for blank pages ────────────────────────
    # Each thread opens its own PDF handle so rendering can overlap.
    # Tesseract releases the GIL → OCR also truly parallelises.
    if blank_page_indices:
        logger.info("%d blank pages will be OCR'd (parallel, 4 workers).",
                    len(blank_page_indices))

        def _render_and_ocr(page_idx: int):
            """Open PDF, render one page at 150 DPI, run Tesseract OCR."""
            try:
                with pdfplumber.open(file_path) as pdf:
                    page = pdf.pages[page_idx]
                    img = _page_to_pil(page)
                # img is a plain PIL Image — no longer needs the PDF open
                if img is None:
                    return page_idx, ""
                text, _conf = ocr_image(img)
                return page_idx, _sanitize_ocr_text(text) if text.strip() else ""
            except Exception as exc:
                logger.warning("OCR failed on page %d: %s", page_idx + 1, exc)
                return page_idx, ""

        workers = min(4, len(blank_page_indices))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for idx, text in executor.map(_render_and_ocr, blank_page_indices):
                if text:
                    page_texts[idx] = text
                    ocr_used = True

    if ocr_used:
        logger.info("OCR fallback used in '%s'.", filename)

    full_text = "\n".join(page_texts)
    rules = _extract_rules_from_text(full_text, page_texts)

    first_lines = full_text[:500]
    tender_name = filename.replace(".pdf", "").replace("_", " ").title()
    ref_m = re.search(
        r"(?:tender|NIT|RFP|RFQ|ref(?:erence)?)[^\w]*([\\w\-/]+)", first_lines, re.IGNORECASE
    )
    tender_ref = ref_m.group(1) if ref_m else f"T-{uuid.uuid4().hex[:6].upper()}"

    return TenderRuleSet(
        tender_id=str(uuid.uuid4()),
        tender_name=tender_name,
        tender_ref=tender_ref,
        uploaded_filename=filename,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        total_pages=total_pages,
        rules=rules,
        approved=False,
    )
