"""
Quick smoke-test for the hybrid extraction improvements.
Run with: python -m backend.tests.test_extraction
No API key required — tests only regex + written-number + sanity logic.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.services.llm_extractor import (
    written_number_to_int,
    parse_indian_number,
    validate_financial_value,
    looks_like_financial_year,
)
from backend.services.tender_processor import _parse_currency

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def check(label, got, expected):
    ok = got == expected
    print(f"  {'[OK]' if ok else '[FAIL]'}  {label}")
    print(f"         expected={expected!r}  got={got!r}")
    results.append(ok)


def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# ── 1. Written-number parser ──────────────────────────────────────────────────
section("1. Written number → integer")

check("Sixteen Lakh Fifty Thousand", written_number_to_int("Sixteen Lakh Fifty Thousand"), 1_650_000)
check("Two Crore Twenty Five Lakh", written_number_to_int("Two Crore Twenty Five Lakh"), 2_25_00_000)
check("Five Thousand Only", written_number_to_int("Five Thousand Only"), 5_000)
check("Rupees Ten Lakh only", written_number_to_int("Rupees Ten Lakh only"), 10_00_000)
check("None (digit text)", written_number_to_int("1234"), None)


# ── 2. Indian comma-number parser ─────────────────────────────────────────────
section("2. Indian comma format")

check("16,50,000", parse_indian_number("16,50,000"), 1_650_000)
check("1,00,00,000", parse_indian_number("1,00,00,000"), 1_00_00_000)
check("Rs. 25,000", parse_indian_number("Rs. 25,000"), 25_000)


# ── 3. Financial year guard ───────────────────────────────────────────────────
section("3. Financial year detection")

check("2021-22 is a year", looks_like_financial_year("turnover for 2021-22"), True)
check("FY2023 is a year", looks_like_financial_year("FY2023 figures"), True)
check("Normal number not a year", looks_like_financial_year("Rs. 50 lakh turnover"), False)


# ── 4. _parse_currency (enhanced) ────────────────────────────────────────────
section("4. _parse_currency — written numbers & FY guards")

val, cur = _parse_currency("Annual Turnover: Rupees Sixteen Lakh Fifty Thousand Only")
check("Written: Sixteen Lakh Fifty Thousand", val, 1_650_000.0)
check("Currency label INR", cur, "INR")

val, cur = _parse_currency("EMD of Rs. 16,50,000")
check("Indian comma EMD: 16,50,000", val, 1_650_000.0)

val, cur = _parse_currency("Turnover for FY 2021-22")
check("FY year rejected (should be 0)", val, 0.0)

val, cur = _parse_currency("Turnover of Rs. 5 Crore")
check("5 Crore = 50000000", val, 5e7)

val, cur = _parse_currency("EMD: Rs. 2021")   # year misread as EMD
check("Year 2021 misread as money rejected", val, 0.0)


# ── 5. Safety layer ───────────────────────────────────────────────────────────
section("5. Sanity / safety validation")

ok, reason = validate_financial_value(3.0, "bid_security")
check("EMD of Rs.3 rejected (too small)", ok, False)

ok, reason = validate_financial_value(2021.0, "annual_turnover")
check("2021 as turnover rejected (looks like year)", ok, False)

ok, reason = validate_financial_value(5_000_000.0, "annual_turnover")
check("50 lakh turnover accepted", ok, True)

ok, reason = validate_financial_value(50_000.0, "bid_security")
check("50k EMD accepted", ok, True)


# ── Summary ───────────────────────────────────────────────────────────────────
section("SUMMARY")
passed = sum(results)
total = len(results)
print(f"\n  {passed}/{total} tests passed")
if passed == total:
    print(f"  {PASS} All tests passed!")
    sys.exit(0)
else:
    print(f"  {FAIL} {total - passed} test(s) failed")
    sys.exit(1)
