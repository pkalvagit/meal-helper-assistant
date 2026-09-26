# Evaluation Framework Setup Guide

## ✅ What's Been Created

Your comprehensive evaluation framework is now ready! Here's what has been built:

### 📁 File Structure

```
evals/
├── eval_config.yaml              # ⚙️ Configuration for all 6 evaluations
├── golden_dataset.json           # 📊 20 test cases (edge cases + common scenarios)
├── eval_runner.py                # 🚀 Main orchestrator with parallel execution
├── test_framework.py             # 🧪 Framework verification script
├── judges/
│   ├── __init__.py
│   ├── base_judge.py            # Base class for all judges
│   ├── dietary_safety_judge.py  # ⚠️ CRITICAL: Allergen detection
│   ├── ground_truth_judge.py    # ✓ Menu item verification
│   ├── relevance_judge.py       # 🎯 Budget + goal alignment
│   └── location_judge.py        # 📍 Geographic accuracy
├── metrics/
│   ├── __init__.py
│   ├── latency_metric.py        # ⏱️ P50, P95, P99 latency
│   └── token_metric.py          # 💰 Token usage + cost
└── results/                      # 📁 Output directory (auto-created)
```

## 🎯 Evaluation Dimensions

### 1. **Latency** (No LLM)
- Metrics: P50, P95, P99, mean, max
- Programmatic calculation using numpy
- Thresholds: P50 < 5s, P95 < 10s

### 2. **Token Usage** (No LLM)
- Tracks: input/output/total tokens, cost per query
- Uses llm_factory for cost calculation
- Threshold: < $0.10 per query

### 3. **Geo Location** (Hybrid)
- Programmatic distance calculation (Haversine formula)
- Optional LLM verification with gpt-5.4-nano
- Critical threshold: within 10 miles

### 4. **Ground Truth** (LLM Judge)
- Model: gpt-5.4-mini
- Verifies recommended items exist in restaurant
- Checks price accuracy, description reasonableness
- Score 1-5, min passing: 4

### 5. **Dietary Safety** (LLM Judge) ⚠️ CRITICAL
- Model: gpt-5.4-mini at temperature=0.0
- Conservative: flags uncertain items as unsafe
- Checks allergens & dietary restrictions
- **MUST score 5/5 to pass** (perfect score only)
- Fail-fast on violations

### 6. **Relevance** (LLM Judge)
- Model: gpt-5.4-mini
- Weighted scoring:
  - Budget adherence: 30%
  - Query intent match: 30%
  - Goal alignment: 30%
  - Variety: 10%
- Score 1-5, min passing: 3

## 🔑 Prerequisites

### 1. Install Dependencies

All dependencies are already in requirements.txt:

```bash
pip install -r requirements.txt
```

Key packages:
- `langchain`, `langchain-openai`, `langchain-anthropic` (LLM support)
- `pydantic` (data validation)
- `rich` (beautiful console output)
- `numpy` (latency statistics)
- `pyyaml` (config parsing)

### 2. Set API Keys

```bash
# For OpenAI judges (recommended - cheaper)
export OPENAI_API_KEY="your-openai-key"

# OR for Claude judges
export ANTHROPIC_API_KEY="your-anthropic-key"

# Optional: for production agent testing
export GOOGLE_PLACES_API_KEY="your-places-key"
```

### 3. Configure LLM Provider (Optional)

Edit `config/llm_config.yaml` to switch providers:

```yaml
# Use OpenAI (default in eval_config.yaml)
provider: "openai"
model: "gpt-5.4-mini"

# OR use Claude
provider: "claude"
model: "claude-haiku-4-5"
```

## 🚀 Quick Start

### Step 1: Verify Framework (No API Key Needed)

```bash
# Check structure and configuration
python -c "
import yaml, json
from pathlib import Path

config = yaml.safe_load(open('evals/eval_config.yaml'))
dataset = json.load(open('evals/golden_dataset.json'))

print(f'✓ Evaluations: {len(config[\"evaluations\"])}')
print(f'✓ Test cases: {len(dataset[\"test_cases\"])}')
print(f'✓ Judges: {list(config[\"evaluations\"].keys())}')
"
```

### Step 2: Run Full Evaluation

```bash
# Set API key first
export OPENAI_API_KEY="sk-..."

# Run all 20 test cases with parallel judges
python evals/eval_runner.py
```

**Expected output:**
```
🧪 Starting Meal Helper Evaluation Suite

Total test cases: 20
Enabled judges: dietary_safety, ground_truth, relevance, geo_location

Running test: Simple pizza query (test_001)
  [dietary_safety] Score: 5.0/5.0 - ✅ PASS
  [ground_truth] Score: 4.5/5.0 - ✅ PASS
  [relevance] Score: 4.2/5.0 - ✅ PASS
  [geo_location] Score: 5.0/5.0 - ✅ PASS

...

📊 EVALUATION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Tests: 20
Passed: 18
Failed: 2
Pass Rate: 90.0%

Latency: P50: 2.3s, P95: 4.8s
Tokens: 45,000 tokens, $0.08

✅ EVALUATION PASSED
```

### Step 3: View Results

```bash
# Results saved to: evals/results/eval_results_20240926_103000.json
cat evals/results/eval_results_*.json | jq '.summary'
```

## 🔧 Integration with Your Agent

### Current State: Mock Agent

Right now, `eval_runner.py` uses a simulated agent (`_simulate_agent_result()`) that returns mock recommendations. This is just for testing the eval framework.

### Replace with Real Agent

Edit `evals/eval_runner.py`, line ~104:

```python
def run_agent_on_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run actual meal helper agent."""
    from core.agent import MealHelperAgent
    from core.models import UserProfile
    
    # Create agent with user profile
    user_profile = UserProfile(**test_case["user_profile"])
    agent = MealHelperAgent(user_profile=user_profile)
    
    # Run query
    result = agent.chat(test_case["query"])
    
    # Return in expected format
    return {
        "success": result.success,
        "recommendations": result.recommendations,
        "metadata": result.metadata
    }
```

**Important**: Ensure your agent returns:
- `recommendations`: List of items with `name`, `price`, `restaurant`, `description`
- `metadata`: Dict with `model`, `tokens` (for tracking)

## ⚙️ Configuration

### Customize eval_config.yaml

**Enable/Disable Evaluations:**
```yaml
evaluations:
  dietary_safety:
    enabled: true  # Set to false to skip
```

**Change LLM Model:**
```yaml
evaluations:
  dietary_safety:
    llm_model: "claude-haiku-4-5"  # Switch to Haiku for cost
    provider: "claude"
```

**Adjust Thresholds:**
```yaml
evaluations:
  relevance:
    thresholds:
      min_score: 4  # Raise bar to 4/5 instead of 3/5
```

**Modify Scoring Weights:**
```yaml
evaluations:
  relevance:
    scoring:
      weights:
        budget_adherence: 0.4  # Increase budget importance
        query_intent_match: 0.3
        goal_alignment: 0.2
        variety: 0.1
```

### Customize Prompts

Edit the `judge_prompts` section in `eval_config.yaml`:

```yaml
judge_prompts:
  dietary_safety: |
    CRITICAL SAFETY EVALUATION
    
    [Your custom prompt here...]
```

## 📊 Golden Dataset

### Current Test Cases (20)

The dataset covers:
- **Simple queries**: Pizza, burgers, sushi
- **Allergen scenarios**: Peanuts, shellfish, gluten, dairy, soy, eggs
- **Diet restrictions**: Vegan, vegetarian, keto, paleo, halal, kosher
- **Budget constraints**: $8 to $30 per meal
- **Location variety**: Major US cities
- **Complex cases**: Multiple allergens + diet + budget + nutrition goals

### Add Your Own Test Cases

Edit `evals/golden_dataset.json`:

```json
{
  "id": "test_021",
  "name": "Your custom test",
  "query": "Spicy ramen near me",
  "user_profile": {
    "name": "Test User",
    "allergies": ["sesame"],
    "dietary_restrictions": [],
    "budget": {"max_per_meal": 18.0},
    "location": {"lat": 40.7589, "lng": -73.9851, "radius": 5000}
  },
  "expected_behavior": {
    "should_find_results": true,
    "dietary_safety_score": 5,
    "must_avoid_allergens": ["sesame", "sesame oil"]
  },
  "ground_truth": {
    "safe_items": ["Miso Ramen", "Tonkotsu Ramen"],
    "unsafe_items": ["Tantanmen (contains sesame)"]
  }
}
```

## 💰 Cost Estimates

### Per Test Case
- Dietary Safety: ~$0.002 (gpt-5.4-mini)
- Ground Truth: ~$0.002
- Relevance: ~$0.003
- Location (with LLM): ~$0.001 (gpt-5.4-nano)
- **Total per test**: ~$0.008

### Full Run (20 tests)
- **Total cost**: ~$0.16
- With parallelization: ~2-3 minutes runtime

### Monthly (daily runs)
- $0.16 × 30 days = **$4.80/month**

**Cost Optimization:**
- Use Claude Haiku for cheaper judges: ~$0.003/test
- Disable location LLM verification: save $0.001/test
- Run on subset for quick checks: 5 tests = $0.04

## 🎨 Customization Examples

### Example 1: Add New Judge

Create `evals/judges/nutrition_judge.py`:

```python
from .base_judge import BaseJudge

class NutritionJudge(BaseJudge):
    def build_prompt(self, test_case, result):
        return f"Evaluate nutrition: {result}"
    
    def parse_response(self, response):
        return self.extract_json_from_response(response)
    
    def calculate_score(self, parsed):
        return float(parsed.get("score", 3))
```

Add to `eval_config.yaml`:
```yaml
evaluations:
  nutrition:
    enabled: true
    llm_required: true
    llm_model: "gpt-5.4-mini"
```

Register in `eval_runner.py`:
```python
judge_map = {
    "nutrition": NutritionJudge,
    # ...existing judges
}
```

### Example 2: Non-LLM Metric

Create `evals/metrics/price_accuracy_metric.py`:

```python
class PriceAccuracyMetric:
    def record(self, expected_price, actual_price):
        self.errors.append(abs(expected_price - actual_price))
    
    def calculate_metrics(self):
        return {
            "mean_absolute_error": np.mean(self.errors),
            "max_error": np.max(self.errors)
        }
```

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'rich'"
```bash
pip install rich numpy pyyaml
```

### "Missing API key"
```bash
export OPENAI_API_KEY="sk-..."
# OR
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "JSON parse error from LLM"
- Check the judge's prompt in `eval_config.yaml`
- Ensure it asks for JSON response
- The framework has fallback JSON extraction

### Results not showing
- Check `evals/results/` directory
- View with: `cat evals/results/eval_results_*.json | jq`

## 📈 Next Steps

1. **Set API key** and run first evaluation
2. **Integrate real agent** (replace mock in eval_runner.py)
3. **Tune thresholds** based on initial results
4. **Add custom test cases** for your specific scenarios
5. **Set up CI/CD** to run evals on every commit
6. **Track over time** - compare results across runs
7. **Add custom judges** for domain-specific requirements

## 🎓 Learn More

- **Parallel execution**: Uses `ThreadPoolExecutor` for concurrent judge evaluation
- **LLM factory**: Reuses your existing `core/llm_factory.py` for model selection
- **Pydantic validation**: All results are type-safe with `JudgeResult` model
- **JSON output**: Structured format for analysis, dashboards, CI/CD integration

## 📞 Support

For questions or issues:
1. Check `evals/README_NEW.md` for detailed documentation
2. Review example test cases in `golden_dataset.json`
3. Inspect judge implementation in `evals/judges/`

---

**Built for**: Meal Helper Assistant
**Version**: 1.0
**Last Updated**: 2024-09-26
