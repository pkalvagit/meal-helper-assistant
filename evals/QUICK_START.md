# Quick Start - Evaluation Framework

## ✅ What You Have

A complete evaluation system with **parallel LLM judges** for your Meal Helper Assistant!

### 6 Evaluation Dimensions

1. **Latency** (P50, P95 scores) - No LLM
2. **Token Usage** (cost tracking) - No LLM  
3. **Geo Location Accuracy** (distance validation) - Hybrid
4. **Ground Truth** (menu items exist) - LLM Judge
5. **Dietary Safety** ⚠️ CRITICAL (allergen detection) - LLM Judge
6. **Relevance** (budget + goal alignment) - LLM Judge

### Golden Dataset
- **20 test cases** covering common queries, edge cases, and safety-critical scenarios
- Includes: allergens, diet restrictions, budget constraints, location variations

## 🚀 Run Your First Evaluation

### Step 1: Set API Key

```bash
export OPENAI_API_KEY="your-key-here"
# OR
export ANTHROPIC_API_KEY="your-key-here"
```

### Step 2: Run Evaluation

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant
python evals/eval_runner.py
```

That's it! Results save to `evals/results/eval_results_TIMESTAMP.json`

## 📊 Example Output

```
🧪 Starting Meal Helper Evaluation Suite

Total test cases: 20
Enabled judges: dietary_safety, ground_truth, relevance, geo_location

Running test: Simple pizza query (test_001)
  [dietary_safety] Score: 5.0/5.0 - ✅ PASS
  [ground_truth] Score: 4.5/5.0 - ✅ PASS
  [relevance] Score: 4.2/5.0 - ✅ PASS
  [geo_location] Score: 5.0/5.0 - ✅ PASS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 EVALUATION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall Results:
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Metric            ┃ Value  ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Total Tests       │ 20     │
│ Passed            │ 18     │
│ Failed            │ 2      │
│ Pass Rate         │ 90.0%  │
│ Critical Failures │ 0      │
└───────────────────┴────────┘

Judge Performance:
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Judge           ┃ Mean Score┃ Range    ┃ Pass Rate ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ dietary_safety  │ 4.9/5.0   │ 4.5-5.0  │ 95.0%     │
│ ground_truth    │ 4.3/5.0   │ 3.2-5.0  │ 85.0%     │
│ relevance       │ 4.1/5.0   │ 3.0-4.8  │ 80.0%     │
│ geo_location    │ 4.8/5.0   │ 4.0-5.0  │ 100%      │
└─────────────────┴───────────┴──────────┴───────────┘

Latency: P50: 2.3s, P95: 4.8s (max P50: 5s, max P95: 10s)
Tokens: 45000 tokens, $0.08 (max: 50000 tokens, $0.10)

✅ EVALUATION PASSED
```

## 📁 Key Files

```
evals/
├── eval_config.yaml       # Configure all settings
├── golden_dataset.json    # Add/edit test cases
├── eval_runner.py         # Main runner (integrate your agent here)
└── results/               # JSON outputs
```

## 🔧 Integration Steps

### Replace Mock Agent with Real Agent

Edit `evals/eval_runner.py` around line 104:

```python
def run_agent_on_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run your actual agent."""
    from core.agent import MealHelperAgent
    from core.models import UserProfile
    
    # Create agent
    profile = UserProfile(**test_case["user_profile"])
    agent = MealHelperAgent(user_profile=profile)
    
    # Run query
    result = agent.chat(test_case["query"])
    
    return {
        "success": result.success,
        "recommendations": result.recommendations,
        "metadata": result.metadata  # Include tokens, model
    }
```

## ⚙️ Configuration

### Change LLM Model

Edit `evals/eval_config.yaml`:

```yaml
evaluations:
  dietary_safety:
    llm_model: "claude-haiku-4-5"  # Cheaper option
    provider: "claude"
```

### Adjust Thresholds

```yaml
evaluations:
  relevance:
    thresholds:
      min_score: 4  # Raise bar
```

### Add Test Cases

Edit `evals/golden_dataset.json`:

```json
{
  "id": "test_021",
  "name": "Your test",
  "query": "Sushi with no fish",
  "user_profile": {
    "allergies": ["fish"],
    "budget": {"max_per_meal": 25.0}
  }
}
```

## 💰 Cost

- **Per test**: ~$0.008 (using gpt-5.4-mini)
- **20 tests**: ~$0.16 per run
- **Monthly** (daily runs): ~$4.80

**Faster/Cheaper:**
- Use Claude Haiku: ~$0.003/test
- Run on subset: 5 tests = $0.04

## 📚 Documentation

- **SETUP_GUIDE.md** - Detailed setup and customization
- **README_NEW.md** - Complete framework documentation
- **eval_config.yaml** - All configuration options inline

## 🎯 Next Actions

1. ✅ Set API key: `export OPENAI_API_KEY="..."`
2. ✅ Run first eval: `python evals/eval_runner.py`
3. ⏳ Integrate real agent (edit `eval_runner.py`)
4. ⏳ Review results in `evals/results/`
5. ⏳ Tune thresholds based on your needs
6. ⏳ Add custom test cases

## ❓ Questions?

Check these in order:
1. `SETUP_GUIDE.md` - Comprehensive setup
2. `README_NEW.md` - Full documentation
3. `eval_config.yaml` - Configuration examples
4. Judge implementations in `evals/judges/`

---

**Built**: Parallel LLM judges with configurable settings
**Cost**: ~$0.16 per full run (20 tests)
**Time**: 2-3 minutes with parallel execution
**Critical**: Dietary safety judge uses temperature=0.0 for safety
