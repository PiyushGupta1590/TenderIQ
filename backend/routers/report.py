"""Report router — Stage 4"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from backend.storage.file_store import load_report, load_latest_report
from backend.services.report_generator import generate_pdf_report
from backend.models.evaluation import EvaluationReport
from backend.config import DATA_DIR

router = APIRouter(prefix="/api/report", tags=["Report"])


@router.get("/latest")
async def get_latest():
    data = await load_latest_report()
    if not data:
        raise HTTPException(404, "No report available.")
    return data


@router.get("/{report_id}")
async def get_report(report_id: str):
    data = await load_report(report_id)
    if not data:
        raise HTTPException(404, "Report not found.")
    return data


@router.get("/{report_id}/pdf")
async def download_pdf(report_id: str):
    """Generate and download PDF report."""
    data = await load_report(report_id)
    if not data:
        raise HTTPException(404, "Report not found.")

    # Check if PDF already exists
    pdf_path = DATA_DIR / "reports" / f"{report_id}.pdf"
    if not pdf_path.exists():
        try:
            report = EvaluationReport(**data)
            generate_pdf_report(report)
        except Exception as e:
            raise HTTPException(500, f"PDF generation failed: {str(e)}")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"TenderIQ_Report_{report_id[:8]}.pdf",
    )
