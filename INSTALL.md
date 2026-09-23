# 🚀 Installation Guide - Meal Helper Assistant

## Quick Install (Recommended)

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant

# Run install script
./install.sh

# Activate virtualenv
source .venv/bin/activate

# Test imports
python test_imports.py

# Configure keys (see below)
cp .env.example .env
nano .env

# Run!
python run.py chat --profile example_user
```

---

## Manual Install (Step by Step)

### 1. Create Virtual Environment

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant

python -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Core
pip install pydantic pydantic-settings python-dotenv pyyaml

# LangChain
pip install langchain langchain-core langchain-community

# LLM Providers
pip install langchain-anthropic anthropic
pip install langchain-openai openai

# Utilities
pip install requests beautifulsoup4

# CLI
pip install typer rich
```

### 3. Verify Installation

```bash
python test_imports.py
```

**You should see:**
```
Testing imports...
1. Core imports...
   ✓ Models
   ✓ LLM Factory
   ✓ Guardrails
   ✓ Simple Agent

2. Tool imports...
   ✓ Search tools
   ✓ Menu tools
   ✓ Filter tools

3. Testing factory...
   ✓ Factory created
   Primary provider: openai
   Guardrail provider: openai

✅ All imports successful!
```

---

## API Keys Setup

### 1. Copy Example Config

```bash
cp .env.example .env
```

### 2. Edit .env File

```bash
nano .env
```

**Add your keys:**
```bash
# Choose one or both LLM providers
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Required for restaurant search
GOOGLE_MAPS_API_KEY=your-google-api-key-here
```

### 3. Verify Keys

```bash
# Check file
cat .env

# Test (should not show "No API key" error)
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('OpenAI:', 'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'); print('Anthropic:', 'SET' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET')"
```

---

## First Run

### Test Guardrails

```bash
python run.py test-guardrails "Find Italian restaurants"
```

**Expected:**
```
┌─────────────── Guardrail Test ───────────────┐
│ Query: Find Italian restaurants              │
│ Valid: ✅                                    │
│ Reason: N/A                                  │
│ Intent: {...}                                │
│ Cost: $0.000050                              │
└──────────────────────────────────────────────┘
```

### Interactive Chat

```bash
python run.py chat --profile example_user
```

**Expected:**
```
[Guardrail] Using openai: gpt-5.4-nano
[Agent] Primary LLM: openai (gpt-5.4-mini)

┌─────────────────────────────────────────────┐
│ 🍽️ Meal Helper Assistant                   │
├─────────────────────────────────────────────┤
│ User: John Doe                              │
│ Allergies: peanuts, shellfish               │
│ Restrictions: no_beef, no_pork              │
│ Budget: $15/meal                            │
└─────────────────────────────────────────────┘

Type your questions or 'quit' to exit

You: _
```

---

## Troubleshooting

### ImportError: No module named 'X'

**Solution:**
```bash
source .venv/bin/activate
pip install X
```

### ImportError: attempted relative import

**Solution:** Already fixed! Make sure you have the latest code:
```bash
git pull  # if using git
# or check that core/simple_agent.py uses absolute imports
```

### ModuleNotFoundError: No module named 'pydantic'

**Solution:**
```bash
source .venv/bin/activate  # ← Make sure virtualenv is active!
pip install pydantic
```

### API Key Errors

**Check keys are loaded:**
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY', 'NOT SET')[:20])"
```

**Should show:** `sk-proj-...` (first 20 chars)

### "Provider 'openai' but no OPENAI_API_KEY"

**Options:**
1. Add `OPENAI_API_KEY` to `.env`
2. Or switch to Claude in `config/llm_config.yaml`:
   ```yaml
   primary:
     provider: "claude"
   guardrail:
     provider: "claude"
   ```

---

## Verification Checklist

Before running the agent, verify:

- [ ] Virtual environment created (`.venv/` exists)
- [ ] Virtual environment activated (`which python` shows `.venv`)
- [ ] Dependencies installed (`python test_imports.py` passes)
- [ ] API keys configured (`.env` file exists with keys)
- [ ] Config file exists (`config/llm_config.yaml`)
- [ ] User profiles exist (`config/user_profiles.json`)

**Run checklist:**
```bash
cd /home/pkalva/my-experiments/meal-helper-assistant

# 1. Check virtualenv
ls .venv/
which python  # Should show .venv path

# 2. Check imports
python test_imports.py

# 3. Check config
cat config/llm_config.yaml | grep provider

# 4. Check keys
cat .env | grep API_KEY

# 5. Test guardrails
python run.py test-guardrails "test query"

# 6. Run agent
python run.py chat --profile example_user
```

---

## Common Issues & Solutions

### Issue: `python: command not found`

**Solution:**
```bash
python3 --version
# Use python3 instead of python
alias python=python3
```

### Issue: `Permission denied: ./install.sh`

**Solution:**
```bash
chmod +x install.sh
./install.sh
```

### Issue: Virtualenv not activating

**Solution:**
```bash
# Linux/Mac
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Verify
which python  # Should show .venv path
```

### Issue: Old dependencies causing conflicts

**Solution:**
```bash
# Remove and recreate virtualenv
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
./install.sh
```

---

## Next Steps After Installation

1. **List available profiles:**
   ```bash
   python run.py list-profiles
   ```

2. **Create your own profile:**
   Edit `config/user_profiles.json`

3. **Switch LLM providers:**
   Edit `config/llm_config.yaml`

4. **Run evaluations:**
   ```bash
   python run.py run-evals
   ```

5. **Read documentation:**
   - `README.md` - Main docs
   - `QUICK_REFERENCE.md` - Commands
   - `config/PROVIDER_EXAMPLES.md` - LLM configs

---

## Installation Complete! 🎉

**Test it:**
```bash
python run.py chat -q "Find high protein lunch under $15"
```

**Get help:**
```bash
python run.py --help
```
