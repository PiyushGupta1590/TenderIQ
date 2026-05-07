"""Tender router — Stage 1"""
import asyncio
import os
import shutil
import uuid
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse

from backend.services.tender_processor import process_tender_pdf
from backend.storage.file_store import save_tender, load_tender, delete_tender
from backend.models.tender import TenderRuleSet, TenderRule, RuleCategory, RuleOperator
from backend.config import DATA_DIR

router = APIRouter(prefix="/api/tender", tags=["Tender"])


@router.post("/upload")
async def upload_tender(file: UploadFile = File(...)):
    """Upload tender PDF and extract rules."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported for tender upload.")

    # Ensure upload directory exists (first-run safety)
    upload_dir = DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Prefix with UUID to avoid collisions from concurrent uploads
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    upload_path = upload_dir / safe_name
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Run the blocking PDF processor in a thread-pool so we don't
        # stall uvicorn's event loop (large scanned PDFs can take 2+ min).
        # get_running_loop() is the correct API inside an async function
        # (get_event_loop() is deprecated in Python 3.10+).
        loop = asyncio.get_running_loop()
        ruleset = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                partial(process_tender_pdf, str(upload_path), file.filename),
            ),
            timeout=600,  # 10-minute hard cap
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "PDF processing timed out (>10 min). Try a smaller file.")
    except Exception as e:
        raise HTTPException(500, f"Failed to process PDF: {str(e)}")
    finally:
        # Clean up temp upload file regardless of success/failure
        try:
            upload_path.unlink(missing_ok=True)
        except Exception:
            pass

    await save_tender(ruleset.model_dump())
    return ruleset.model_dump()


@router.get("/rules")
async def get_rules():
    """Get current tender ruleset."""
    data = await load_tender()
    if not data:
        raise HTTPException(404, "No tender uploaded yet.")
    return data


@router.put("/rules/{rule_id}/approve")
async def approve_rule(rule_id: str):
    """Approve a single rule."""
    data = await load_tender()
    if not data:
        raise HTTPException(404, "No tender found.")
    for r in data["rules"]:
        if r["id"] == rule_id:
            r["approved"] = True
            await save_tender(data)
            return {"status": "approved", "rule_id": rule_id}
    raise HTTPException(404, f"Rule {rule_id} not found.")


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, updates: dict = Body(...)):
    """Update a rule (edit label, value, operator, notes, mandatory flag)."""
    data = await load_tender()
    if not data:
        raise HTTPException(404, "No tender found.")
    for r in data["rules"]:
        if r["id"] == rule_id:
            allowed = {"label", "value", "operator", "unit", "notes", "approved", "mandatory"}
            for k, v in updates.items():
                if k in allowed:
                    r[k] = v
            await save_tender(data)
            return r
    raise HTTPException(404, f"Rule {rule_id} not found.")


@router.post("/rules/add")
async def add_manual_rule(rule_data: dict = Body(...)):
    """
    Officer manually adds a rule not auto-extracted from the tender PDF.
    Required fields: label, field, category, operator
    Optional: value, unit, mandatory, notes
    """
    data = await load_tender()
    if not data:
        raise HTTPException(404, "No tender found. Upload a tender PDF first.")

    # Validate required fields
    required = {"label", "field", "category", "operator"}
    missing = required - set(rule_data.keys())
    if missing:
        raise HTTPException(400, f"Missing required fields: {missing}")

    # Validate enums
    try:
        cat = RuleCategory(rule_data["category"])
        op  = RuleOperator(rule_data["operator"])
    except ValueError as e:
        raise HTTPException(400, f"Invalid enum value: {e}")

    # Generate a new rule ID
    existing_ids = [r["id"] for r in data["rules"]]
    rule_num = len(existing_ids) + 1
    new_id = f"R{rule_num}"
    while new_id in existing_ids:
        rule_num += 1
        new_id = f"R{rule_num}"

    new_rule = TenderRule(
        id=new_id,
        category=cat,
        field=rule_data["field"],
        label=rule_data["label"],
        operator=op,
        value=rule_data.get("value"),
        unit=rule_data.get("unit"),
        string_value=rule_data.get("string_value"),
        source_text=rule_data.get("source_text", "Manually added by officer"),
        source_page=rule_data.get("source_page", 0),
        source_section=rule_data.get("source_section"),
        confidence=1.0,          # Officer-added = full confidence
        approved=True,            # Officer-added rules are auto-approved
        mandatory=rule_data.get("mandatory", True),
        is_manual=True,
        notes=rule_data.get("notes"),
    )

    data["rules"].append(new_rule.model_dump())
    await save_tender(data)
    return new_rule.model_dump()


@router.post("/rules/{rule_id}/delete")
async def delete_rule(rule_id: str):
    data = await load_tender()
    if not data:
        raise HTTPException(404, "No tender found.")
    data["rules"] = [r for r in data["rules"] if r["id"] != rule_id]
    await save_tender(data)
    return {"status": "deleted"}


@router.post("/approve-all")
async def approve_all_rules():
    """Approve all rules and mark tender as approved."""
    data = await load_tender()
    if not data:
        raise HTTPException(404, "No tender found.")
    for r in data["rules"]:
        r["approved"] = True
    data["approved"] = True
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    await save_tender(data)
    return {"status": "all_approved", "count": len(data["rules"])}


@router.post("/approve-mandatory")
async def approve_mandatory_only():
    """Approve only mandatory rules and mark tender as approved."""
    data = await load_tender()
    if not data:
        raise HTTPException(404, "No tender found.")
    count = 0
    for r in data["rules"]:
        if r.get("mandatory", True):
            r["approved"] = True
            count += 1
    data["approved"] = True
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    await save_tender(data)
    return {"status": "mandatory_approved", "count": count}


@router.delete("/")
async def reset_tender():
    """Delete current tender (start fresh)."""
    await delete_tender()
    return {"status": "deleted"}
