@echo off
echo ====================================
echo AllLegal - Windows Setup
echo ====================================

echo.
echo [1/4] Creating virtual environment...
python -m venv venv

echo.
echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/4] Installing backend dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [4/4] Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo.
echo ====================================
echo Setup Complete
echo ====================================
echo.
echo Next Steps:
echo 1. Copy .env.example to .env and fill in the credentials
echo 2. Start a local OpenSearch: docker compose up -d
echo 3. Run backend: python main.py
echo 4. Run frontend: cd frontend ^&^& npm run dev
echo.
pause
