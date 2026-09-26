# Evaluation Strategies & Frameworks

Comprehensive overview of evaluation approaches for the Meal Helper Assistant.

---

## Table of Contents
1. [Available Frameworks](#available-frameworks)
2. [Evaluation Types](#evaluation-types)
3. [Custom vs Off-the-Shelf](#custom-vs-off-the-shelf)
4. [Recommended Stack](#recommended-stack)
5. [Cost-Benefit Analysis](#cost-benefit-analysis)

---

## Available Frameworks

### 1. LangSmith (LangChain Native)

**Overview:** Official observability and evaluation platform from LangChain.

**Pros:**
- ✅ Already integrated with LangChain (we're using it)
- ✅ Built-in dataset management
- ✅ Traces every LLM call automatically
- ✅ Easy A/B testing between providers
- ✅ Has LLM-as-judge built-in
- ✅ Good UI for reviewing results
- ✅ Free tier sufficient to start

**Cons:**
- ❌ Vendor lock-in to LangChain ecosystem
- ❌ Limited customization for domain-specific metrics
- ❌ Can get expensive at scale (after free tier)

**Best For:**
- Quick setup and iteration
- A/B testing different LLMs
- Teams already using LangChain

**Evaluation Types:**
```
├── Correctness Evals
│   ├── Did agent find restaurants in correct location?
│   ├── Are menu prices accurate?
│   └── Did it filter allergies correctly?
│
├── Quality Evals (LLM-as-judge)
│   ├── "Is recommendation relevant to query?"
│   ├── "Does response address user's constraints?"
│   └── "Is explanation helpful and clear?"
│
└── Performance Evals
    ├── Latency (time to first recommendation)
    ├── Cost per query
    └── Success rate (found results vs failed)
```

**Example Setup:**
```python
from langsmith import Client, RunTree

client = Client()

# Create dataset
dataset = client.create_dataset("meal-helper-golden-50")
client.create_examples(
    dataset_id=dataset.id,
    inputs=[{"query": "pizza under $15"}],
    outputs=[{"expected_location": "user_profile_location"}]
)

# Run evaluation
def run_agent(inputs):
    return agent.chat(inputs["query"])

results = client.run_on_dataset(
    dataset_name="meal-helper-golden-50",
    llm_or_chain_factory=run_agent,
    evaluation=evaluate_result
)
```

**Cost Estimate:**
- Free tier: 5,000 traces/month
- After: $99/month for 50k traces
- For daily eval runs (50 queries): ~1,500 traces/month = **Free**

---

### 2. Phoenix by Arize AI

**Overview:** Open-source observability and eval platform focused on ML/LLM systems.

**Pros:**
- ✅ Open source (free forever)
- ✅ Great for observability + evals
- ✅ LLM-as-judge patterns built-in
- ✅ Can evaluate retrieval quality (menu extraction)
- ✅ Drift detection (is performance degrading over time?)
- ✅ Self-hosted (data privacy)

**Cons:**
- ❌ More setup required (self-hosted)
- ❌ Less integrated with LangChain
- ❌ UI not as polished as LangSmith

**Best For:**
- Teams wanting open-source
- Need for custom metrics
- Data privacy requirements

**Unique Features for Our Project:**

**Menu Extraction Quality Eval:**
```python
from phoenix.evals import run_evals

# Evaluate menu scraping accuracy
eval_results = run_evals(
    eval_model="gpt-4",
    evaluators=[
        PrecisionEvaluator(),  # % extracted items that are real
        RecallEvaluator(),     # % real items that were extracted
        PriceAccuracyEvaluator()  # Are prices correct?
    ],
    data={
        "reference": ground_truth_menu,
        "prediction": scraped_menu
    }
)
```

**Drift Detection:**
```python
# Track if menu extraction quality is degrading
px.track_metric(
    name="menu_extraction_precision",
    value=0.92,
    timestamp=datetime.now()
)

# Alert if drops below threshold
if precision < 0.85:
    alert("Menu extraction quality degraded!")
```

**Cost:** Free (open source)

---

### 3. BrainTrust by BrainTrust Data

**Overview:** Platform specifically designed for LLM application development.

**Pros:**
- ✅ Designed specifically for LLM apps
- ✅ Version control for prompts
- ✅ A/B testing built-in
- ✅ Regression testing (did new code break old queries?)
- ✅ Great for prompt engineering iteration
- ✅ Good team collaboration features

**Cons:**
- ❌ Newer platform (less mature)
- ❌ Pricing can get expensive
- ❌ Less community support than LangSmith

**Best For:**
- Prompt engineering teams
- Need for version control
- Want regression testing

**Key Features:**

**Prompt Versioning:**
```python
# Track prompt changes
prompt_v1 = "Find restaurants matching {query}"
prompt_v2 = "Search for {query} restaurants within {radius}m"

# Compare performance
results = braintrust.compare(
    prompts=[prompt_v1, prompt_v2],
    test_cases=golden_dataset
)
# Shows which prompt version performs better
```

**Regression Testing:**
```python
# Before deploying new code
baseline = braintrust.get_baseline("main")
current = braintrust.run_evals(golden_dataset)

diff = braintrust.compare(baseline, current)
if diff.regression_detected:
    print(f"⚠️ Regression in: {diff.failed_cases}")
    # Block deployment
```

**Cost:**
- Free tier: 1,000 evals/month
- Pro: $50/month for 10k evals
- For daily runs: **Free tier sufficient**

---

### 4. Custom LLM-as-Judge Framework

**Overview:** Build your own using Claude/GPT as evaluators.

**Pros:**
- ✅ Full control over evaluation logic
- ✅ Can optimize for specific use case
- ✅ No vendor lock-in
- ✅ Can use cheapest models (Haiku)
- ✅ Easy to debug and iterate

**Cons:**
- ❌ Need to build everything yourself
- ❌ No built-in UI
- ❌ Need to manage datasets manually
- ❌ Need to build tracking/monitoring

**Best For:**
- Specific domain requirements
- Want full control
- Have engineering resources

**Implementation Patterns:**

#### **Pattern 1: Single-Dimension Scoring**
```python
def evaluate_relevance(query: str, recommendations: str) -> dict:
    prompt = f"""
    Rate the relevance of these recommendations on a scale of 1-5.
    
    Query: {query}
    Recommendations: {recommendations}
    
    Respond with JSON:
    {{
      "score": 1-5,
      "reasoning": "why this score",
      "issues": ["list any problems"]
    }}
    """
    
    response = client.messages.create(
        model="claude-haiku-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return json.loads(response.content[0].text)
```

#### **Pattern 2: Multi-Criteria Evaluation**
```python
EVALUATION_RUBRIC = {
    "allergen_safety": {
        "critical": True,
        "weight": 0.4,
        "question": "Does ANY recommendation contain user's allergens?",
        "pass_criteria": "No allergens found"
    },
    "budget_adherence": {
        "critical": False,
        "weight": 0.2,
        "question": "Are all items under budget?",
        "pass_criteria": "All items <= max_price"
    },
    "location_correctness": {
        "critical": True,
        "weight": 0.3,
        "question": "Are restaurants in the requested location?",
        "pass_criteria": "All restaurants within radius"
    },
    "relevance": {
        "critical": False,
        "weight": 0.1,
        "question": "Do recommendations match query intent?",
        "pass_criteria": "Score >= 4/5"
    }
}

def evaluate_with_rubric(test_case, result):
    scores = {}
    for dimension, criteria in EVALUATION_RUBRIC.items():
        score = evaluate_dimension(
            dimension=dimension,
            criteria=criteria,
            test_case=test_case,
            result=result
        )
        scores[dimension] = score
    
    # Calculate weighted average
    total_score = sum(
        scores[dim]["score"] * EVALUATION_RUBRIC[dim]["weight"]
        for dim in scores
    )
    
    # Check critical failures
    critical_failures = [
        dim for dim, score in scores.items()
        if EVALUATION_RUBRIC[dim]["critical"] and not score["passed"]
    ]
    
    return {
        "scores": scores,
        "total_score": total_score,
        "passed": len(critical_failures) == 0,
        "critical_failures": critical_failures
    }
```

**Cost:**
- Haiku: ~$0.0003/eval
- Sonnet: ~$0.0020/eval
- Custom hybrid: ~$0.0026/eval
- **50 daily evals: ~$4/month**

---

## Evaluation Types

### 1. Quantitative Metrics (Ground Truth)

These have objectively correct answers:

#### **Component-Level:**

**Location Service:**
```python
def test_geocoding_accuracy():
    test_cases = [
        ("17050", (40.247, -77.033), 5.0),  # ZIP, expected coords, tolerance (miles)
        ("New York, NY", (40.713, -74.006), 10.0),
        ("Times Square", (40.758, -73.986), 2.0),
    ]
    
    for address, expected, tolerance in test_cases:
        lat, lng, _ = get_location(address)
        distance = haversine_distance((lat, lng), expected)
        assert distance < tolerance, f"{address} off by {distance} miles"
```

**Menu Extraction:**
```python
def test_menu_extraction_accuracy():
    ground_truth = load_ground_truth_menu("restaurant_x")
    scraped = scrape_menu("restaurant_x")
    
    # Precision: % of scraped items that are real
    precision = len(scraped & ground_truth) / len(scraped)
    
    # Recall: % of real items that were scraped
    recall = len(scraped & ground_truth) / len(ground_truth)
    
    # Price accuracy
    price_errors = [
        abs(scraped[item] - ground_truth[item])
        for item in (scraped & ground_truth)
    ]
    mae = sum(price_errors) / len(price_errors)
    
    assert precision > 0.90, f"Precision too low: {precision}"
    assert recall > 0.85, f"Recall too low: {recall}"
    assert mae < 0.50, f"Price error too high: ${mae}"
```

**Filtering:**
```python
def test_allergen_filtering():
    menu_items = [
        {"name": "Peanut Butter Cookie", "ingredients": ["peanuts", "flour"]},
        {"name": "Vanilla Cake", "ingredients": ["flour", "sugar", "vanilla"]},
    ]
    
    filtered = filter_by_allergies(menu_items, allergies=["peanuts"])
    
    # MUST filter out peanut cookie
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Vanilla Cake"
    
    # Check no allergens in results
    for item in filtered:
        for allergen in ["peanuts"]:
            assert allergen not in item.get("ingredients", [])
```

#### **End-to-End:**

**Success Rate:**
```python
def test_success_rate():
    results = run_golden_dataset()
    
    success_count = sum(1 for r in results if len(r.recommendations) > 0)
    success_rate = success_count / len(results)
    
    assert success_rate > 0.90, f"Success rate too low: {success_rate}"
```

**Latency:**
```python
def test_latency():
    latencies = []
    for test_case in golden_dataset:
        start = time.time()
        result = agent.chat(test_case.query)
        latency = time.time() - start
        latencies.append(latency)
    
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    
    assert p50 < 3.0, f"P50 latency too high: {p50}s"
    assert p95 < 10.0, f"P95 latency too high: {p95}s"
```

**Cost:**
```python
def test_cost_per_query():
    costs = []
    for test_case in golden_dataset:
        result = agent.chat(test_case.query)
        costs.append(result.cost)
    
    avg_cost = sum(costs) / len(costs)
    
    assert avg_cost < 0.05, f"Cost too high: ${avg_cost}/query"
```

---

### 2. Qualitative Metrics (LLM-as-Judge)

These require nuanced judgment:

#### **Relevance Evaluation:**
```python
RELEVANCE_PROMPT = """
You are evaluating a restaurant recommendation system.

USER QUERY: "{query}"
USER PROFILE:
- Allergies: {allergies}
- Restrictions: {restrictions}
- Budget: {budget}

RECOMMENDATIONS:
{recommendations}

Evaluate relevance (1-5):
1 = Completely irrelevant
2 = Somewhat related but poor match
3 = Relevant but could be better
4 = Good match with minor issues
5 = Perfect match for user needs

Respond with JSON:
{{
  "score": 1-5,
  "reasoning": "detailed explanation",
  "strengths": ["what was good"],
  "weaknesses": ["what could improve"]
}}
"""

def evaluate_relevance(test_case, result):
    response = claude.messages.create(
        model="claude-sonnet-4",
        messages=[{
            "role": "user",
            "content": RELEVANCE_PROMPT.format(
                query=test_case.query,
                allergies=test_case.profile.allergies,
                restrictions=test_case.profile.restrictions,
                budget=test_case.profile.budget,
                recommendations=format_recommendations(result)
            )
        }]
    )
    
    return json.loads(response.content[0].text)
```

#### **Safety Evaluation (Critical):**
```python
SAFETY_PROMPT = """
CRITICAL SAFETY CHECK

USER ALLERGIES: {allergies}
RECOMMENDATIONS: {recommendations}

Task: Check if ANY recommendation contains user's allergens.

For each item:
1. List all ingredients (if available)
2. Check against allergen list
3. Flag ANY matches

Respond with JSON:
{{
  "safe": true/false,
  "items_checked": count,
  "allergen_matches": [
    {{"item": "name", "allergen": "found", "confidence": 0.0-1.0}}
  ],
  "reasoning": "explanation"
}}

IMPORTANT: Even suspected allergens should be flagged.
Better to be overly cautious than risk user safety.
"""

def evaluate_safety(test_case, result):
    response = claude.messages.create(
        model="claude-haiku-4",  # Fast & cheap for binary check
        messages=[{
            "role": "user",
            "content": SAFETY_PROMPT.format(
                allergies=test_case.profile.allergies,
                recommendations=format_recommendations(result)
            )
        }]
    )
    
    safety_result = json.loads(response.content[0].text)
    
    # Critical: Must be safe
    if not safety_result["safe"]:
        raise CriticalSafetyFailure(
            f"Allergen found: {safety_result['allergen_matches']}"
        )
    
    return safety_result
```

#### **Helpfulness Evaluation:**
```python
HELPFULNESS_PROMPT = """
Evaluate how helpful this response is to the user.

USER QUERY: "{query}"
RESPONSE: {response}

Rate helpfulness (1-5):
1 = Unhelpful or confusing
2 = Barely helpful, missing key info
3 = Somewhat helpful but incomplete
4 = Helpful with minor gaps
5 = Extremely helpful and actionable

Consider:
- Is information clear and easy to understand?
- Are next steps obvious (how to order/visit)?
- Does it explain WHY these recommendations?
- Are addresses/prices clearly presented?
- Would user know what to do next?

Respond with JSON:
{{
  "score": 1-5,
  "reasoning": "why this score",
  "actionability": "what user can do next",
  "missing_info": ["what else would help"]
}}
"""
```

---

### 3. Domain-Specific Evals

Specific to meal recommendations:

#### **Dietary Safety Eval (Critical):**
```python
def test_dietary_safety():
    """Test that NO restricted items appear in results."""
    
    test_cases = [
        {
            "query": "pizza near me",
            "restrictions": ["no_beef"],
            "must_not_contain": ["beef", "steak", "ground beef"],
            "severity": "critical"
        },
        {
            "query": "seafood restaurant",
            "allergies": ["shellfish"],
            "must_not_contain": ["shrimp", "crab", "lobster", "clams"],
            "severity": "critical"
        },
    ]
    
    for case in test_cases:
        result = agent.chat(case["query"])
        
        # Check ALL recommended items
        for item in result.items:
            name_lower = item["name"].lower()
            desc_lower = item.get("description", "").lower()
            
            for forbidden in case["must_not_contain"]:
                assert forbidden not in name_lower, \
                    f"SAFETY: Found '{forbidden}' in item name"
                assert forbidden not in desc_lower, \
                    f"SAFETY: Found '{forbidden}' in description"
```

#### **Location Accuracy Eval:**
```python
def test_location_accuracy():
    """Test that results are in the correct location."""
    
    test_cases = [
        ("pizza in 17050", "Mechanicsburg, PA", 5),  # ZIP
        ("burger in New York", "New York, NY", 20),   # City
        ("sushi at Times Square", "Manhattan, NY", 2), # Landmark
    ]
    
    for query, expected_location, tolerance_miles in test_cases:
        result = agent.chat(query)
        
        # All restaurants should be near expected location
        for restaurant in result.restaurants:
            distance = calculate_distance(
                restaurant.location,
                geocode(expected_location)
            )
            assert distance < tolerance_miles, \
                f"Restaurant {restaurant.name} is {distance}mi away"
```

#### **Query Intent Eval:**
```python
def test_query_understanding():
    """Test that search query makes sense for user input."""
    
    test_cases = [
        {
            "input": "biryani near me",
            "expected_search": ["biryani", "indian restaurant"],
            "location_extracted": True
        },
        {
            "input": "pizza under $15",
            "expected_search": ["pizza"],
            "price_extracted": 15.0
        },
        {
            "input": "lunch near me",
            "expected_search": ["lunch restaurant", "restaurant"],
            "location_extracted": True
        },
    ]
    
    for case in test_cases:
        # Mock the agent's internal parsing
        parsed_query = agent.query_parser.extract_food_query(case["input"])
        
        # Check if parsed query matches expectations
        matches = any(
            expected in parsed_query.lower()
            for expected in case["expected_search"]
        )
        assert matches, \
            f"Query '{parsed_query}' doesn't match expectations: {case['expected_search']}"
```

---

## Custom vs Off-the-Shelf

### When to Build Custom

**Choose Custom Framework When:**

✅ You have specific domain requirements
```
Example: Food safety eval with ingredient-level checking
→ Off-the-shelf doesn't understand food allergies deeply
```

✅ You need full control over cost
```
Example: Use Haiku for simple checks, Sonnet for complex reasoning
→ Vendor platforms charge flat rate
```

✅ You want to optimize for your use case
```
Example: Fail-fast on critical safety checks before quality eval
→ Vendor platforms run all evals regardless
```

✅ You have engineering resources
```
Team can maintain custom code and iterate quickly
```

### When to Use Off-the-Shelf

**Choose Vendor Platform When:**

✅ You want to move fast
```
LangSmith can be set up in <1 day
→ Custom framework takes ~1 week
```

✅ You need built-in features
```
Dataset versioning, UI, A/B testing all included
→ Would take weeks to build yourself
```

✅ You're already using the ecosystem
```
Using LangChain? → LangSmith is seamless
Using Arize for ML? → Phoenix is natural fit
```

✅ Team is small or non-technical
```
Less code to maintain
UI for non-engineers to review results
```

---

## Recommended Stack

Based on our analysis, here's the recommended evaluation stack for Meal Helper Assistant:

### **Primary: Custom Hybrid LLM-as-Judge**
**Why:** Best accuracy, cost-effective, full control

**Architecture:**
```python
# Critical judges (specialized)
safety_judge = SafetyJudge(model="claude-haiku-4")      # $0.0003/eval
location_judge = LocationJudge(model="claude-haiku-4")  # $0.0003/eval

# Quality judge (generalist)
quality_judge = QualityJudge(model="claude-sonnet-4")   # $0.0020/eval

# Total: $0.0026/eval = $3.90/month for daily runs
```

### **Secondary: LangSmith for Observability**
**Why:** Already integrated, free tier sufficient, good UI

**Use For:**
- Viewing traces of agent runs
- Comparing different LLM providers
- Dataset management
- Team collaboration

**Cost:** Free (under 5k traces/month)

### **Testing: pytest for Automation**
**Why:** Easy to run in CI/CD, familiar to developers

**Use For:**
```bash
# Component tests
pytest tests/test_location_service.py

# Integration tests
pytest tests/test_agent_e2e.py

# Evaluation suite
pytest evals/test_golden_dataset.py
```

**Cost:** Free

### **Dataset: Custom Golden Dataset**
**Why:** Domain-specific, high-quality test cases

**Structure:**
```
evals/datasets/
├── golden_50.json          # Main test suite
├── safety_critical.json    # Allergen tests
├── location_edge_cases.json
└── failure_modes.json
```

**Cost:** Free (hand-crafted)

---

## Cost-Benefit Analysis

### Total Cost Comparison (Monthly, Daily Eval Runs)

| Stack | Setup Time | Monthly Cost | Pros | Cons |
|-------|-----------|--------------|------|------|
| **LangSmith Only** | 1 day | $0 (free tier) | Fast setup, good UI | Less control, limited customization |
| **Phoenix Only** | 3 days | $0 (open source) | Free forever, self-hosted | More setup, less polished |
| **BrainTrust Only** | 2 days | $0 (free tier) | Great for prompt engineering | Newer, less mature |
| **Custom Only** | 1 week | $4 | Full control, optimized | More code to maintain |
| **Hybrid (Custom + LangSmith)** | 1 week | $4 | Best of both worlds | More complex | ✅ **Recommended**

### ROI Analysis

**Investment:**
- 1 week engineering time to build custom framework
- ~2 hours/week to maintain

**Returns:**
- Catch critical bugs before production (allergen filtering)
- Prevent regression when changing code
- Optimize LLM costs (test before deploying expensive models)
- Improve user satisfaction (data-driven improvements)

**Break-Even:**
- If prevents 1 production bug/month → Saves hours of debugging
- If catches 1 allergen slip → Potentially saves lives
- If optimizes LLM provider choice → Saves 20-30% on LLM costs

**Verdict:** High ROI, especially for safety-critical applications

---

## Next Steps

To implement evaluations:

1. **Review judge architectures** → `judge_architectures.md`
2. **Define metrics** → `metrics_and_rubrics.md`
3. **Create golden dataset** → `test_cases.md`
4. **Implement judges** → `implementation_guide.md`
5. **Integrate into CI/CD**

---

**Created:** 2024-09-24  
**Status:** Ready for implementation  
**Recommended:** Hybrid Custom + LangSmith stack
