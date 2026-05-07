# TenderIQ — AI Bid Evaluation System

> AI-assisted government tender evaluation: reads rules, processes bidder documents, makes explainable eligibility decisions.

## 🚀 Quick Start

### Option 1: Docker (Recommended)

**Windows:**
```bash
.\docker-start.bat
```

**Linux/Mac:**
```bash
chmod +x docker-start.sh
./docker-start.sh
```

Then open **http://localhost**

### Option 2: Manual Setup (Windows)

```bash
# Double-click run.bat  OR run in terminal:
.\run.bat
```

Then open **http://localhost:5173**

---

## 📋 Prerequisites

### Docker Setup (Recommended)
- Docker Desktop installed
- 4GB RAM minimum
- 2GB free disk space

### Manual Setup
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Tesseract OCR (optional, for scanned images):
  ```
  winget install UB-Mannheim.TesseractOCR
  ```

---

## 🐳 Docker Deployment

### Local Development

1. **Clone and Configure**
   ```bash
   git clone https://github.com/PiyushGupta1590/TenderIQ.git
   cd TenderIQ
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Start Services**
   ```bash
   docker-compose up -d
   ```

3. **Access Application**
   - Frontend: http://localhost
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

4. **View Logs**
   ```bash
   docker-compose logs -f
   ```

5. **Stop Services**
   ```bash
   docker-compose down
   ```

### Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions on deploying to Render, AWS, or other cloud platforms.

---

## Manual Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Tesseract OCR (optional, for scanned images):
  ```
  winget install UB-Mannheim.TesseractOCR
  ```

### Backend
```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 4-Stage Workflow

| Stage | What you do | What AI does |
|---|---|---|
| **1. Upload Tender** | Upload `CRPF_TenderEval_Phase1_Solution.pdf` | Extracts rules into a checklist |
| **2. Approve Rules** | Review each rule, click Approve | — |
| **3. Upload Bidders** | Upload bidder PDFs with company name | OCR + field extraction |
| **4. Run Evaluation** | Click "Run AI Evaluation" | Compares rules vs bidder data |
| **5. View Report** | Review decisions, override if needed | Provides full explanations |

---

## Demo with Included PDF

The file `CRPF_TenderEval_Phase1_Solution.pdf` is pre-loaded for testing:

1. Go to Stage 1 → Upload that PDF
2. Review the extracted eligibility rules
3. Click "Confirm All Rules"
4. Go to Stage 2 → Add bidder (use any company name + upload a PDF)
5. Stage 3 → Run Evaluation
6. Stage 4 → View & download report

---

## Configuration (`.env`)

Copy `.env.example` → `.env` to customise:

```
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
CONFIDENCE_THRESHOLD=0.75   # below this = MANUAL_REVIEW
BORDERLINE_MARGIN=0.05      # 5% within limit = MANUAL_REVIEW
```

---

## API Documentation
Visit `http://localhost:8000/docs` for full Swagger UI.

## Architecture
```
Frontend (React/Vite :5173)
    ↕ REST API
Backend (FastAPI :8000)
    ↕
Services: TenderProcessor | BidderProcessor | EvaluationEngine | ReportGenerator
    ↕
Storage: data/tender.json | data/bidders/*.json | data/reports/*.json
```
