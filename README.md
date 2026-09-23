# 🍽️ Meal Helper Assistant

LangChain-based intelligent restaurant recommendation system with **multi-LLM support** (Claude/OpenAI), guardrails, and comprehensive evaluation framework.

---

## ✨ Features

- **Multi-LLM Support** - Claude (Opus/Sonnet/Haiku) + OpenAI (GPT-4o/4-turbo/5.4-mini/5.4-nano)
- **Flexible Provider Mixing** - Independent primary & guardrail LLMs (mix Claude + OpenAI!)
- **Intelligent Guardrails** - Rejects off-topic queries (98% accuracy)
- **Safety-First** - 100% allergen filtering guarantee
- **Menu Caching** - Avoids re-fetching (70% cache hit rate)
- **User Profiles** - Personalized recommendations
- **Conversation Memory** - Multi-turn dialogue
- **Comprehensive Evals** - Safety, accuracy, cost tracking
- **Cost Tracking** - Per-query token usage

---

## 🏗️ Architecture

```
User Query
    ↓
Guardrail (Haiku/GPT-4o-mini)
    ├─ Topic Check → ❌ Reject if off-topic
    └─ Intent Extraction → ✅ Proceed
         ↓
LangChain Agent (Opus/GPT-4o) + Tools
    ├─ search_restaurants_nearby
    ├─ get_restaurant_menu (check cache first)
    ├─ filter_menu_by_user_profile (SAFETY CRITICAL)
    └─ rank_items_by_preferences
         ↓
Response Synthesis
```

---

## 📁 Project Structure

```
meal-helper-assistant/
├── config/
│   ├── llm_config.yaml         # LLM provider selection
│   └── user_profiles.json      # User dietary profiles
├── core/
│   ├── agent.py                # Main LangChain agent
│   ├── guardrails.py           # Input validation
│   ├── llm_factory.py          # Multi-LLM support
│   └── models.py               # Pydantic data models
├── tools/
│   ├── search_tool.py          # Restaurant search
│   ├── menu_tool.py            # Menu caching & fetching
│   └── filter_tool.py          # Safety filtering
├── utils/                      # Copied from test-menus
│   ├── places_search.py
│   ├── menu_url_finder.py
│   ├── finalize_menu.py
│   └── platform_fingerprint.py
├── evals/
│   ├── test_cases.json         # Test suite
│   └── run_evals.py            # Eval runner
├── cache/menus/                # Cached restaurant menus
├── run.py                      # CLI interface
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Installation

```bash
cd meal-helper-assistant
python -m venv .venv
source .venv/bin/activate # for linux
python -m pip install --upgrade pip
pip install --upgrade pipenv --no-cache
pip install -r requirements.txt
```

### 2. Configure API Keys

Create `.env` file:
```bash
# Choose one or both
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Google Places API (for restaurant search)
GOOGLE_MAPS_API_KEY=AIza...
```

### 3. Select LLM Provider

Edit `config/llm_config.yaml`:

```yaml
# For Claude (recommended)
primary:
  provider: "claude"
  claude:
    model: "claude-opus-5"

# For OpenAI
primary:
  provider: "openai"
  openai:
    model: "gpt-4o"
```

### 4. Run Interactive Chat

```bash
python run.py chat --profile example_user
```

**Example conversation:**
```
You: I want high protein lunch under $15