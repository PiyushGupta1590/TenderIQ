"""TenderIQ FastAPI Application Entry Point"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import tender, bidder, evaluate, report
from backend.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run DB table creation on startup; clean up engine on shutdown."""
    await init_db()
    yield
    # engine disposal is handled automatically by SQLAlchemy


app = FastAPI(
    title="TenderIQ API",
    description="AI-assisted tender evaluation system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration - supports both local development and production
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000", 
    "http://127.0.0.1:5173",
    "http://localhost",
    "http://localhost:80",
]

# Add production frontend URL from environment variable
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tender.router)
app.include_router(bidder.router)
app.include_router(evaluate.router)
app.include_router(report.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/")
async def root():
    return {"message": "TenderIQ API — visit http://localhost:5173 for the UI"}
