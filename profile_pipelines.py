"""
Profile both pipelines stage-by-stage to identify the real bottleneck.
Run: python profile_pipelines.py
"""
import time, sys, os
sys.path.insert(0, ".")

# ── helpers ──────────────────────────────────────────────────────────────────

class Timer:
    def __init__(self, label):
        self.label = label
    def __enter__(self):
        self.t = time.perf_counter()
        return self
    def __exit__(self, *_):
        elapsed = time.perf_counter() - self.t
        print(f"  [{elapsed:6.2f}s]  {self.label}")
        return False

SEP = "=" * 60

# ── pick test files ───────────────────────────────────────────────────────────

TENDER_PDF   = r"data\uploads\GeM-Bidding-4593000.pdf"        # smaller tender
BIDDER_PDF   = r"data\uploads\test_1_pdf.pdf"                  # bidder doc
LARGE_TENDER = r"data\uploads\Tender notice 898092025-520.pdf" # big one

for f in (TENDER_PDF, BIDDER_PDF, LARGE_TENDER):
    if not os.path.exists(f):
        print(f"WARNING: {f} not found — update path in script")

# ═══════════════════════════════════════════════════════════════════════════════
print(SEP)
print("STAGE 1 — TENDER PIPELINE PROFILING")
print(SEP)

import pdfplumber
from backend.services.ocr_engine import TESSERACT_AVAILABLE

print(f"\nTender file  : {TENDER_PDF}  ({os.path.getsize(TENDER_PDF)//1024} KB)")
print(f"Tesseract    : {TESSERACT_AVAILABLE}")

# Stage 1-A: PDF text extraction only
page_texts = []
with Timer("1-A  pdfplumber open + extract_text (all pages)"):
    with pdfplumber.open(TENDER_PDF) as pdf:
        total_pages = len(pdf.pages)
        for page in pdf.pages:
            t = page.extract_text() or ""
            page_texts.append(t)

print(f"         Pages: {total_pages}  |  Total chars: {sum(len(t) for t in page_texts):,}")

# Stage 1-B: OCR fallback check (how many pages had no text?)
blank_pages = sum(1 for t in page_texts if not t.strip())
print(f"         Blank pages (would trigger OCR): {blank_pages}")
if blank_pages and TESSERACT_AVAILABLE:
    from backend.services.ocr_engine import ocr_image
    # time OCR on first blank page
    with pdfplumber.open(TENDER_PDF) as pdf:
        for i, page in enumerate(pdf.pages):
            if not (page.extract_text() or "").strip():
                with Timer(f"1-B  OCR on blank page {i+1}"):
                    img = page.to_image(resolution=200).original
                    ocr_image(img)
                break

# Stage 1-C: Regex pattern matching only (no LLM)
full_text = "\n".join(page_texts)
from backend.services.tender_processor import _RULE_PATTERNS, _get_context_window, _is_mandatory

with Timer("1-C  Regex scan (all patterns × all lines)"):
    matched = []
    seen = set()
    for pn, pt in enumerate(page_texts, 1):
        for line in pt.split("\n"):
            line = line.strip()
            if len(line) < 20:
                continue
            for pat in _RULE_PATTERNS:
                m = pat["pattern"].search(line)
                if m and pat["field"] not in seen:
                    seen.add(pat["field"])
                    matched.append((pat, m, line, pn))
                    break

print(f"         Regex matches found: {len(matched)}")

# Stage 1-D: LLM calls (time each one individually)
from backend.services.llm_extractor import should_use_llm, extract_with_llm, LLM_AVAILABLE
from backend.models.tender import RuleOperator

print(f"\n         LLM available: {LLM_AVAILABLE}")
financial_fields = ("annual_turnover","net_worth","bid_security","performance_guarantee","similar_work_value")
llm_candidates = []
for pat, m, line, pn in matched:
    if pat["operator"] == RuleOperator.GTE and pat["field"] in financial_fields:
        ctx = _get_context_window(page_texts, pn, line)
        needs, reason = should_use_llm(ctx, None, pat["confidence_base"], pat["field"])
        llm_candidates.append((pat["field"], ctx, reason, needs))

print(f"         Financial fields matched: {len(llm_candidates)}")
llm_needed = [(f, c, r) for f, c, r, n in llm_candidates if n]
print(f"         Fields that would call LLM: {len(llm_needed)}")
for f, _, r in llm_needed:
    print(f"           - {f}: {r}")

if llm_needed and LLM_AVAILABLE:
    print()
    for field, ctx, reason in llm_needed[:3]:  # test first 3
        with Timer(f"1-D  LLM call → {field}"):
            extract_with_llm(ctx, field)
else:
    print("         (Skipping LLM timing — not needed or not available)")

# Stage 1-E: Full pipeline end-to-end
print()
with Timer("1-E  FULL process_tender_pdf() end-to-end"):
    from backend.services.tender_processor import process_tender_pdf
    result = process_tender_pdf(TENDER_PDF, os.path.basename(TENDER_PDF))
print(f"         Rules extracted: {len(result.rules)}")

# ═══════════════════════════════════════════════════════════════════════════════
print()
print(SEP)
print("STAGE 2 — BIDDER PIPELINE PROFILING")
print(SEP)

print(f"\nBidder file  : {BIDDER_PDF}  ({os.path.getsize(BIDDER_PDF)//1024} KB)")

# Stage 2-A: PDF layout analysis
from backend.services.layout_analyzer import analyze_pdf_layout, extract_tables_from_pdf, create_smart_chunks

with Timer("2-A  analyze_pdf_layout()"):
    blocks = analyze_pdf_layout(BIDDER_PDF)
print(f"         Blocks: {len(blocks)}")

with Timer("2-B  extract_tables_from_pdf()"):
    tables = extract_tables_from_pdf(BIDDER_PDF)
print(f"         Tables: {len(tables)}")

with Timer("2-C  create_smart_chunks()"):
    chunks = create_smart_chunks(blocks, max_chunk_size=2000)
print(f"         Chunks: {len(chunks)}")

# Stage 2-D: Per-field hybrid extraction (time each individually)
from backend.services.hybrid_extractor import HybridExtractor, ExtractionStatus
from backend.services.bidder_processor import _FIELD_PATTERNS

extractor = HybridExtractor(_FIELD_PATTERNS)

print(f"\n         Fields to extract: {len(_FIELD_PATTERNS)}")
print()
total_llm_time = 0
for field in list(_FIELD_PATTERNS.keys()):
    t0 = time.perf_counter()
    r = extractor.extract_field_hybrid(field, blocks, chunks)
    elapsed = time.perf_counter() - t0
    flag = "  ← LLM" if r.extraction_method in ("llm","hybrid") else ""
    print(f"  [{elapsed:5.2f}s]  {field:30s}  method={r.extraction_method:6s}  status={r.status.value}{flag}")
    if r.extraction_method in ("llm","hybrid"):
        total_llm_time += elapsed

print(f"\n         Total time in LLM fields: {total_llm_time:.2f}s")

# Stage 2-E: Full pipeline end-to-end
print()
with Timer("2-E  FULL process_bidder_files() end-to-end"):
    from backend.services.bidder_processor import process_bidder_files
    res = process_bidder_files([BIDDER_PDF], "Test Bidder", "T-TEST-001")
print(f"         Fields found: {len(res.extracted_fields)}")
print(f"         Status: {res.status}")

# ── Also test the large tender
print()
print(SEP)
print("STAGE 1 (LARGE PDF) — extra test")
print(SEP)
print(f"\nLarge tender: {LARGE_TENDER}  ({os.path.getsize(LARGE_TENDER)//1024} KB)")
with Timer("FULL process_tender_pdf() on large PDF"):
    from backend.services.tender_processor import process_tender_pdf as _ptp
    r2 = _ptp(LARGE_TENDER, os.path.basename(LARGE_TENDER))
print(f"         Pages: {r2.total_pages}  |  Rules: {len(r2.rules)}")

print()
print(SEP)
print("PROFILING COMPLETE")
print(SEP)
