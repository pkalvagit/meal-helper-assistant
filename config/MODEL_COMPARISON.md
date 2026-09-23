# 🤖 LLM Model Comparison

## All Supported Models

### Claude Models (Anthropic)

| Model | Input $/MTok | Output $/MTok | Context | Best For | Speed |
|-------|--------------|---------------|---------|----------|-------|
| **claude-opus-5** | $5.00 | $25.00 | 1M | Premium agent, complex reasoning | ⚡⚡ Medium |
| **claude-sonnet-5** | $2.00 | $10.00 | 1M | Balanced agent, production | ⚡⚡⚡ Fast |
| **claude-haiku-4-5** | $1.00 | $5.00 | 200K | Guardrails, quick tasks | ⚡⚡⚡⚡ Very Fast |

### OpenAI Models

| Model | Input $/MTok | Output $/MTok | Context | Best For | Speed |
|-------|--------------|---------------|---------|----------|-------|
| **gpt-4o** | $2.50 | $10.00 | 128K | Main agent, very capable | ⚡⚡⚡ Fast |
| **gpt-4-turbo** | $10.00 | $30.00 | 128K | Premium agent (expensive) | ⚡⚡ Medium |
| **gpt-4o-mini** | $0.15 | $0.60 | 128K | Guardrails, budget agent | ⚡⚡⚡⚡ Very Fast |
| **gpt-5.4-mini** | $0.10 | $0.40 | 128K | Guardrails, ultra-cheap | ⚡⚡⚡⚡⚡ Ultra Fast |
| **gpt-5.4-nano** | $0.05 | $0.20 | 128K | Guardrails only, extreme budget | ⚡⚡⚡⚡⚡ Ultra Fast |

---

## Cost per 1K Tokens (More Intuitive)

### Primary Agent (full query with tools)

| Model | Input $0.001 | Output $0.001 | Typical Query Cost |
|-------|--------------|---------------|---------------------|
| claude-opus-5 | $0.005 | $0.025 | **$0.05-0.15** |
| claude-sonnet-5 | $0.002 | $0.010 | **$0.02-0.08** |
| gpt-4o | $0.0025 | $0.010 | **$0.025-0.10** |
| gpt-4-turbo | $0.010 | $0.030 | **$0.10-0.30** |
| gpt-5.4-mini | $0.0001 | $0.0004 | **$0.005-0.02** |

### Guardrail (simple classification)

| Model | Per Check | Daily (1000 queries) |
|-------|-----------|----------------------|
| claude-haiku-4-5 | $0.001 | **$1.00** |
| gpt-4o-mini | $0.0002 | **$0.20** |
| gpt-5.4-mini | $0.0001 | **$0.10** |
| gpt-5.4-nano | $0.00005 | **$0.05** |

---

## Quality Comparison (Subjective)

### For Restaurant Recommendations

| Model | Reasoning | Tool Use | Accuracy | Overall |
|-------|-----------|----------|----------|---------|
| claude-opus-5 | ★★★★★ | ★★★★★ | ★★★★★ | **Best** |
| claude-sonnet-5 | ★★★★☆ | ★★★★★ | ★★★★☆ | Excellent |
| gpt-4o | ★★★★☆ | ★★★★☆ | ★★★★☆ | Excellent |
| gpt-4-turbo | ★★★★☆ | ★★★★☆ | ★★★★☆ | Excellent |
| gpt-4o-mini | ★★★☆☆ | ★★★☆☆ | ★★★☆☆ | Good |
| gpt-5.4-mini | ★★★☆☆ | ★★★☆☆ | ★★★☆☆ | Good |
| gpt-5.4-nano | ★★☆☆☆ | ★★☆☆☆ | ★★☆☆☆ | Basic |

### For Guardrails (Topic Classification)

| Model | Accuracy | Speed | Cost | Recommended |
|-------|----------|-------|------|-------------|
| claude-haiku-4-5 | 98% | 200ms | $$ | ✅ Yes |
| gpt-4o-mini | 95% | 150ms | $ | ✅ Yes |
| gpt-5.4-mini | 93% | 100ms | $ | ✅ Yes |
| gpt-5.4-nano | 90% | 80ms | ¢ | ⚠️ Budget only |

---

## Recommended Configurations

### 🏆 Best Quality (Production)
```yaml
primary:
  provider: "claude"
  claude:
    model: "claude-opus-5"

guardrail:
  provider: "claude"
  claude:
    model: "claude-haiku-4-5"
```
**Cost:** $0.05-0.15 per query  
**Quality:** ★★★★★  
**Speed:** ⚡⚡⚡ Fast

---

### 💰 Best Value (Recommended)
```yaml
primary:
  provider: "claude"
  claude:
    model: "claude-opus-5"

guardrail:
  provider: "openai"
  openai:
    model: "gpt-5.4-nano"
```
**Cost:** $0.05-0.15 per query (guardrail saves 20x)  
**Quality:** ★★★★★  
**Speed:** ⚡⚡⚡⚡ Very Fast

---

### ⚡ Fastest (Development)
```yaml
primary:
  provider: "claude"
  claude:
    model: "claude-sonnet-5"

guardrail:
  provider: "openai"
  openai:
    model: "gpt-5.4-nano"
```
**Cost:** $0.02-0.08 per query  
**Quality:** ★★★★☆  
**Speed:** ⚡⚡⚡⚡⚡ Ultra Fast

---

### 💸 Cheapest (Budget)
```yaml
primary:
  provider: "openai"
  openai:
    model: "gpt-5.4-mini"

guardrail:
  provider: "openai"
  openai:
    model: "gpt-5.4-nano"
```
**Cost:** $0.005-0.02 per query  
**Quality:** ★★★☆☆  
**Speed:** ⚡⚡⚡⚡⚡ Ultra Fast

---

### 🔬 Experimental (Compare)
```yaml
# Try both and measure
primary:
  provider: "openai"
  openai:
    model: "gpt-4o"

guardrail:
  provider: "claude"
  claude:
    model: "claude-haiku-4-5"
```
**Cost:** $0.025-0.10 per query  
**Quality:** ★★★★☆  
**Speed:** ⚡⚡⚡ Fast

---

## Cost at Scale

### 1,000 Queries/Day

| Configuration | Daily Cost | Monthly Cost | Annual Cost |
|---------------|------------|--------------|-------------|
| Opus + Haiku | $100 | $3,000 | $36,000 |
| Opus + 5.4-nano | $100 | $3,000 | $36,000 |
| GPT-4o + 4o-mini | $50 | $1,500 | $18,000 |
| Sonnet + 5.4-nano | $40 | $1,200 | $14,400 |
| 5.4-mini + nano | $10 | $300 | $3,600 |

### 10,000 Queries/Day (High Volume)

| Configuration | Daily Cost | Monthly Cost | Annual Cost |
|---------------|------------|--------------|-------------|
| Opus + Haiku | $1,000 | $30,000 | $360,000 |
| Opus + 5.4-nano | $1,000 | $30,000 | $360,000 |
| Sonnet + 5.4-nano | $400 | $12,000 | $144,000 |
| 5.4-mini + nano | $100 | $3,000 | $36,000 |

---

## When to Use Each Model

### Claude Opus 5
✅ Complex multi-step reasoning  
✅ Extended thinking required  
✅ Highest quality needed  
✅ Budget not a concern  
❌ Don't use for simple queries

### Claude Sonnet 5
✅ Production workloads  
✅ Good balance cost/quality  
✅ High-volume with quality  
❌ Not cheapest option

### Claude Haiku 4.5
✅ Guardrails (best accuracy)  
✅ Quick classifications  
✅ Simple extractions  
❌ Not for complex reasoning

### GPT-4o
✅ Alternative to Claude Opus  
✅ OpenAI ecosystem  
✅ Good tool use  
❌ Not cheapest

### GPT-5.4-mini
✅ Budget primary agent  
✅ High-volume guardrails  
✅ Development/testing  
❌ Lower quality than Opus/4o

### GPT-5.4-nano
✅ Ultra-cheap guardrails  
✅ Topic classification only  
✅ Extreme budget constraints  
❌ Not reliable for complex tasks

---

## Testing Different Models

```bash
# 1. Edit config
nano config/llm_config.yaml

# 2. Run test query
python run.py chat -q "Find high protein lunch under $15"

# 3. Compare cost
# (shown at end of response)

# 4. Run evals
python run.py run-evals

# 5. Log results
echo "Model X: Cost=$Y, Pass rate=Z%" >> model_comparison.txt
```

---

## API Key Requirements

| Provider | Required API Key | Get Key From |
|----------|------------------|--------------|
| Claude | `ANTHROPIC_API_KEY` | https://console.anthropic.com |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Google Places | `GOOGLE_MAPS_API_KEY` | https://console.cloud.google.com |

You can use **one or both** LLM providers - agent respects which keys are set.

---

## Model Selection Decision Tree

```
Need highest quality? → claude-opus-5
    ↓ No
Cost matters? → Yes
    ↓
Volume < 1000/day? → claude-sonnet-5 + gpt-5.4-nano
    ↓ No
Volume > 10k/day? → gpt-5.4-mini + gpt-5.4-nano
    ↓ No
Want to compare? → Try both Claude & OpenAI
    ↓
Done! Measure & iterate.
```
