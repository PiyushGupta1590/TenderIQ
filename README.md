# TenderIQ — AI Bid Evaluation System

> AI-assisted government tender evaluation: reads rules, processes bidder documents, makes explainable eligibility decisions.

[![Live Demo](https://img.shields.io/badge/demo-live-success)](https://tenderiq-6a07.onrender.com)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 🌟 Features

- **Intelligent Document Processing**: Extracts tender rules and bidder information from PDFs using OCR and NLP
- **Automated Evaluation**: Compares bidder qualifications against tender requirements
- **Explainable AI**: Provides detailed reasoning for each eligibility decision
- **Manual Override**: Allows reviewers to override AI decisions with justification
- **PDF Report Generation**: Creates comprehensive evaluation reports
- **RESTful API**: Well-documented API with Swagger/OpenAPI support
- **Dockerized**: Easy deployment with Docker and Docker Compose

---

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

**Or manually:**
```bash
docker-compose up -d
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
  ```bash
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

## 📖 Manual Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Tesseract OCR (optional, for scanned images):
  ```bash
  winget install UB-Mannheim.TesseractOCR
  ```

### Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
python create_db.py

# Start backend server
python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Access the application at http://localhost:5173

---

## 🎯 4-Stage Workflow

| Stage | What you do | What AI does |
|---|---|---|
| **1. Upload Tender** | Upload tender document PDF | Extracts eligibility rules into a checklist |
| **2. Approve Rules** | Review and approve each rule | Validates rule structure |
| **3. Upload Bidders** | Upload bidder PDFs with company names | OCR + field extraction from documents |
| **4. Run Evaluation** | Click "Run AI Evaluation" | Compares bidder data vs tender rules |
| **5. View Report** | Review decisions, override if needed | Provides detailed explanations |

### Example Workflow

1. **Stage 1:** Upload a tender document
   - System extracts eligibility criteria
   - Review extracted rules
   - Approve or edit rules

2. **Stage 2:** Add bidders
   - Enter company name
   - Upload bidder documents (PDF)
   - System extracts company information
   - Confirm extracted data

3. **Stage 3:** Run evaluation
   - Click "Run AI Evaluation"
   - System evaluates all bidders
   - Wait for processing (1-2 minutes)

4. **Stage 4:** View results
   - Review eligibility decisions
   - See detailed explanations
   - Override decisions if needed
   - Download PDF report

---

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Database (Required)
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/tenderiq

# OCR Configuration
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_ENGINE=tesseract

# AI Provider (Optional)
AI_PROVIDER=none
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key

# Evaluation Thresholds
CONFIDENCE_THRESHOLD=0.75   # Below this = MANUAL_REVIEW
BORDERLINE_MARGIN=0.05      # 5% within limit = MANUAL_REVIEW
LLM_HIGH_CONF=0.85
LLM_MED_CONF=0.60

# Storage
DATA_DIR=data
```

---

## 📚 API Documentation

### Interactive API Docs
Visit `http://localhost:8000/docs` for full Swagger UI with interactive testing.

### Key Endpoints

**Health Check:**
```
GET /api/health
```

**Tender Management:**
```
POST /api/tender/upload          # Upload tender document
GET  /api/tender/rules            # Get extracted rules
PUT  /api/tender/rules/{id}       # Update a rule
POST /api/tender/approve-all      # Approve all rules
DELETE /api/tender/               # Reset tender data
```

**Bidder Management:**
```
POST /api/bidder/upload           # Upload bidder documents
GET  /api/bidder/list             # List all bidders
GET  /api/bidder/{id}             # Get bidder details
POST /api/bidder/{id}/confirm     # Confirm bidder data
DELETE /api/bidder/{id}           # Remove bidder
```

**Evaluation:**
```
POST /api/evaluate/run            # Run evaluation
GET  /api/evaluate/latest         # Get latest results
POST /api/evaluate/override       # Override a decision
POST /api/evaluate/finalize       # Finalize report
```

**Reports:**
```
GET  /api/report/latest           # Get latest report
GET  /api/report/{id}             # Get specific report
GET  /api/report/{id}/pdf         # Download PDF report
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      TenderIQ System                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Frontend   │─────▶│   Backend    │─────▶│PostgreSQL │ │
│  │ React + Vite │      │   FastAPI    │      │ Database  │ │
│  │   Port 5173  │      │  Port 8000   │      │           │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│                              │                               │
│                              ▼                               │
│                    ┌──────────────────┐                     │
│                    │    Services      │                     │
│                    ├──────────────────┤                     │
│                    │ TenderProcessor  │                     │
│                    │ BidderProcessor  │                     │
│                    │ EvaluationEngine │                     │
│                    │ ReportGenerator  │                     │
│                    │ OCR Engine       │                     │
│                    │ LLM Extractor    │                     │
│                    └──────────────────┘                     │
│                              │                               │
│                              ▼                               │
│                    ┌──────────────────┐                     │
│                    │  File Storage    │                     │
│                    │  data/uploads/   │                     │
│                    │  data/bidders/   │                     │
│                    │  data/reports/   │                     │
│                    └──────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- FastAPI (Python web framework)
- SQLAlchemy (ORM with async support)
- PostgreSQL (Database)
- Tesseract OCR (Text extraction)
- pdfplumber (PDF processing)
- OpenCV (Image processing)
- FPDF2 (PDF generation)

**Frontend:**
- React 18 (UI framework)
- Vite (Build tool)
- Axios (HTTP client)
- Framer Motion (Animations)
- React Router (Navigation)

**DevOps:**
- Docker & Docker Compose
- Nginx (Frontend serving)
- Render (Cloud deployment)

---

## 📁 Project Structure

```
TenderIQ/
├── backend/                    # FastAPI backend
│   ├── models/                # Database models
│   │   ├── tender.py          # Tender and rules models
│   │   ├── bidder.py          # Bidder models
│   │   └── evaluation.py     # Evaluation models
│   ├── routers/               # API endpoints
│   │   ├── tender.py          # Tender routes
│   │   ├── bidder.py          # Bidder routes
│   │   ├── evaluate.py        # Evaluation routes
│   │   └── report.py          # Report routes
│   ├── services/              # Business logic
│   │   ├── tender_processor.py      # Tender extraction
│   │   ├── bidder_processor.py      # Bidder extraction
│   │   ├── evaluation_engine.py     # Evaluation logic
│   │   ├── report_generator.py      # PDF generation
│   │   ├── ocr_engine.py            # OCR processing
│   │   ├── llm_extractor.py         # LLM extraction
│   │   └── hybrid_extractor.py      # Hybrid approach
│   ├── storage/               # File storage
│   ├── tests/                 # Unit tests
│   ├── config.py              # Configuration
│   ├── database.py            # Database setup
│   ├── main.py                # Application entry
│   └── Dockerfile             # Backend Docker config
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── pages/            # UI pages
│   │   │   ├── Stage1.jsx    # Tender upload
│   │   │   ├── Stage2.jsx    # Bidder upload
│   │   │   ├── Stage3.jsx    # Evaluation
│   │   │   └── Stage4.jsx    # Results
│   │   ├── api/              # API client
│   │   ├── App.jsx           # Main app
│   │   └── main.jsx          # Entry point
│   ├── Dockerfile            # Frontend Docker config
│   ├── nginx.conf            # Nginx configuration
│   └── package.json          # Dependencies
├── data/                     # Data storage
│   ├── uploads/              # Uploaded files
│   ├── bidders/              # Bidder data
│   └── reports/              # Generated reports
├── docker-compose.yml        # Docker orchestration
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template
├── README.md                 # This file
└── DEPLOYMENT.md             # Deployment guide
```

---

## 🧪 Testing

### Run Tests
```bash
# Backend tests
python -m pytest backend/tests/

# Test specific module
python test_tender_rules.py
python test_monetary.py
python test_all_pdfs.py
```

### Manual Testing
1. Start the application
2. Upload test documents from `data/uploads/`
3. Verify extraction accuracy
4. Test evaluation logic
5. Check report generation

---

## 🔧 Troubleshooting

### Docker Issues

**Problem:** Docker build fails
- **Solution:** Ensure Docker Desktop is running
- Check Docker has enough resources (4GB RAM minimum)
- Try: `docker-compose build --no-cache`

**Problem:** Port already in use
- **Solution:** Stop services using ports 80, 8000, or 5432
- Or change ports in `docker-compose.yml`

### Database Issues

**Problem:** Database connection error
- **Solution:** Check DATABASE_URL format in .env
- Ensure PostgreSQL is running
- Verify credentials are correct
- Format: `postgresql+asyncpg://user:pass@host:port/db`

### OCR Issues

**Problem:** Tesseract not found
- **Solution:** Install Tesseract OCR
- Windows: `winget install UB-Mannheim.TesseractOCR`
- Update TESSERACT_PATH in .env

### Frontend Issues

**Problem:** Cannot connect to backend
- **Solution:** Verify backend is running on port 8000
- Check VITE_API_URL configuration
- Check browser console for CORS errors
- Ensure FRONTEND_URL is set in backend

---

## 🚀 Deployment

### Render (Recommended)

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete instructions.

**Quick Steps:**
1. Push code to GitHub
2. Create PostgreSQL database on Render
3. Deploy backend as Web Service (Docker)
4. Deploy frontend as Static Site
5. Configure environment variables
6. Update CORS settings

**Live Demo:** https://tenderiq-6a07.onrender.com

### Other Platforms

The application can be deployed on:
- AWS (ECS, Elastic Beanstalk)
- Google Cloud (Cloud Run, App Engine)
- Azure (Container Instances, App Service)
- DigitalOcean (App Platform)
- Heroku

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

- **Piyush Gupta** - [GitHub](https://github.com/PiyushGupta1590)

---

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- React team for the UI library
- Tesseract OCR for text extraction
- Render for hosting platform
- All open-source contributors

---

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/PiyushGupta1590/TenderIQ/issues)
- Check the [DEPLOYMENT.md](DEPLOYMENT.md) guide
- Review the API documentation at `/docs`

---

## 🔗 Links

- **Live Demo:** https://tenderiq-6a07.onrender.com
- **API Documentation:** https://tenderiq-6a07.onrender.com/docs
- **GitHub Repository:** https://github.com/PiyushGupta1590/TenderIQ

---

**Built with ❤️ for transparent and efficient government procurement**
