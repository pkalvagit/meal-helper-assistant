# 🚀 Meal Helper Assistant - Quick Reference

## Installation & Setup

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant

# 1. Install
pip install -r requirements.txt

# 2. Configure keys
cp .env.example .env
nano .env  # Add your API keys

# 3. Run
python run.py chat --profile example_user
```

---

## Key Commands

```bash
# Interactive chat
python run.py chat --profile example_user

# Single query
python run.py chat -q "Find Italian restaurants near me"

# List profiles
python run.py list-profiles

# Test guardrails
python run.py test-guardrails "Tell me a joke"

# Run evaluations
python run.py run-evals
```

---

## Switching LLMs (Fully Flexible!)

Edit `config/llm_config.yaml` - Mix and match providers!

**Claude:**
```yaml
primary:
  provider: "claude"
  claude:
    model: "claude-opus-5"  # or claude-sonnet-5, claude-haiku-4-5

guardrail:
  provider: "claude"
  claude:
    model: "claude-haiku-4-5"
```

**OpenAI:**
```yaml
primary:
  provider: "openai"
  openai:
    model: "gpt-4o"  # or gpt-4o-mini, gpt-4-turbo, gpt-5.4-mini, gpt-5.4-nano

guardrail:
  provider: "openai"
  openai:
    model: "gpt-5.4-nano"  # Ultra-cheap guardrail!
```

**Mixed (Best Cost/Quality):**
```yaml
primary:
  provider: "claude"      # Best quality
  claude:
    model: "claude-opus-5"

guardrail:
  provider: "openai"      # Cheapest guardrail
  openai:
    model: "gpt-5.4-nano"  # 20x cheaper than Claude Haiku!
```

**See `config/PROVIDER_EXAMPLES.md` for more combinations!**

---

## Example Queries

```
✅ "Find Italian restaurants near me"
✅ "I want high protein lunch under $15"
✅ "Show me vegan options"
✅ "What has the most protein?"

❌ "Tell me a joke" → Rejected by guardrail
❌ "What's the weather?" → Rejected by guardrail
```

---

## Architecture Flow

```
User Query
    ↓
Guardrail Check (Haiku/GPT-4o-mini) - $0.0001
    ├─ Off-topic? → ❌ Reject
    └─ Valid? → ✅ Continue
         ↓
LangChain Agent (Opus/GPT-4o) - $0.02-0.10
    ├─ search_restaurants(lat, lng)
    ├─ check_menu_cache(restaurant_url)
    ├─ filter_by_user_profile(items, allergies)
    └─ rank_by_preferences(items)
         ↓
Response with Recommendations
```

---

## Safety Guarantees

### Allergen Filtering (100% Required)
```python
# User profile
allergies: ["peanuts", "shellfish"]

# Filter ALWAYS runs
filter_menu_by_user_profile(
    items=menu_items,
    allergies=user.allergies,  # ← NEVER skipped
    dietary_restrictions=user.restrictions,
    max_price=user.budget
)

# Result: ZERO items with allergens
```

**Eval Result:** ✅ 100% pass rate required

---

## Cost Breakdown

| Component | Model | Cost per Query |
|-----------|-------|----------------|
| Guardrail | Claude Haiku | $0.0001 |
| Intent | Claude Haiku | $0.005 |
| Agent | Claude Opus | $0.02-0.10 |
| **Total** | | **$0.02-0.12** |

**Optimization:**
- Menu cache hit: $0.02 (no fetch)
- Menu cache miss: $0.12 (fetch + extract)

---

## User Profiles

Located in `config/user_profiles.json`:

```json
{
  "example_user": {
    "name": "John Doe",
    "allergies": ["peanuts", "shellfish"],
    "dietary_restrictions": ["no_beef", "no_pork"],
    "preferences": {
      "high_protein": true,
      "vegetarian_options": true
    },
    "budget": {
      "max_per_meal": 15.00
    },
    "location": {
      "default_lat": 38.9586,
      "default_lng": -77.3570,
      "default_radius": 5000
    }
  }
}
```

**Add new profiles** by editing this file.

---

## Evaluation Suite

```bash
python run.py run-evals
```

**Tests:**
1. **Guardrails** - Topic classification (95% accuracy)
2. **Safety** - Allergen filtering (100% required)
3. **Intent** - Query understanding (90% accuracy)

**Success Criteria:**
- Safety tests: 100% pass
- Overall: ≥80% pass rate

---

## File Locations

```
Config:           config/llm_config.yaml
User Profiles:    config/user_profiles.json
Menu Cache:       cache/menus/*.json
Test Cases:       evals/test_cases.json
API Keys:         .env
```

---

## Troubleshooting

### "No module named 'anthropic'"
```bash
pip install -r requirements.txt
```

### "ANTHROPIC_API_KEY not set"
```bash
cp .env.example .env
# Edit .env and add your key
```

### "ModuleNotFoundError: No module named 'core'"
```bash
# Run from project root:
cd /home/pkalva/my-experiments/meal-helper-assistant
python run.py chat
```

### Guardrail rejecting valid queries
Check `config/llm_config.yaml` - guardrail model might be too strict.
Try using Claude Haiku or GPT-4o-mini.

### High costs
- Increase menu cache hits
- Use Haiku for guardrails
- Use Sonnet instead of Opus for main agent (edit config)

---

## LangChain vs Native Claude API

**Why LangChain was chosen:**
- ✅ Built-in tool calling
- ✅ Conversation memory
- ✅ Easy LLM switching
- ✅ Rich ecosystem (future: RAG, vector stores)
- ✅ LangSmith tracing (optional)

**Trade-offs:**
- ❌ Abstraction overhead
- ❌ Framework dependency
- ❌ Harder to debug than native API

**Alternative:** See `/home/pkalva/my-experiments/test-menus` for native Claude API approach (no LangChain).

---

## Next Steps

1. **Add more user profiles** in `config/user_profiles.json`
2. **Tune LLM config** for cost/quality balance
3. **Add more test cases** in `evals/test_cases.json`
4. **Connect menu pipeline** - Integrate `finalize_menu.py` for real menu fetching
5. **Add RAG** - Vector search over menu descriptions (future)

---

## Key Differences from test-menus/

| Feature | test-menus/ | meal-helper-assistant/ |
|---------|-------------|------------------------|
| Framework | Native Claude API | LangChain |
| Focus | Menu extraction pipeline | Conversational agent |
| LLM Support | Claude only | Claude + OpenAI |
| Guardrails | Prompt-based | Separate classifier |
| Memory | Manual | LangChain built-in |
| Evals | Manual scripts | Structured framework |
| Use Case | Batch menu extraction | Interactive recommendations |

---

## Support & Documentation

- **Main README**: `README.md`
- **This file**: Quick reference
- **Usage examples**: `USAGE.md`
- **Test cases**: `evals/test_cases.json`
- **LangChain docs**: https://python.langchain.com/docs/

---

**Built with:**
- LangChain 0.3+
- Claude API (Anthropic)
- OpenAI API
- Google Places API
- Rich CLI (terminal UI)
- Pydantic (data validation)
