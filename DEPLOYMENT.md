# TenderIQ Deployment Guide

This guide covers deploying TenderIQ using Docker and Render.

## Prerequisites

- Docker and Docker Compose installed
- Git installed
- GitHub account
- Render account (free tier available)

## Local Docker Testing

### 1. Create Environment File

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Database
DB_PASSWORD=your_secure_password

# Optional: AI API Keys
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_google_key

# Thresholds
CONFIDENCE_THRESHOLD=0.75
BORDERLINE_MARGIN=0.05
```

### 2. Build and Run with Docker Compose

```bash
# Build all services
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

Access the application:
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 3. Verify Deployment

```bash
# Check service status
docker-compose ps

# Test backend health
curl http://localhost:8000/api/health

# View backend logs
docker-compose logs backend

# View frontend logs
docker-compose logs frontend
```

## GitHub Setup

### 1. Initialize Git Repository

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: TenderIQ with Docker support"
```

### 2. Push to GitHub

```bash
# Add remote (replace with your repo URL)
git remote add origin https://github.com/PiyushGupta1590/TenderIQ.git

# Push to main branch
git branch -M main
git push -u origin main
```

## Render Deployment

### Option 1: Using Render Blueprint (Recommended)

1. **Connect GitHub Repository**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New" → "Blueprint"
   - Connect your GitHub account
   - Select the `TenderIQ` repository
   - Render will automatically detect `render.yaml`

2. **Configure Environment Variables**
   - Render will create services based on `render.yaml`
   - Add optional environment variables in Render dashboard:
     - `GROQ_API_KEY` (for LLM features)
     - `GOOGLE_API_KEY` (for Gemini AI)

3. **Deploy**
   - Click "Apply" to deploy all services
   - Wait for deployment to complete (5-10 minutes)

### Option 2: Manual Deployment

#### A. Create PostgreSQL Database

1. Go to Render Dashboard → "New" → "PostgreSQL"
2. Configure:
   - Name: `tenderiq-db`
   - Database: `tenderiq`
   - User: `postgres`
   - Region: Oregon (or closest to you)
   - Plan: Free
3. Click "Create Database"
4. Copy the **Internal Database URL** (starts with `postgresql://`)

#### B. Deploy Backend

1. Go to Render Dashboard → "New" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - Name: `tenderiq-backend`
   - Environment: Docker
   - Region: Oregon
   - Branch: main
   - Dockerfile Path: `backend/Dockerfile`
   - Plan: Free
4. Add Environment Variables:
   ```
   DATABASE_URL=<paste internal database URL>
   TESSERACT_PATH=/usr/bin/tesseract
   OCR_ENGINE=tesseract
   AI_PROVIDER=none
   CONFIDENCE_THRESHOLD=0.75
   BORDERLINE_MARGIN=0.05
   DATA_DIR=/data
   ```
5. Add Disk:
   - Name: `tenderiq-data`
   - Mount Path: `/app/data`
   - Size: 1 GB
6. Click "Create Web Service"

#### C. Deploy Frontend

1. Go to Render Dashboard → "New" → "Static Site"
2. Connect your GitHub repository
3. Configure:
   - Name: `tenderiq-frontend`
   - Environment: Docker
   - Region: Oregon
   - Branch: main
   - Dockerfile Path: `frontend/Dockerfile`
   - Plan: Free
4. Add Environment Variable:
   ```
   VITE_API_URL=https://tenderiq-backend.onrender.com/api
   ```
   (Replace with your actual backend URL)
5. Click "Create Static Site"

### Post-Deployment Configuration

1. **Update CORS Settings**
   - Once frontend is deployed, note its URL
   - Update `backend/main.py` CORS origins:
   ```python
   allow_origins=[
       "http://localhost:5173",
       "https://your-frontend-url.onrender.com"
   ]
   ```
   - Commit and push changes

2. **Test the Deployment**
   - Visit your frontend URL
   - Upload a tender document
   - Verify all stages work correctly

## Monitoring and Maintenance

### View Logs

```bash
# Render Dashboard → Select Service → Logs tab

# Local Docker
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Update Deployment

```bash
# Make changes locally
git add .
git commit -m "Your changes"
git push origin main

# Render will automatically redeploy
```

### Database Backup

```bash
# From Render Dashboard
# PostgreSQL service → Backups tab → Create Backup
```

## Troubleshooting

### Backend Won't Start

1. Check DATABASE_URL is correct
2. Verify Tesseract is installed in container
3. Check logs: `docker-compose logs backend`

### Frontend Can't Connect to Backend

1. Verify VITE_API_URL environment variable
2. Check CORS settings in backend
3. Ensure backend is running and healthy

### Database Connection Issues

1. Verify DATABASE_URL format: `postgresql+asyncpg://user:pass@host:port/db`
2. Check database is running: `docker-compose ps`
3. Test connection: `docker-compose exec backend python -c "from backend.database import engine; print('OK')"`

### File Upload Issues

1. Check disk space: `docker-compose exec backend df -h`
2. Verify data directory permissions
3. Check upload size limits in nginx config

## Performance Optimization

### For Production

1. **Increase Resources**
   - Upgrade Render plan for better performance
   - Increase disk size if handling many documents

2. **Enable Caching**
   - Add Redis for session management
   - Cache OCR results

3. **Database Optimization**
   - Add indexes for frequently queried fields
   - Enable connection pooling

4. **CDN for Static Assets**
   - Use Cloudflare or similar CDN
   - Enable asset compression

## Security Checklist

- [ ] Change default database password
- [ ] Use environment variables for all secrets
- [ ] Enable HTTPS (Render provides this automatically)
- [ ] Restrict CORS to specific domains
- [ ] Regularly update dependencies
- [ ] Monitor logs for suspicious activity
- [ ] Implement rate limiting for API endpoints
- [ ] Regular database backups

## Cost Estimation

### Render Free Tier
- PostgreSQL: 1 GB storage, 90 days retention
- Web Services: 750 hours/month (enough for 1 service)
- Static Sites: 100 GB bandwidth/month

### Paid Plans (if needed)
- Starter: $7/month per service
- Standard: $25/month per service
- Includes more resources and 24/7 uptime

## Support

For issues:
1. Check logs first
2. Review this guide
3. Check GitHub Issues
4. Contact: [Your Contact Info]
