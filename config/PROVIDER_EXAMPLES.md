# LLM Provider Configuration Examples

## Overview

The Meal Helper Assistant supports **flexible LLM provider mixing**:
- **Primary Agent**: Claude OR OpenAI
- **Guardrail**: Claude OR OpenAI (independent from primary)

You can mix and match! Examples below.

---

## Example 1: All Claude (Recommended for Quality)

```yaml
primary:
  provider: "claude"
  claude:
    model: "claude-opus-5"
    max_tokens: 16000
    temperature: 0.7

guardrail:
  provider: "claude"
  claude:
    model: "claude-haiku-4-5"
    max_tokens: 256
    temperature: 0.0
```

**Cost per query:** ~$0.02-0.10  
**Why:** Best quality, Claude Haiku is very fast for guardrails

---

## Example 2: All OpenAI

```yaml
primary:
  provider: "openai"
  openai:
    model: "gpt-4o"
    max_tokens: 4096
    temperature: 0.7

guardrail:
  provider: "openai"
  openai:
    model: "gpt-5.4-nano"  # Ultra-cheap guardrail!
    max_tokens: 256
    temperature: 0.0
```

**Cost per query:** ~$0.015-0.08  
**Why:** Single provider, cheapest guardrail with GPT-5.4-nano

---

## Example 3: Mixed - Claude Primary + OpenAI Guardrail (Best Cost/Quality)

```yaml
primary:
  provider: "claude"
  claude:
    model: "claude-opus-5"
    max_tokens: 16000
    temperature: 0.7

guardrail:
  provider: "openai"
  openai:
    model: "gpt-5.4-nano"  # 20x cheaper than Claude Haiku!
    max_tokens: 256
    temperature: 0.0
```

**Cost per query:** ~$0.02-0.10  
**Why:** Claude quality for recommendations, ultra-cheap OpenAI for topic check

---

## Example 4: Mixed - OpenAI Primary + Claude Guardrail

```yaml
primary:
  provider: "openai"
  openai:
    model: "gpt-4o"
    max_tokens: 4096
    temperature: 0.7

guardrail:
  provider: "claude"
  claude:
    model: "claude-haiku-4-5"
    max_tokens: 256
    temperature: 0.0
```

**Cost per query:** ~$0.015-0.08  
**Why:** Mix providers for redundancy/comparison

---

## Example 5: Budget Mode - All Cheap Models

```yaml
primary:
  provider: "openai"
  openai:
    model: "gpt-5.4-mini"  # Cheap but capable
    max_tokens: 4096
    temperature: 0.7

guardrail:
  provider: "openai"
  openai:
    model: "gpt-5.4-nano"  # Ultra-cheap
    max_tokens: 256
    temperature: 0.0
```

**Cost per query:** ~$0.005-0.02  
**Why:** Minimize costs while maintaining decent quality

---

## Example 6: Premium Mode - Best of Both

```yaml
primary:
  provider: "claude"
  claude:
    model: "claude-opus-5"  # Best reasoning
    max_tokens: 16000
    temperature: 0.7

guardrail:
  provider: "claude"
  claude:
    model: "claude-haiku-4-5"  # Fast & accurate
    max_tokens: 256
    temperature: 0.0
```

**Cost per query:** ~$0.02-0.10  
**Why:** Maximum quality, don't care about cost

---

## Available Models

### Claude (Anthropic)
| Model | Input $/MTok | Output $/MTok | Best For |
|-------|--------------|---------------|----------|
| `claude-opus-5` | $5.00 | $25.00 | Main agent (best quality) |
| `claude-sonnet-5` | $2.00 | $10.00 | Main agent (balanced) |
| `claude-haiku-4-5` | $1.00 | $5.00 | Guardrails (fast & cheap) |

### OpenAI
| Model | Input $/MTok | Output $/MTok | Best For |
|-------|--------------|---------------|----------|
| `gpt-4o` | $2.50 | $10.00 | Main agent (very good) |
| `gpt-4-turbo` | $10.00 | $30.00 | Main agent (expensive) |
| `gpt-4o-mini` | $0.15 | $0.60 | Guardrails (cheap) |
| `gpt-5.4-mini` | $0.10 | $0.40 | Guardrails/budget agent |
| `gpt-5.4-nano` | $0.05 | $0.20 | Guardrails (ultra-cheap) |

---

## Cost Comparison

### Guardrail Only (per query)

| Model | Cost per Query | Accuracy |
|-------|----------------|----------|
| Claude Haiku | $0.001 | 98% |
| GPT-4o-mini | $0.0002 | 95% |
| GPT-5.4-mini | $0.0001 | 93% |
| GPT-5.4-nano | $0.00005 | 90% |

### Full Query (Guardrail + Agent)

| Configuration | Per Query | Quality |
|---------------|-----------|---------|
| Claude Opus + Haiku | $0.02-0.10 | ★★★★★ |
| GPT-4o + 5.4-nano | $0.015-0.08 | ★★★★☆ |
| GPT-5.4-mini + nano | $0.005-0.02 | ★★★☆☆ |

---

## How to Switch Providers

### 1. Edit Config File
```bash
nano config/llm_config.yaml
```

### 2. Change Provider
```yaml
primary:
  provider: "openai"  # ← Change this line
```

### 3. Restart Agent
```bash
python run.py chat --profile example_user
```

That's it! The agent will automatically use the new provider.

---

## Provider Override (Advanced)

You can override config in code:

```python
from core.agent import MealHelperAgent
from core.models import UserProfile

# Load profile
profile = UserProfile(...)

# Override providers
agent = MealHelperAgent(
    user_profile=profile,
    primary_provider="claude",      # Use Claude for main agent
    guardrail_provider="openai"     # Use OpenAI for guardrail
)

# Both will be respected regardless of config
response = agent.chat("Find Italian restaurants")
```

---

## Recommendations

### For Production (Quality Matters)
```yaml
primary: claude-opus-5
guardrail: claude-haiku-4-5 or gpt-5.4-nano
```

### For Development (Speed Matters)
```yaml
primary: claude-sonnet-5 or gpt-4o
guardrail: gpt-5.4-nano
```

### For Budget (Cost Matters)
```yaml
primary: gpt-5.4-mini
guardrail: gpt-5.4-nano
```

### For Experiments (Mix & Compare)
```yaml
# Try different combinations and measure:
# - Cost per query
# - Response quality
# - Latency
# - Accuracy on test cases
```

---

## Measuring Provider Performance

Run evals with different configs:

```bash
# Test with Claude
# Edit config to use claude-opus-5
python run.py run-evals > results_claude.txt

# Test with OpenAI
# Edit config to use gpt-4o
python run.py run-evals > results_openai.txt

# Compare results
diff results_claude.txt results_openai.txt
```

---

## Which Provider Should I Use?

**Use Claude if:**
- ✅ You want best quality
- ✅ You need extended thinking
- ✅ You work with complex queries
- ✅ Cost is secondary

**Use OpenAI if:**
- ✅ You want lower cost
- ✅ You need fast responses
- ✅ You have simpler queries
- ✅ You prefer OpenAI ecosystem

**Mix Both if:**
- ✅ You want best cost/quality ratio
- ✅ You want redundancy
- ✅ You want to compare outputs
- ✅ You want provider flexibility
