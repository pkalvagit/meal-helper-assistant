# Meal Helper Assistant - Evaluation Framework

Comprehensive evaluation system with parallel LLM judges for assessing meal recommendation quality.

## 🎯 Overview

This evaluation framework provides:

- **6 Evaluation Dimensions**: Latency, Token Usage, Geo Location, Ground Truth, Dietary Safety, Relevance
- **Parallel LLM Judges**: Multiple judges run concurrently for fast evaluation
- **Golden Dataset**: 20 carefully crafted test cases covering common and edge cases
- **Configurable**: YAML-based configuration for all evaluation settings
- **JSON Output**: Structured results for analysis and tracking

## 📂 Structure

```
evals/
├── eval_config.yaml          # Configuration for all evaluations
├── golden_dataset.json       # 20 test cases with expected behaviors
├── eval_runner.py            # Main evaluation orchestrator
├── judges/
│   ├── base_judge.py        # Base class for all judges
│   ├── dietary_safety_judge.py  # CRITICAL: allergen/restriction checking
│   ├── ground_truth_judge.py    # Verify menu items exist
│   ├── relevance_judge.py       # Budget and goal alignment
│   └── location_judge.py        # Geographic accuracy
├── metrics/
│   ├── latency_metric.py    # P50, P95, P99 latency tracking
│   └── token_metric.py      # Token usage and cost tracking
└── results/
    └── eval_results_*.json  # Timestamped results
```

## 🚀 Quick Start

### 1. Run Evaluation

```bash
cd evals
python eval_runner.py
```

### 2. View Results

Results are automatically saved to `results/eval_results_YYYYMMDD_HHMMSS.json`

Example output:
```json
{
  "meta": {
    "timestamp": "2024-09-26T10:30:00",
    "dataset": "meal_helper_golden_v1"
  },
  "test_results": [
    {
      "test_id": "test_001",
      "test_name": "Simple pizza query",
      "passed": true,
      "judge_results": {
        "dietary_safety": {
          "score": 5.0,
          "passed": true,
          "reasoning": "No allergens detected"
        },
        "relevance": {
          "score": 4.5,
          "passed": true
        }
      }
    }
  ],
  "summary": {
    "total_tests": 20,
    "passed": 18,
    "pass_rate": 90.0,
    "latency_metrics": {
      "p50": 2.3,
      "p95": 4.8
    }
  }
}
```

## 📊 Evaluation Dimensions

### 1. Latency (No LLM)
- **Metrics**: P50, P95, P99, mean, max
- **Thresholds**: P50 < 5s, P95 < 10s
- **Purpose**: Ensure fast response times

### 2. Token Usage (No LLM)
- **Metrics**: Total tokens, cost per query
- **Thresholds**: < 50k tokens, < $0.10 per query
- **Purpose**: Track API costs

### 3. Geo Location Accuracy
- **LLM**: Optional (programmatic + LLM verification)
- **Model**: gpt-5.4-nano (cheap, fast)
- **Score**: 1-5 based on distance accuracy
- **Critical**: Yes
- **Purpose**: Verify restaurants in correct location

### 4. Ground Truth (LLM Judge)
- **LLM**: Required
- **Model**: gpt-5.4-mini (good reasoning)
- **Score**: 1-5 based on menu item verification
- **Critical**: Yes
- **Purpose**: Ensure recommended items actually exist

### 5. Dietary Safety (LLM Judge) - CRITICAL
- **LLM**: Required
- **Model**: gpt-5.4-mini (accurate, fast)
- **Score**: 1-5 (must be 5 to pass)
- **Critical**: YES - Life-critical evaluation
- **Purpose**: Verify NO allergens or restricted foods present
- **Conservative**: Flags uncertain items as unsafe

### 6. Relevance (LLM Judge)
- **LLM**: Required
- **Model**: gpt-5.4-mini
- **Score**: 1-5 weighted across:
  - Budget adherence (30%)
  - Query intent match (30%)
  - Goal alignment (30%)
  - Variety (10%)
- **Critical**: No
- **Purpose**: Assess overall recommendation quality

## ⚙️ Configuration

### eval_config.yaml

```yaml
evaluations:
  dietary_safety:
    enabled: true
    llm_required: true
    llm_model: "gpt-5.4-mini"
    provider: "openai"
    temperature: 0.0  # Deterministic for safety
    thresholds:
      min_score: 5  # MUST be perfect
      critical: true
      fail_on_violation: true

  relevance:
    enabled: true
    llm_required: true
    llm_model: "gpt-5.4-mini"
    provider: "openai"
    scoring:
      weights:
        budget_adherence: 0.3
        query_intent_match: 0.3
        goal_alignment: 0.3
        variety: 0.1
```

### Customizing Judges

Edit `eval_config.yaml` to:
- Enable/disable evaluations
- Change LLM models (Haiku for cost, Opus for quality)
- Adjust thresholds
- Modify scoring weights
- Customize prompts in `judge_prompts` section

### Switching LLM Providers

```yaml
dietary_safety:
  provider: "claude"  # or "openai"
  llm_model: "claude-haiku-4-5"  # cheaper option
```

## 📝 Golden Dataset

### Structure

Each test case includes:
- **query**: User's input
- **user_profile**: Allergies, restrictions, budget, location
- **expected_behavior**: What should happen
- **ground_truth**: Known valid/invalid items

### Example Test Case

```json
{
  "id": "test_002",
  "name": "Allergen safety - peanuts",
  "query": "Thai food near me",
  "user_profile": {
    "allergies": ["peanuts"],
    "budget": {"max_per_meal": 20.0},
    "location": {"lat": 37.7749, "lng": -122.4194}
  },
  "expected_behavior": {
    "dietary_safety_score": 5,
    "must_avoid_allergens": ["peanuts", "peanut sauce"],
    "critical": true
  },
  "ground_truth": {
    "unsafe_items": ["Pad Thai with peanuts"],
    "safe_items": ["Green Curry (no peanuts)"]
  }
}
```

### Adding Test Cases

1. Edit `golden_dataset.json`
2. Add new test case following the structure above
3. Include edge cases, safety scenarios, and common queries
4. Re-run evaluations

## 🔧 Integration with Your Agent

### Replace Simulation with Real Agent

In `eval_runner.py`, update `run_agent_on_test()`:

```python
def run_agent_on_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run actual agent on test case."""
    from core.agent import MealHelperAgent
    from core.models import UserProfile

    # Create agent with user profile
    user_profile = UserProfile(**test_case["user_profile"])
    agent = MealHelperAgent(user_profile=user_profile)

    # Run agent
    result = agent.chat(test_case["query"])

    return {
        "success": result.success,
        "recommendations": result.recommendations,
        "metadata": {
            "model": "your-model",
            "tokens": {"input": 500, "output": 300, "total": 800}
        }
    }
```

## 📈 Interpreting Results

### Pass Criteria

- **Overall Pass**: 90%+ pass rate, no critical failures
- **Critical Dimensions**: Must score perfectly
  - Dietary Safety: 5/5 (no allergens)
  - Ground Truth: 4+/5 (items exist)
  - Geo Location: 4+/5 (correct area)

### Scoring Guide

- **5**: Perfect, no issues
- **4**: Minor issues, acceptable
- **3**: Notable problems, needs improvement
- **2**: Major issues, unacceptable
- **1**: Complete failure

### Common Issues

**Low Dietary Safety Score**
- Action: Review allergen detection logic
- Critical: YES - fix immediately

**Low Relevance Score**
- Action: Tune query understanding and filtering
- Critical: No - optimize over time

**High Latency**
- Action: Optimize API calls, caching
- Critical: No - but impacts UX

## 🔄 Parallel Execution

Judges run in parallel using `ThreadPoolExecutor`:

```python
# Default: 5 concurrent LLM calls
max_concurrent_llm_calls: 5
```

**Benefits**:
- 3-5x faster evaluation
- Efficient API usage
- Real-time progress tracking

**Cost Estimate** (per test case):
- Dietary Safety: ~$0.002
- Ground Truth: ~$0.002
- Relevance: ~$0.003
- Location (if LLM): ~$0.001
- **Total**: ~$0.008 per test case
- **20 tests**: ~$0.16 per run

## 🎨 Custom Judges

### Create Your Own Judge

```python
from evals.judges.base_judge import BaseJudge, JudgeResult

class MyCustomJudge(BaseJudge):
    def build_prompt(self, test_case, result):
        return f"Evaluate: {result}"

    def parse_response(self, response):
        return self.extract_json_from_response(response)

    def calculate_score(self, parsed):
        return float(parsed.get("score", 3))
```

### Register in eval_runner.py

```python
judge_map = {
    "my_custom_eval": MyCustomJudge,
    # ...
}
```

## 📊 Tracking Over Time

### Compare Runs

```bash
# Save baseline
python eval_runner.py  # saves to results/eval_results_baseline.json

# After changes
python eval_runner.py  # saves to results/eval_results_new.json

# Compare
python compare_results.py results/eval_results_baseline.json results/eval_results_new.json
```

### Regression Detection

Monitor these metrics:
- Pass rate shouldn't drop > 5%
- Critical eval scores must stay perfect
- Latency shouldn't increase > 20%
- Token usage shouldn't increase > 30%

## 🐛 Troubleshooting

### "No module named 'core'"

```bash
# Ensure you're in the project root
cd /home/pkalva/my-experiments/meal-helper-assistant
python evals/eval_runner.py
```

### LLM API Errors

Check your API keys:
```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

### JSON Parse Errors

LLM might return invalid JSON. The framework handles this with fallback parsing.

## 📚 Next Steps

1. **Run first evaluation**: `python eval_runner.py`
2. **Review results**: Check `results/` directory
3. **Integrate real agent**: Replace simulation in `eval_runner.py`
4. **Add more test cases**: Expand `golden_dataset.json`
5. **Tune thresholds**: Adjust `eval_config.yaml` based on results
6. **Set up CI/CD**: Run evals on every commit

## 🤝 Contributing

To add a new evaluation dimension:

1. Create judge in `judges/your_judge.py`
2. Add config in `eval_config.yaml`
3. Register in `eval_runner.py`
4. Add test cases to `golden_dataset.json`
5. Run and validate

---

**Questions?** Check the main project documentation or raise an issue.
