#!/bin/bash
# Convenience script to run evaluations

echo "🧪 Meal Helper Assistant - Evaluation Runner"
echo "=============================================="
echo

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo
    echo "Please create .env file with your API keys:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    echo
    echo "Required keys:"
    echo "  - OPENAI_API_KEY (for OpenAI LLM judges)"
    echo "  - OR ANTHROPIC_API_KEY (for Claude LLM judges)"
    exit 1
fi

# Check if API keys are set
if ! grep -q "OPENAI_API_KEY=sk-" .env && ! grep -q "ANTHROPIC_API_KEY=sk-ant-" .env; then
    echo "⚠️  Warning: No valid API keys found in .env file"
    echo
    echo "Please set at least one API key in .env:"
    echo "  OPENAI_API_KEY=sk-your-key-here"
    echo "  OR"
    echo "  ANTHROPIC_API_KEY=sk-ant-your-key-here"
    echo
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✓ Environment file loaded"
echo

# Check if numpy is installed
python -c "import numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Error: numpy not installed"
    echo
    echo "Please install dependencies:"
    echo "  pip install -r requirements.txt"
    echo "  OR"
    echo "  pip install numpy"
    exit 1
fi

echo "✓ Dependencies verified"
echo

# Run evaluation
echo "Starting evaluation..."
echo
python evals/eval_runner.py "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo
    echo "✅ Evaluation complete!"
    echo
    echo "Results saved to: evals/results/"
    echo "View with: cat evals/results/eval_results_*.json | jq '.summary'"
else
    echo
    echo "❌ Evaluation failed with exit code: $exit_code"
    echo
    echo "Common issues:"
    echo "  - Missing API keys in .env"
    echo "  - Invalid API key"
    echo "  - Network connectivity issues"
    echo "  - Missing dependencies (run: pip install -r requirements.txt)"
fi

exit $exit_code
