"""
LLM Extractor — Groq Free Tier (llama-3.1-8b-instant / gemma2-9b-it)
Called ONLY when regex confidence is low/medium, or when specific failure
conditions are detected (written-out numbers, fiscal-year confusion, etc.)

Provides:
  - extract_with_llm(text, field, context_hint) → (value, confidence, raw)
  - validate_llm_output(value, field)          → (is_valid, reason)
  - written_number_to_int(text)               → int | None  (Indian number words)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)



import backend.config as config

GROQ_API_KEY = getattr(config, "GROQ_API_KEY", "")
GEMINI_API_KEY = getattr(config, "GEMINI_API_KEY", "")

GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"          # free tier, fast

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

LLM_AVAILABLE: bool = bool(GROQ_API_KEY or GEMINI_API_KEY)

# ── Simple thread-safe LLM response cache ────────────────────────────────────
_LLM_CACHE: dict = {}
_LLM_CACHE_LOCK = threading.Lock()
_LLM_CACHE_MAX = 256


def _make_cache_key(source_text: str, field: str) -> str:
    return hashlib.md5(f"{field}:{source_text[:500]}".encode()).hexdigest()

# ── Indian number-word → integer ─────────────────────────────────────────────

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

_SCALE = {
    "hundred": 100,
    "thousand": 1_000,
    "lakh": 1_00_000,
    "lakhs": 1_00_000,
    "lac": 1_00_000,
    "lacs": 1_00_000,
    "crore": 1_00_00_000,
    "crores": 1_00_00_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}


# Digit-word sentinel: written_number_to_int only fires when actual
# cardinal words (zero..ninety) are present, not just scale words like
# "crore" or "lakh" standing next to a digit.
_CARDINAL_WORDS = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\b",
    re.IGNORECASE,
)


def written_number_to_int(text: str) -> Optional[int]:
    """
    Parse Indian-English written numbers to integers.
    Examples:
      "Sixteen Lakh Fifty Thousand"       → 1650000
      "Rupees Sixteen Lakh Fifty Thousand Only" → 1650000
      "Two Crore Twenty Five Lakh"        → 22500000
      "Five Thousand Only"                → 5000
    Returns None if parsing fails or no CARDINAL number-words detected.
    IMPORTANT: does NOT fire for "Rs. 5 Crore" — that has digit 5, not word "five".
    """
    # Gate: must contain at least one cardinal word (five, sixteen, etc.)
    # This prevents "5 Crore" from being parsed as 1 Crore.
    if not _CARDINAL_WORDS.search(text):
        return None

    text = text.lower()
    # Strip noise words
    text = re.sub(r"\b(rupees?|inr|rs\.?|only|and|the|a|an)\b", " ", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    words = text.split()

    if not any(w in _ONES or w in _SCALE for w in words):
        return None

    total = 0
    current = 0

    for word in words:
        if word in _ONES:
            current += _ONES[word]
        elif word == "hundred":
            current = current * 100 if current else 100
        elif word in _SCALE and word != "hundred":
            scale = _SCALE[word]
            if current == 0:
                current = 1
            total += current * scale
            current = 0
        # else: unknown word — skip

    total += current
    return total if total > 0 else None


# ── Year-range / financial-year detection ────────────────────────────────────

_FY_PATTERN = re.compile(
    r"\b(19|20)\d{2}[-–—]\d{2,4}\b"       # 2021-22, 2021-2022
    r"|\bFY\s*(19|20)\d{2}\b"              # FY2023
    r"|\bfinancial\s+year\b",
    re.IGNORECASE,
)


def looks_like_financial_year(text: str) -> bool:
    """Return True if text contains a financial year expression."""
    return bool(_FY_PATTERN.search(text))


# ── Sanity / safety layer ─────────────────────────────────────────────────────

# Minimum plausible values for financial fields (in INR)
_MIN_PLAUSIBLE = {
    "annual_turnover": 10_000,          # ₹10 000 absolute minimum
    "net_worth": 10_000,
    "bid_security": 500,                # ₹500 EMD is possible for tiny tenders
    "performance_guarantee": 500,
    "similar_work_value": 1_000,
}

# Maximum plausible values (sanity cap — prevents interpreting years as money)
_MAX_PLAUSIBLE = {
    "annual_turnover": 1_000_000_000_000,   # ₹1 lakh crore
    "net_worth": 1_000_000_000_000,
    "bid_security": 500_000_000,
    "performance_guarantee": 500_000_000,
    "similar_work_value": 1_000_000_000,
}


def validate_financial_value(value: float, field: str) -> Tuple[bool, str]:
    """
    Sanity-check a numeric financial extraction.
    Returns (is_valid, rejection_reason_or_empty).
    """
    if value <= 0:
        return False, "Value is zero or negative"

    # Year-range detector: values like 2021, 2022, 2023 are almost certainly years
    if 1900 <= value <= 2100:
        return False, f"Value {value:.0f} looks like a calendar/financial year, not a monetary amount"

    min_v = _MIN_PLAUSIBLE.get(field, 100)
    if value < min_v:
        return False, f"Value ₹{value:,.0f} is implausibly small for field '{field}' (min ₹{min_v:,})"

    max_v = _MAX_PLAUSIBLE.get(field, 1e15)
    if value > max_v:
        return False, f"Value ₹{value:,.2e} exceeds plausible cap for field '{field}'"

    return True, ""


# ── Indian comma-format parser ────────────────────────────────────────────────

def parse_indian_number(text: str) -> Optional[float]:
    """
    Parse Indian-format numbers like 16,50,000 or 1,00,00,000.
    Handles both Indian grouping (2-digit groups) and Western grouping (3-digit groups).
    Returns float or None.
    """
    # Match any comma-separated number with at least one comma
    m = re.search(r"(\d{1,3}(?:,\d{2,3})+)", text)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


# ── LLM call helpers ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a procurement document parser for Indian government tenders.
Your ONLY task is to extract a single numeric value or document-presence flag from a text snippet.

Rules:
1. Return ONLY valid JSON — no prose, no markdown, no backticks.
2. If the answer is a currency amount, convert it to a plain integer in FULL RUPEES (no commas, no units).
3. Written-out numbers like "Sixteen Lakh Fifty Thousand" = 1650000.
4. Indian comma format "16,50,000" = 1650000.
5. If you see a financial-year like "2021-22" near a currency word, it is a year, NOT money.
6. If the field is a document (gst_registration, pan_card, etc.), return {"present": true} if evidence found.
7. If you cannot determine the value with confidence, return {"value": null, "confidence": 0.2}.
8. Never invent values not present in the source text.

CRITICAL EXTRACTION RULES:
- For EMD/Bid Security: Prioritize LARGE comma-formatted numbers over small reference numbers
  Example: "EMD of Rs. 16,50,000 (Appendix-3)" → extract 1650000, NOT 3
  
- For Performance Guarantee: Extract PERCENTAGE values, NOT timeframes
  Example: "3% of contract value within 28 days" → extract 3 with unit "PERCENT", NOT 28
  Ignore "days" or "months" - these are deadlines, not amounts
  
- Do NOT extract "Income Tax Return" or "ITR filing" unless explicitly stated as a requirement

Response schema (choose one):
{"value": <integer_or_float>, "unit": "<INR|USD|years|count|PERCENT>", "confidence": <0.0-1.0>}
{"present": <true|false>, "confidence": <0.0-1.0>}
{"value": null, "confidence": <0.0-1.0>}
"""


def _call_groq(user_message: str, retries: int = 2) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 150,
        "temperature": 0.0,
    }
    for attempt in range(retries + 1):
        try:
            resp = requests.post(GROQ_BASE_URL, json=payload, headers=headers, timeout=15)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Groq call failed (attempt %d): %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(1)
    return None


def _call_gemini(user_message: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    url = f"{GEMINI_BASE_URL}?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{_SYSTEM_PROMPT}\n\n{user_message}"}
                ]
            }
        ],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 150},
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
        return None


def _parse_llm_response(raw: str) -> Optional[dict]:
    """Parse and clean LLM JSON response."""
    # Strip markdown fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON object from text
        m = re.search(r"\{[^}]+\}", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_with_llm(
    source_text: str,
    field: str,
    context_hint: str = "",
) -> Tuple[Optional[float], float, str]:
    """
    Ask an LLM to extract a specific field value from source_text.
    Returns (numeric_value_or_None, confidence, raw_text_found).

    Falls back to Gemini if Groq fails, returns (None, 0.0, '') if both fail.
    Results are cached in-memory to avoid duplicate API calls.
    """
    if not LLM_AVAILABLE:
        return None, 0.0, ""

    # Cache lookup
    cache_key = _make_cache_key(source_text, field)
    with _LLM_CACHE_LOCK:
        if cache_key in _LLM_CACHE:
            logger.debug("LLM cache hit for field '%s'", field)
            return _LLM_CACHE[cache_key]

    prompt = (
        f"Extract the value for field: '{field}'\n"
        f"Context hint: {context_hint}\n\n"
        f"Source text:\n```\n{source_text[:1500]}\n```"
    )

    raw_response = _call_groq(prompt) or _call_gemini(prompt)
    if not raw_response:
        return None, 0.0, ""

    parsed = _parse_llm_response(raw_response)
    if not parsed:
        logger.warning("LLM returned unparseable response for field '%s': %s", field, raw_response[:100])
        return None, 0.0, ""

    confidence = float(parsed.get("confidence", 0.5))

    # Document presence field
    if "present" in parsed:
        val = 1.0 if parsed["present"] else 0.0
        return val, confidence, raw_response

    # Numeric field
    value = parsed.get("value")
    if value is None:
        return None, confidence, raw_response

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        result = (None, 0.2, raw_response)
        with _LLM_CACHE_LOCK:
            if len(_LLM_CACHE) >= _LLM_CACHE_MAX:
                del _LLM_CACHE[next(iter(_LLM_CACHE))]
            _LLM_CACHE[cache_key] = result
        return result

    result = (numeric, confidence, raw_response)
    with _LLM_CACHE_LOCK:
        if len(_LLM_CACHE) >= _LLM_CACHE_MAX:
            del _LLM_CACHE[next(iter(_LLM_CACHE))]
        _LLM_CACHE[cache_key] = result
    return result


def should_use_llm(
    text: str,
    regex_value: Optional[float],
    regex_confidence: float,
    field: str,
) -> Tuple[bool, str]:
    """
    Decide whether to invoke LLM for this extraction.
    Returns (should_call_llm, reason).

    Call LLM if any of:
    - regex_confidence < 0.60  (low confidence — LLM extract mode)
    - 0.60 ≤ regex_confidence < 0.85  (medium — LLM verify mode)
    - Written number words detected in text
    - Financial year detected and field is monetary
    - regex_value fails sanity check for a monetary field
    - Indian comma-format number detected (regex may misparse)
    """
    if not LLM_AVAILABLE:
        return False, "no LLM configured"

    # Written number words (e.g. "Sixteen Lakh")
    has_written = bool(re.search(
        r"\b(crore|lakh|lac|thousand|hundred|million|billion)\b.*\b(only|rupees?)\b"
        r"|\b(rupees?|inr)\b.*\b(crore|lakh|lac|thousand)\b",
        text, re.IGNORECASE
    ))
    if has_written:
        return True, "written-out currency words detected"

    # Financial year confusion
    is_monetary = field in ("annual_turnover", "net_worth", "bid_security",
                            "performance_guarantee", "similar_work_value")
    if is_monetary and looks_like_financial_year(text):
        return True, "financial year pattern near monetary field"

    # Sanity check on existing regex value
    if regex_value is not None and is_monetary:
        valid, reason = validate_financial_value(regex_value, field)
        if not valid:
            return True, f"regex value failed sanity: {reason}"

    # Indian comma format
    indian_m = re.search(r"\d{1,2}(?:,\d{2})+", text)
    if indian_m and is_monetary:
        return True, "Indian comma-format number detected"

    # Confidence thresholds
    if regex_confidence < 0.60:
        return True, f"low regex confidence ({regex_confidence:.2f})"
    if regex_confidence < 0.85:
        return True, f"medium regex confidence ({regex_confidence:.2f}) — LLM verify"

    return False, "regex result is reliable"
