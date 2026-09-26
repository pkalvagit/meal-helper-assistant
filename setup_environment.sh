#!/bin/bash
# Complete environment setup including Playwright browsers

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Meal Helper Assistant - Environment Setup          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate
echo "✓ Activated"
echo ""

# Install Python packages
echo "📦 Installing Python packages from requirements.txt..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Python packages installed"
echo ""

# Install Playwright browsers (THIS IS THE MISSING STEP!)
echo "🌐 Installing Playwright browser binaries..."
echo "   (This downloads Chromium, Firefox, and WebKit)"
playwright install

if [ $? -eq 0 ]; then
    echo "✓ Playwright browsers installed"
else
    echo "❌ Playwright installation failed"
    echo ""
    echo "Try manually:"
    echo "  source .venv/bin/activate"
    echo "  playwright install"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║               ✅ Setup Complete!                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Installed browsers:"
playwright list 2>/dev/null | grep -E "chromium|firefox|webkit" || echo "  (Use 'playwright list' to verify)"
echo ""
echo "Next steps:"
echo "  1. Configure .env with your API keys"
echo "  2. Run: python run.py chat --profile example_user"
echo ""
