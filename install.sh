#!/bin/bash
# Installation script for Meal Helper Assistant

echo "🍽️ Meal Helper Assistant - Installation"
echo "========================================"
echo

# Check if virtualenv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtualenv
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip -q

# Install core dependencies
echo "Installing core dependencies..."
pip install -q pydantic pydantic-settings python-dotenv pyyaml

# Install LangChain
echo "Installing LangChain..."
pip install -q langchain langchain-core langchain-community

# Install LLM providers
echo "Installing LLM providers..."
pip install -q langchain-anthropic anthropic
pip install -q langchain-openai openai

# Install utilities
echo "Installing utilities..."
pip install -q requests beautifulsoup4 pypdf markdownify playwright

# Install CLI
echo "Installing CLI tools..."
pip install -q typer rich

echo
echo "✅ Installation complete!"
echo
echo "Next steps:"
echo "1. Configure API keys:"
echo "   cp .env.example .env"
echo "   nano .env"
echo
echo "2. Run the agent:"
echo "   source .venv/bin/activate"
echo "   python run.py chat --profile example_user"
echo
echo "3. Test imports:"
echo "   python test_imports.py"
