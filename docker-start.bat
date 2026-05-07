@echo off
REM TenderIQ Docker Quick Start Script for Windows

echo Starting TenderIQ with Docker...

REM Check if .env exists
if not exist .env (
    echo No .env file found. Creating from .env.example...
    copy .env.example .env
    echo Created .env file. Please edit it with your configuration.
    echo Especially set DB_PASSWORD for security.
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker is not running. Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Build and start services
echo Building Docker images...
docker-compose build

echo Starting services...
docker-compose up -d

echo Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM Check service health
echo Checking service status...
docker-compose ps

echo.
echo TenderIQ is running!
echo.
echo Access points:
echo    Frontend:  http://localhost
echo    Backend:   http://localhost:8000
echo    API Docs:  http://localhost:8000/docs
echo.
echo Useful commands:
echo    View logs:        docker-compose logs -f
echo    Stop services:    docker-compose down
echo    Restart:          docker-compose restart
echo.
pause
