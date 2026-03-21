#!/bin/bash
# AllLegal API - Linux/macOS Setup

echo "===================================="
echo "AllLegal API - Setup"
echo "===================================="

echo ""
echo "[1/5] Creating virtual environment..."
python3 -m venv venv

echo ""
echo "[2/5] Activating virtual environment..."
source venv/bin/activate

echo ""
echo "[3/5] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[4/5] Creating required directories..."
mkdir -p logs
mkdir -p uploads

echo ""
echo "===================================="
echo "✅ Setup Complete!"
echo "===================================="
echo ""
echo "📋 Next Steps:"
echo "1. Update .env with Supabase credentials"
echo "2. Start services: docker-compose up"
echo "3. Run app: uvicorn main:app --reload"
echo "4. Visit: http://localhost:8000/docs"
echo ""
