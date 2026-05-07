"""PostgreSQL-backed storage for TenderIQ.

Drop-in replacement for the old flat-file JSON store.
All routers call these functions unchanged — only the underlying
persistence layer has moved from disk JSON to PostgreSQL via SQLAlchemy.
"""
from typing import Optional

from sqlalchemy import select, delete

from backend.database import AsyncSessionLocal
from backend.db_models import TenderTable, BidderTable, ReportTable


# ── internal helper ──────────────────────────────────────────────────────────

def _to_dict(row) -> dict:
    """Convert any ORM row to a plain dict (compatible with old JSON format)."""
    return {col.name: getattr(row, col.name) for col in row.__table__.columns}


def _col_names(model) -> set:
    """Return the set of column names for a given ORM model class."""
    return {col.name for col in model.__table__.columns}


# ── Tender ───────────────────────────────────────────────────────────────────

async def save_tender(tender_dict: dict) -> None:
    """Insert or update a tender row (upsert by primary key)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            existing = await session.get(TenderTable, tender_dict["tender_id"])
            if existing:
                # Update every column that appears in the dict
                for col in TenderTable.__table__.columns:
                    if col.name in tender_dict:
                        setattr(existing, col.name, tender_dict[col.name])
            else:
                cols = _col_names(TenderTable)
                row = TenderTable(**{k: v for k, v in tender_dict.items() if k in cols})
                session.add(row)


async def load_tender() -> Optional[dict]:
    """Return the most recently uploaded tender, or None."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TenderTable).order_by(TenderTable.uploaded_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_dict(row) if row else None


async def delete_tender() -> None:
    """Remove all tender rows (start-fresh operation)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(TenderTable))


# ── Bidders ──────────────────────────────────────────────────────────────────

async def save_bidder(bidder_id: str, bidder_dict: dict) -> None:
    """Insert or update a bidder row."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            existing = await session.get(BidderTable, bidder_id)
            if existing:
                for col in BidderTable.__table__.columns:
                    if col.name in bidder_dict:
                        setattr(existing, col.name, bidder_dict[col.name])
            else:
                cols = _col_names(BidderTable)
                row = BidderTable(**{k: v for k, v in bidder_dict.items() if k in cols})
                session.add(row)


async def load_bidder(bidder_id: str) -> Optional[dict]:
    """Return a single bidder by ID, or None."""
    async with AsyncSessionLocal() as session:
        row = await session.get(BidderTable, bidder_id)
        return _to_dict(row) if row else None


async def list_bidders() -> list[dict]:
    """Return all bidders ordered by upload time."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BidderTable).order_by(BidderTable.uploaded_at)
        )
        return [_to_dict(r) for r in result.scalars().all()]


async def delete_bidder(bidder_id: str) -> None:
    """Delete a single bidder by ID."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            row = await session.get(BidderTable, bidder_id)
            if row:
                await session.delete(row)


async def clear_bidders() -> None:
    """Delete all bidders (bulk reset)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(BidderTable))


# ── Reports ──────────────────────────────────────────────────────────────────

async def save_report(report_id: str, report_dict: dict) -> None:
    """Insert or update an evaluation report row."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            existing = await session.get(ReportTable, report_id)
            if existing:
                for col in ReportTable.__table__.columns:
                    if col.name in report_dict:
                        setattr(existing, col.name, report_dict[col.name])
            else:
                cols = _col_names(ReportTable)
                row = ReportTable(**{k: v for k, v in report_dict.items() if k in cols})
                session.add(row)


async def load_report(report_id: str) -> Optional[dict]:
    """Return a single report by ID, or None."""
    async with AsyncSessionLocal() as session:
        row = await session.get(ReportTable, report_id)
        return _to_dict(row) if row else None


async def load_latest_report() -> Optional[dict]:
    """Return the most recently generated report, or None."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ReportTable).order_by(ReportTable.generated_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_dict(row) if row else None
