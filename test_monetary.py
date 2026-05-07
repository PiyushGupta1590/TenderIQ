import sys, re, time
sys.path.insert(0, ".")
from backend.services.tender_processor import process_tender_pdf, _RULE_PATTERNS, _UNIT_MAP, _extract_section

# == Test 1: monetary value extraction from regex groups =====================
print("=== Test 1: Monetary value parsing ===")
test_cases = [
    ("9. Minimum annual turnover shall be Rs. 9 Crore",          9e7,  "crore suffix"),
    ("9.1 Average annual turnover of INR 50 lakh",               5e6,  "lakh suffix"),
    ("Minimum turnover: Rs. 1,50,00,000",                        1.5e7,"Indian commas"),
    ("The annual turnover should not be less than Rs.25 Crores", 2.5e7,"Rs.25 Crores"),
    ("Minimum annual turnover >= 500 lakh",                      5e7,  "500 lakhs"),
]

annual_pat = next(p for p in _RULE_PATTERNS if p["field"] == "annual_turnover")
pat = annual_pat["pattern"]

for line, expected, desc in test_cases:
    m = pat.search(line)
    if m:
        raw_num  = m.group(1) if m.lastindex and m.lastindex >= 1 else None
        raw_unit = m.group(2) if m.lastindex and m.lastindex >= 2 else None
        num_clean = re.sub(r"[^\d.]", "", raw_num or "")
        unit_key  = (raw_unit or "").strip().lower()
        val = float(num_clean) * _UNIT_MAP.get(unit_key, 1) if num_clean else 0
        ok  = abs(val - expected) < 1 or (val == 0 and expected == 0)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}]  {desc}")
        print(f"         got={val:,.0f}  expected={expected:,.0f}  (num={raw_num!r}, unit={raw_unit!r})")
    else:
        print(f"  [SKIP]  {desc}  -- pattern did not match (fallback will be used)")

# == Test 2: section extraction ==============================================
print()
print("=== Test 2: Section extraction ===")
full = (
    "SECTION 3 - ELIGIBILITY CRITERIA\n"
    "3.1 Financial Requirements\n"
    "9. The minimum annual turnover of Rs. 9 Crore is required.\n"
    "Clause 9.1 - Technical Requirements\n"
    "The bidder must have ISO 9001 certification.\n"
)
tests_sec = [
    ("9. The minimum annual turnover of Rs. 9 Crore is required.", "Section 9"),
    ("The bidder must have ISO 9001 certification.",               "Section 9.1"),
]
for line, expected in tests_sec:
    got = _extract_section(full, line)
    ok = got == expected
    print(f"  {'[OK  ]' if ok else '[FAIL]'}  got={got!r}  expected={expected!r}")

# == Test 3: full pipeline on real PDF ======================================
print()
print("=== Test 3: GeM tender full pipeline ===")
t0 = time.perf_counter()
result = process_tender_pdf(
    r"data/uploads/GeM-Bidding-4593000.pdf", "GeM-Bidding-4593000.pdf"
)
print(f"  Time: {time.perf_counter()-t0:.1f}s  |  Rules: {len(result.rules)}")
for r in result.rules:
    val_str = f"{r.value:,.0f} {r.unit}" if r.value else (r.string_value or "(present)")
    print(f"  {r.label:45s}  {r.operator.value} {val_str}   [{r.source_section}]")
