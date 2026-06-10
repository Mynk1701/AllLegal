#!/bin/bash
# AllLegal - Linux/macOS Setup

echo "===================================="
echo "AllLegal - Setup"
echo "===================================="

echo ""
echo "[1/6] Creating virtual environment..."
python3 -m venv venv

echo ""
echo "[2/6] Activating virtual environment..."
source venv/bin/activate

echo ""
echo "[3/6] Installing backend dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[4/6] Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "[5/6] Creating required directories..."
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
echo "3. Run backend: python main.py"
echo "4. Run frontend: cd frontend && npm run dev"
echo ""
