"""
Test both pipelines across all available PDFs.
Run: python test_all_pdfs.py
"""
import time, sys, os
sys.path.insert(0, ".")

SEP = "=" * 65

def fmt(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds/60:.1f}min"

# ── discover all test files ───────────────────────────────────────────────────
UPLOAD_DIR = r"data\uploads"
all_files = [
    os.path.join(UPLOAD_DIR, f)
    for f in os.listdir(UPLOAD_DIR)
    if os.path.isfile(os.path.join(UPLOAD_DIR, f))
]

pdf_files  = [f for f in all_files if f.endswith(".pdf")]
docx_files = [f for f in all_files if f.endswith((".docx", ".doc"))]

print(SEP)
print(f"Found {len(pdf_files)} PDF(s) and {len(docx_files)} DOCX(s)")
print(SEP)

# ══════════════════════════════════════════════════════════════════════════════
print("\n🟦  STAGE 1 — TENDER PIPELINE  (all PDFs)\n")

from backend.services.tender_processor import process_tender_pdf

tender_summary = []
for fpath in sorted(pdf_files):
    fname = os.path.basename(fpath)
    size_kb = os.path.getsize(fpath) // 1024
    t0 = time.perf_counter()
    try:
        result = process_tender_pdf(fpath, fname)
        elapsed = time.perf_counter() - t0
        rules = len(result.rules)
        pages = result.total_pages
        print(f"  ✅  [{fmt(elapsed):>6}]  {fname}")
        print(f"         {pages} pages  |  {rules} rules extracted  |  {size_kb} KB")
        tender_summary.append((fname, elapsed, pages, rules, True))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"  ❌  [{fmt(elapsed):>6}]  {fname}  →  {type(e).__name__}: {e}")
        tender_summary.append((fname, elapsed, 0, 0, False))
    print()

# ══════════════════════════════════════════════════════════════════════════════
print(SEP)
print("\n🟩  STAGE 2 — BIDDER PIPELINE  (all files)\n")

from backend.services.bidder_processor import process_bidder_files

bidder_files = pdf_files + docx_files
bidder_summary = []

for fpath in sorted(bidder_files):
    fname = os.path.basename(fpath)
    size_kb = os.path.getsize(fpath) // 1024
    t0 = time.perf_counter()
    try:
        result = process_bidder_files([fpath], "Test Bidder", "T-TEST-001")
        elapsed = time.perf_counter() - t0
        n_fields = len(result.extracted_fields)
        found    = sum(1 for f in result.extracted_fields if f.value is not None)
        status   = result.status
        print(f"  ✅  [{fmt(elapsed):>6}]  {fname}")
        print(f"         {found}/{n_fields} fields found  |  status={status}  |  {size_kb} KB")
        # Show found fields
        for field in result.extracted_fields:
            if field.value is not None:
                print(f"           • {field.field_name:30s} = {str(field.value)[:50]}"
                      f"  [{field.extraction_method}  conf={field.confidence:.2f}]")
        bidder_summary.append((fname, elapsed, found, n_fields, True))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"  ❌  [{fmt(elapsed):>6}]  {fname}  →  {type(e).__name__}: {e}")
        bidder_summary.append((fname, elapsed, 0, 0, False))
    print()

# ══════════════════════════════════════════════════════════════════════════════
print(SEP)
print("SUMMARY")
print(SEP)

print("\nStage 1 (Tender):")
for fname, t, pages, rules, ok in tender_summary:
    status = "✅" if ok else "❌"
    print(f"  {status}  {fname:<45}  {fmt(t):>7}  {rules} rules")

print("\nStage 2 (Bidder):")
for fname, t, found, total, ok in bidder_summary:
    status = "✅" if ok else "❌"
    print(f"  {status}  {fname:<45}  {fmt(t):>7}  {found}/{total} fields")
