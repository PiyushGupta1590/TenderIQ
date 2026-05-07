"""Bidder router — Stage 2"""
import asyncio
import shutil
from functools import partial
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List

from backend.services.bidder_processor import process_bidder_files
from backend.storage.file_store import (
    save_bidder, load_bidder, list_bidders, delete_bidder, clear_bidders, load_tender
)
from backend.config import DATA_DIR

router = APIRouter(prefix="/api/bidder", tags=["Bidder"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp", ".docx", ".doc"}


@router.post("/upload")
async def upload_bidder(
    bidder_name: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """Upload bidder documents and process them with production-grade pipeline."""
    tender_data = await load_tender()
    if not tender_data:
        raise HTTPException(400, "Upload and approve a tender first.")
    if not tender_data.get("approved"):
        raise HTTPException(400, "Tender rules must be approved before uploading bidder documents.")

    tender_id = tender_data["tender_id"]
    saved_paths = []

    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {f.filename}")
        save_path = DATA_DIR / "uploads" / f.filename
        with open(save_path, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved_paths.append(str(save_path))

    try:
        # Run in a thread so we don't stall uvicorn's event loop.
        loop = asyncio.get_event_loop()
        bidder = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                partial(process_bidder_files, saved_paths, bidder_name, tender_id),
            ),
            timeout=600,  # 10-minute hard cap
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Bidder processing timed out (>10 min).")
    except Exception as e:
        raise HTTPException(500, f"Processing failed: {str(e)}")

    await save_bidder(bidder.bidder_id, bidder.model_dump())
    return bidder.model_dump()


@router.get("/list")
async def list_all_bidders():
    return await list_bidders()


@router.get("/{bidder_id}")
async def get_bidder(bidder_id: str):
    data = await load_bidder(bidder_id)
    if not data:
        raise HTTPException(404, "Bidder not found.")
    return data


@router.post("/{bidder_id}/confirm")
async def confirm_bidder(bidder_id: str):
    """Officer confirms extracted data is correct."""
    data = await load_bidder(bidder_id)
    if not data:
        raise HTTPException(404, "Bidder not found.")
    data["confirmed"] = True
    data["status"] = "complete"
    await save_bidder(bidder_id, data)
    return {"status": "confirmed"}


@router.delete("/{bidder_id}")
async def remove_bidder(bidder_id: str):
    await delete_bidder(bidder_id)
    return {"status": "deleted"}


@router.delete("/")
async def clear_all_bidders():
    await clear_bidders()
    return {"status": "cleared"}
