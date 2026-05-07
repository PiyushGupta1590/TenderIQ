import sys, time
sys.path.insert(0, ".")
from backend.services.tender_processor import process_tender_pdf

# Test on Tender 16012026-908.pdf which the test_all_pdfs showed extracts 7 rules
PDFs = [
    r"data/uploads/Tender 16012026-908.pdf",
    r"data/uploads/GeM-Bidding-4593000.pdf",
    r"data/uploads/test_1_pdf.pdf",
]

for pdf_path in PDFs:
    import os
    if not os.path.exists(pdf_path):
        continue
    fname = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"  {fname}  ({os.path.getsize(pdf_path)//1024} KB)")
    print(f"{'='*60}")
    t0 = time.perf_counter()
    result = process_tender_pdf(pdf_path, fname)
    elapsed = time.perf_counter() - t0
    print(f"  Extracted in {elapsed:.1f}s  |  {result.total_pages} pages  |  {len(result.rules)} rules\n")

    for r in result.rules:
        if r.value is not None and r.value > 0:
            # Format monetary values in Indian style
            v = r.value
            if v >= 1e7:
                formatted = f"Rs. {v/1e7:.2f} Crore"
            elif v >= 1e5:
                formatted = f"Rs. {v/1e5:.2f} Lakh"
            elif v >= 1e3:
                formatted = f"Rs. {v/1e3:.2f} Thousand"
            else:
                formatted = f"{v} {r.unit}"
            print(f"  {r.label:45s}  >= {formatted}  (conf={r.confidence})  [{r.source_section}]")
        else:
            print(f"  {r.label:45s}  {r.operator.value} {r.string_value or '(present)'}  [{r.source_section}]")
