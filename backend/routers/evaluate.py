"""Evaluate router — Stage 3"""
from fastapi import APIRouter, HTTPException, Body
from backend.services.evaluation_engine import evaluate_all
from backend.models.tender import TenderRuleSet
from backend.models.bidder import BidderData
from backend.models.evaluation import Verdict
from backend.storage.file_store import (
    load_tender, list_bidders, save_report, load_latest_report
)

router = APIRouter(prefix="/api/evaluate", tags=["Evaluation"])


@router.post("/run")
async def run_evaluation():
    """Run evaluation of all bidders against approved tender rules."""
    tender_data = await load_tender()
    if not tender_data:
        raise HTTPException(400, "No tender found.")
    if not tender_data.get("approved"):
        raise HTTPException(400, "Tender rules must be approved first.")

    bidder_list = await list_bidders()
    if not bidder_list:
        raise HTTPException(400, "No bidder documents uploaded.")

    ruleset = TenderRuleSet(**tender_data)
    bidders = [BidderData(**b) for b in bidder_list]

    report = evaluate_all(ruleset, bidders)
    await save_report(report.report_id, report.model_dump())
    return report.model_dump()


@router.get("/latest")
async def get_latest_report():
    data = await load_latest_report()
    if not data:
        raise HTTPException(404, "No evaluation run yet.")
    return data


@router.post("/override/{report_id}/{bidder_id}")
async def officer_override(
    report_id: str,
    bidder_id: str,
    override: dict = Body(...),
):
    """Officer overrides a bidder's verdict."""
    from backend.storage.file_store import load_report, save_report
    data = await load_report(report_id)
    if not data:
        raise HTTPException(404, "Report not found.")

    verdict_str = override.get("verdict", "")
    note = override.get("note", "")
    try:
        verdict = Verdict(verdict_str)
    except ValueError:
        raise HTTPException(400, f"Invalid verdict: {verdict_str}")

    for br in data["bidder_results"]:
        if br["bidder_id"] == bidder_id:
            br["officer_override"] = verdict.value
            br["officer_override_note"] = note
            br["overall_verdict"] = verdict.value
            await save_report(report_id, data)
            return {"status": "overridden", "new_verdict": verdict.value}

    raise HTTPException(404, "Bidder not found in report.")


@router.post("/finalize/{report_id}")
async def finalize_report(report_id: str):
    from backend.storage.file_store import load_report, save_report
    from datetime import datetime, timezone
    data = await load_report(report_id)
    if not data:
        raise HTTPException(404, "Report not found.")
    data["finalized"] = True
    data["finalized_at"] = datetime.now(timezone.utc).isoformat()
    await save_report(report_id, data)
    return {"status": "finalized"}
