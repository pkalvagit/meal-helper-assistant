# How to Run Evaluations

## ✅ Prerequisites

1. **API Keys in .env file**
   ```bash
   # Check if .env exists
   ls -la .env
   
   # View your .env file (without exposing keys)
   grep "API_KEY" .env | sed 's/=.*/=***/'
   ```

2. **Dependencies installed**
   ```bash
   pip install -r requirements.txt
   ```

## 🚀 Running Evaluations

### Method 1: Using the convenience script (Recommended)

```bash
# From project root
./evals/run_eval.sh
```

This script will:
- ✅ Check for .env file
- ✅ Verify API keys are set
- ✅ Check dependencies
- ✅ Run evaluations
- ✅ Show results location

### Method 2: Direct Python execution

```bash
# From project root
python evals/eval_runner.py
```

### Method 3: From evals directory

```bash
cd evals
python eval_runner.py
```

## 🔑 API Key Setup

The evaluation script automatically loads API keys from `.env` file.

### Option 1: OpenAI (Recommended - Cheaper)

Edit `.env`:
```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

Cost per evaluation run (20 tests): ~$0.16

### Option 2: Claude/Anthropic

Edit `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

Then edit `evals/eval_config.yaml` to use Claude:
```yaml
evaluations:
  dietary_safety:
    provider: "claude"
    llm_model: "claude-haiku-4-5"
  
  ground_truth:
    provider: "claude"
    llm_model: "claude-haiku-4-5"
  
  relevance:
    provider: "claude"
    llm_model: "claude-sonnet-4"
```

### Option 3: Environment Variable (Alternative)

If you prefer not to use .env file:
```bash
export OPENAI_API_KEY="sk-your-key-here"
python evals/eval_runner.py
```

## 📊 Output

### Console Output

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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Tests: 20
Passed: 18
Pass Rate: 90.0%
```

### JSON Results

Results are automatically saved to:
```
evals/results/eval_results_YYYYMMDD_HHMMSS.json
```

View summary:
```bash
cat evals/results/eval_results_*.json | jq '.summary'
```

View full results:
```bash
cat evals/results/eval_results_*.json | jq '.'
```

## 🧪 Test Run (Framework Verification)

Before running full evaluation, test the framework:

```bash
python evals/test_framework.py
```

This will:
- ✅ Verify configuration loads
- ✅ Check dataset is valid
- ✅ Test each judge works
- ✅ Confirm dependencies

**Note**: Requires API keys to test LLM judges.

## 🔧 Troubleshooting

### Error: "Missing API key"

**Problem**: No API key found in .env

**Solution**:
```bash
# Create .env from example
cp .env.example .env

# Edit and add your key
nano .env  # or vim, code, etc.

# Add:
OPENAI_API_KEY=sk-your-actual-key-here
```

### Error: "ModuleNotFoundError: No module named 'dotenv'"

**Problem**: python-dotenv not installed

**Solution**:
```bash
pip install python-dotenv
# OR
pip install -r requirements.txt
```

### Error: "ModuleNotFoundError: No module named 'numpy'"

**Problem**: numpy not installed

**Solution**:
```bash
pip install numpy
# OR
pip install -r requirements.txt
```

### Error: "OpenAI API error: Invalid API key"

**Problem**: API key is invalid or incorrect

**Solution**:
1. Check your API key in .env file
2. Verify key is active on OpenAI dashboard
3. Make sure no extra spaces: `OPENAI_API_KEY=sk-...` (no spaces)

### Error: "Rate limit exceeded"

**Problem**: Too many API requests

**Solution**:
```bash
# Wait a minute and retry
# OR
# Reduce concurrent calls in eval_config.yaml:
execution:
  max_concurrent_llm_calls: 2  # Reduce from 5 to 2
```

### Evaluation runs but shows mock data

**Problem**: Real agent not integrated yet

**Solution**: The framework uses mock agent by default. To integrate your real agent, edit `evals/eval_runner.py` line ~110:

```python
def run_agent_on_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
    # TODO: Replace with real agent
    from core.agent import MealHelperAgent
    from core.models import UserProfile
    
    profile = UserProfile(**test_case["user_profile"])
    agent = MealHelperAgent(user_profile=profile)
    
    return {
        "success": True,
        "recommendations": agent.chat(test_case["query"]).recommendations,
        "metadata": {"model": "...", "tokens": {...}}
    }
```

## 📈 Understanding Results

### Score Interpretation

| Score | Meaning |
|-------|---------|
| 5.0 | Perfect - No issues |
| 4.0-4.9 | Good - Minor issues |
| 3.0-3.9 | Acceptable - Needs improvement |
| 2.0-2.9 | Poor - Major issues |
| 1.0-1.9 | Failed - Critical problems |

### Critical Evaluations

These MUST pass for overall success:
- **Dietary Safety**: Score must be 5.0 (no allergens)
- **Ground Truth**: Score must be ≥4.0 (items exist)
- **Geo Location**: Score must be ≥4.0 (correct location)

### Pass Rate

- **≥90%**: ✅ Excellent
- **70-89%**: ⚠️ Needs improvement
- **<70%**: ❌ Major issues

## 🎯 Common Workflows

### Daily Quick Check (5 tests)

Edit `golden_dataset.json` to test only first 5 cases, or create a subset:

```bash
# Run with subset
python evals/eval_runner.py --tests 5
```

### Full Regression Test (20 tests)

```bash
./evals/run_eval.sh
```

### Compare Before/After

```bash
# Before changes
./evals/run_eval.sh
mv evals/results/eval_results_*.json evals/results/baseline.json

# Make changes to your agent

# After changes
./evals/run_eval.sh
mv evals/results/eval_results_*.json evals/results/current.json

# Compare
python evals/compare_results.py baseline.json current.json
```

### CI/CD Integration

```bash
# In your CI pipeline
./evals/run_eval.sh || exit 1  # Fail build if evals fail
```

## 💰 Cost Tracking

Monitor costs in the JSON output:

```bash
cat evals/results/eval_results_*.json | jq '.summary.token_metrics'
```

Shows:
- Total tokens used
- Cost per test
- Model breakdown

## 📝 Logging

Evaluation logs are displayed in console. To save logs:

```bash
./evals/run_eval.sh 2>&1 | tee eval_run.log
```

## 🆘 Getting Help

1. **Check documentation**:
   - `QUICK_START.md` - Quick setup
   - `SETUP_GUIDE.md` - Detailed guide
   - `README_NEW.md` - Complete reference

2. **Verify setup**:
   ```bash
   python evals/test_framework.py
   ```

3. **Check configuration**:
   ```bash
   cat evals/eval_config.yaml
   ```

4. **View example .env**:
   ```bash
   cat .env.example
   ```

---

## Quick Reference

```bash
# Setup (one-time)
cp .env.example .env
nano .env  # Add API keys
pip install -r requirements.txt

# Run evaluations
./evals/run_eval.sh

# View results
cat evals/results/eval_results_*.json | jq '.summary'

# Test framework
python evals/test_framework.py
```

**Ready to run?** Execute: `./evals/run_eval.sh`
