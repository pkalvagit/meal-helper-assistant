# Installation Guide - Evaluation Framework

## Updated Dependencies

The evaluation framework requires a few additional packages that have been added to the project.

### New Dependencies Added

| Package | Version | Purpose | Location |
|---------|---------|---------|----------|
| `numpy` | >=1.24 | Latency statistics (P50, P95, P99) | requirements.txt |
| `rich` | >=13.0 | Already in project | requirements.txt |
| `pydantic` | >=2.0 | Already in project | requirements.txt |
| `pyyaml` | >=6.0 | Already in project | requirements.txt |
| `pytest` | >=7.4 | Already in project | requirements.txt |
| `pytest-asyncio` | >=0.21 | Already in project | requirements.txt |

### What Was Updated

✅ **requirements.txt** - Added `numpy>=1.24` in the data processing section

✅ **install.sh** - Added two new installation steps:
- Data processing libraries (numpy, pandas)
- Evaluation dependencies (pytest, pytest-asyncio)

## Installation Methods

### Method 1: Using install.sh (Recommended)

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant
chmod +x install.sh
./install.sh
```

This will:
1. Create/activate virtual environment
2. Install all dependencies including evaluation packages
3. Set up everything needed for the eval framework

### Method 2: Using requirements.txt

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant
pip install -r requirements.txt
```

### Method 3: Manual Installation (Eval packages only)

If you already have the project installed and just need eval packages:

```bash
pip install numpy>=1.24 rich pydantic pyyaml pytest pytest-asyncio
```

## Verification

After installation, verify everything is working:

```bash
python -c "
import numpy
import rich
import pydantic
import yaml
import pytest
print('✓ All evaluation dependencies installed successfully')
print(f'  numpy: {numpy.__version__}')
print(f'  rich: {rich.__version__}')
print(f'  pydantic: {pydantic.__version__}')
"
```

## Next Steps

After installation:

1. **Set API Keys**:
   ```bash
   export OPENAI_API_KEY="your-key"
   # OR
   export ANTHROPIC_API_KEY="your-key"
   ```

2. **Run Evaluation**:
   ```bash
   python evals/eval_runner.py
   ```

3. **View Results**:
   ```bash
   ls evals/results/
   ```

## Troubleshooting

### "ModuleNotFoundError: No module named 'numpy'"

```bash
pip install numpy
```

### "ModuleNotFoundError: No module named 'rich'"

```bash
pip install rich
```

### Virtual Environment Issues

If using a virtual environment, make sure it's activated:

```bash
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows
```

### Install Script Permissions

If install.sh won't run:

```bash
chmod +x install.sh
./install.sh
```

## What Gets Installed

### Core Dependencies (already in project)
- LangChain ecosystem (langchain, langchain-core, langchain-community)
- LLM providers (langchain-anthropic, langchain-openai, anthropic, openai)
- Web scraping (requests, beautifulsoup4, playwright)
- Configuration (pydantic, pyyaml, python-dotenv)

### Evaluation-Specific (new)
- **numpy** - Statistical calculations for latency metrics
- **rich** - Beautiful console output (already in project for CLI)
- **pytest** - Testing framework (already in project)

### Total Installation Size

Approximate additional disk space for new packages:
- numpy: ~15 MB
- (rich, pydantic, pytest already installed)

**Total additional**: ~15 MB

## Dependencies Summary

```
Evaluation Framework Dependencies:
├── numpy (new)          → Latency statistics
├── rich (existing)      → Console output
├── pydantic (existing)  → Data validation
├── pyyaml (existing)    → Config parsing
└── pytest (existing)    → Testing

LLM Integration (uses existing):
├── langchain-core
├── langchain-anthropic
└── langchain-openai
```

---

**Note**: All packages are already compatible with your existing project dependencies. No conflicts expected.
