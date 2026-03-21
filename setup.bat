@echo off
echo ====================================
echo AllLegal API - Windows Setup
echo ====================================

echo.
echo [1/5] Creating virtual environment...
python -m venv venv

echo.
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/5] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [4/5] Creating required directories...
if not exist "logs" mkdir logs
if not exist "uploads" mkdir uploads

echo.
echo ====================================
echo ✅ Setup Complete!
echo ====================================
echo.
echo 📋 Next Steps:
echo 1. Update .env with Supabase credentials
echo 2. Start services: docker-compose up
echo 3. Activate: venv\Scripts\activate.bat
echo 4. Run app: uvicorn main:app --reload
echo 5. Visit: http://localhost:8000/docs
echo.
echo 📚 Features:
echo   - GET /api/search (hardcoded mock data)
echo   - POST /api/auth/login (Supabase auth)
echo   - POST /api/auth/signup (Supabase auth)
echo   - GET /health (health check)
echo.
pause
