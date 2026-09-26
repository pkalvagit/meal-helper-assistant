# Project Scope - Meal Helper Assistant

**Version**: 1.0  
**Last Updated**: September 26, 2026  
**Status**: Active Development

---

## 🎯 Goal

**Meal Assistant Planner for Personal Use**

A personalized meal recommendation system that helps users:
- Define health goals and dietary requirements
- Store personal information (allergies, restrictions, preferences)
- Discover food options available nearby or at a specified address
- Filter recommendations within a defined budget
- Get safe, relevant meal suggestions matching their profile

**Primary Use Case**: Individual users planning meals with dietary constraints and budget limitations.

---

## ✅ What IS Covered (In Scope)

### Core Features

#### 1. **Restaurant Discovery**
- ✅ Fetch restaurants nearby using Google Places API
- ✅ Support location-based search (current location or specified address)
- ✅ Return up to 20 nearby restaurants
- ✅ Filter by distance radius (default: 5km)

#### 2. **Menu Retrieval & Processing**
- ✅ Dynamically scrape restaurant menus from websites
- ✅ Extract menu items, prices, descriptions
- ✅ Support multiple formats:
  - HTML pages
  - PDF menus
  - Images (convert to markdown first)
- ✅ Multi-page menu handling (pagination)

#### 3. **Intelligent Filtering**
- ✅ Filter menu items by:
  - User allergies (safety-critical)
  - Dietary restrictions (vegan, gluten-free, halal, etc.)
  - Budget constraints (max price per meal)
  - Nutrition targets (high protein, low carb, etc.)
- ✅ Rank recommendations by preference matching

#### 4. **Menu Caching System**
- ✅ Local file-based cache (JSON)
- ✅ Avoids re-scraping previously fetched menus
- ✅ Clear cache script available (`clear_cache.py`)
- 🔄 **Future**: Redis/Memcached with TTL (Time-To-Live)
- 🔄 **Future**: Automatic cache invalidation

#### 5. **Guardrails & Input Validation**
- ✅ Topic relevance check (food/restaurant queries only)
- ✅ Reject off-topic queries (jokes, business advice, etc.)
- ✅ Intent extraction (query type, cuisine, price range)
- ✅ Structured query parsing

#### 6. **Multi-LLM Support**
- ✅ Configurable LLM providers:
  - **Claude**: Opus, Sonnet, Haiku
  - **OpenAI**: GPT-4o, GPT-5.4-mini, GPT-5.4-nano
- ✅ Independent provider selection for:
  - Primary agent (complex reasoning)
  - Guardrails (fast, cheap validation)
- ✅ Cost optimization (use cheaper models where appropriate)

#### 7. **Token Optimization**
- ✅ Pre-process web scraping results
- ✅ Convert HTML/PDF/images to clean markdown
- ✅ Extract structured data before LLM processing
- ✅ **Significant savings**: See example below

**Token Optimization Example (100 Restaurants):**

| Approach | Tokens Used | Cost (GPT-4o) | Time |
|----------|-------------|---------------|------|
| **Direct LLM Extraction** (raw HTML) | ~500K tokens | ~$12.50 | ~5 min |
| **Pre-processed Markdown** (scraping first) | ~50K tokens | ~$1.25 | ~2 min |
| **Savings** | **90% fewer tokens** | **$11.25 saved** | **60% faster** |

*Calculation: 100 restaurants × 5K tokens (raw HTML) vs 100 × 500 tokens (markdown)*

#### 8. **Response Generation**
- ✅ Natural language recommendations
- ✅ Explain why items were selected
- ✅ Show filtering rationale (allergen avoidance)
- ✅ Include prices, distances, restaurant details

#### 9. **User Profile Management**
- ✅ Store user profiles locally (JSON format)
- ✅ Profile fields:
  - Name
  - Allergies
  - Dietary restrictions
  - Budget (max per meal)
  - Preferences
  - Nutrition targets
  - Default location

#### 10. **Evaluation Framework**
- ✅ 6 evaluation dimensions:
  - Latency (P50, P95, P99)
  - Token usage & cost
  - Geo location accuracy
  - Ground truth (menu verification)
  - Dietary safety (allergen detection)
  - Relevance (budget & goal alignment)
- ✅ Parallel LLM judges (3-5x faster)
- ✅ Golden dataset (20 test cases)
- ✅ JSON output for tracking

---

## ❌ What IS NOT Covered (Out of Scope)

### Functional Limitations

#### 1. **Restaurant Coverage**
- ❌ May not cover ALL possible restaurants
- ❌ Limited to restaurants with online presence
- ❌ No coverage for restaurants without websites/menus

#### 2. **Menu Completeness**
- ❌ Dynamic scraping can miss menu items
- ❌ No guarantee of 100% menu extraction
- ❌ Special offers/seasonal items may not be captured
- ❌ Daily specials often missed

#### 3. **Result Set Limitations**
- ❌ **Limited to 5 final restaurant recommendations**
  - Even though 20 nearby restaurants are found
  - Top 5 selected based on menu availability & relevance
- ❌ No pagination or "show more" functionality

#### 4. **Data Storage**
- ❌ No persistent database (SQL/NoSQL)
  - *Technically should use SQL database*
  - Currently: JSON files only
- ❌ No user account system
- ❌ No conversation history storage
- ❌ No analytics database

#### 5. **Caching & Performance**
- ❌ Cache is NOT Redis (currently file-based)
  - *Performance limitation for concurrent users*
  - *No distributed caching*
- ❌ No cache TTL (menus never expire automatically)
- ❌ No cache warming or pre-fetching

#### 6. **Scalability**
- ❌ Not designed for concurrent users
- ❌ No load balancing
- ❌ No horizontal scaling
- ❌ Single-process execution only
- ❌ No rate limiting per user

#### 7. **Mobile & Deployment**
- ❌ No mobile application (iOS/Android)
- ❌ No mobile-optimized UI
- ❌ Local run only (not cloud-deployed)
- ❌ No API service layer

#### 8. **Privacy & Security**
- ❌ User privacy NOT covered in depth
  - User profiles stored in plain text
  - No encryption at rest
  - No anonymization
  - No GDPR/CCPA compliance
- ❌ No user consent management
- ❌ No data retention policies
- ❌ No audit logging

#### 9. **Advanced Features**
- ❌ No restaurant reviews/ratings integration
- ❌ No reservation system
- ❌ No ordering/delivery integration
- ❌ No meal planning (multi-day schedules)
- ❌ No nutrition tracking over time
- ❌ No social features (sharing recommendations)

#### 10. **Error Recovery**
- ❌ No automatic retry for failed scraping
- ❌ No fallback data sources
- ❌ No graceful degradation (all-or-nothing)

---

## 🔧 Assumptions

### Technical Assumptions

#### 1. **LLM Models**
- **Primary Assumption**: OpenAI models are available
  - `gpt-5.4-mini` (primary agent)
  - `gpt-5.4-nano` (guardrails)
- **Alternative**: Claude models (Opus, Sonnet, Haiku)
- **Assumption**: API keys are valid and have sufficient quota

#### 2. **External APIs**
- Google Places API is accessible
- Restaurants have publicly accessible websites
- Web scraping is legally permissible (no ToS violations)

#### 3. **User Environment**
- Python 3.9+ installed
- Sufficient disk space for cache (~100MB per 100 restaurants)
- Internet connectivity
- Modern browser (for Playwright scraping)

#### 4. **Data Quality**
- Restaurant websites contain extractable menus
- Menu prices are in USD
- Allergen information is available (or can be inferred)
- Location data from Google Places is accurate

#### 5. **Usage Patterns**
- Single user (personal use)
- ~10-20 queries per day
- Willing to wait 3-10 seconds for results
- Comfortable with CLI interface

#### 6. **Budget & Cost**
- User has API budget (~$5-10/month)
- Cost-conscious (prefers cheaper models)
- Token optimization is valuable

---

## ⚠️ Known Failures & Limitations

### 1. **Scraping Failures (High Impact)**

**Problem**: Menu scraping can fail partially or completely

**Scenarios**:
- ❌ **Partial Menu**: Some sections not scraped
  - Example: Appetizers found, but desserts missing
  - Pagination not fully traversed
  - JavaScript-heavy sites timeout
  
- ❌ **Complete Failure**: No menu extracted
  - Site blocks bots (Cloudflare, Captcha)
  - Menu in unsupported format (Flash, proprietary viewer)
  - Network timeout during scraping
  - Invalid menu URL returned by finder

**Impact**:
- Incomplete recommendations
- User may miss relevant options
- Restaurant dropped from final 5 if no menu

**Mitigation**:
- Retry once on failure
- Skip restaurant if unsuccessful
- Show warning to user

**Current Behavior**:
```
Found 20 restaurants nearby
✓ Scraped 12 menus successfully
⚠️ Failed: 8 restaurants (dropped from results)
→ Showing top 5 from 12 successful
```

### 2. **Result Set Limitation (Medium Impact)**

**Problem**: Only 5 restaurants shown from 20 nearby

**Why**:
- Performance: Scraping 20 menus takes 2-5 minutes
- Token limits: Processing 20 menus exceeds token budget
- Relevance: Most users only need top 5 options

**Impact**:
- User may miss better options in #6-20
- Bias toward restaurants scraped first (order matters)

**Mitigation**:
- Select 5 based on:
  1. Menu availability
  2. Distance (closer = higher priority)
  3. Rating (if available)
  4. Cache hit (faster = higher priority)

**Example**:
```
Nearby restaurants: 20 found
  → Attempting top 10 by distance
  → Successfully scraped: 7
  → Filtered by allergies: 5 remain
  → Final recommendations: 5 restaurants
```

### 3. **Stale Cache (Low Impact)**

**Problem**: Cached menus never expire automatically

**Impact**:
- Outdated prices
- Unavailable items recommended
- Seasonal items shown out of season

**Current Behavior**:
- Menu cached indefinitely until manually cleared
- No freshness check

**Workaround**:
```bash
# Clear all cached menus
python clear_cache.py

# OR manually delete
rm -rf cache/menus/*
```

**Future Fix**: Add TTL (7 days) to cache

### 4. **Allergen Detection Uncertainty (High Impact)**

**Problem**: Not all ingredients are explicitly listed

**Scenarios**:
- Menu says "Caesar Salad" but doesn't list anchovies (fish allergy risk)
- "May contain traces" warnings not captured
- Cross-contamination not considered
- Generic descriptions ("special sauce" - what's in it?)

**Impact**:
- **Safety risk**: Allergen might be present but not detected
- Over-filtering: Conservative approach drops safe items

**Mitigation**:
- LLM makes conservative guesses
- If uncertain, item is flagged/dropped
- User warned to verify with restaurant

**Example Warning**:
```
⚠️ Allergen Uncertainty Detected:
"House Special Sauce" - ingredients not specified
→ Could contain shellfish (your allergy)
→ Recommendation: Ask restaurant before ordering
```

### 5. **Location Accuracy (Medium Impact)**

**Problem**: Google Places coordinates may be off

**Impact**:
- Distance calculations slightly wrong
- "Near me" might include farther restaurants
- Address-based search depends on geocoding quality

**Typical Error**: ±100-500 meters

### 6. **Token Budget Exceeded (Low Impact)**

**Problem**: Very large menus can hit token limits

**Scenario**:
- Menu with 200+ items
- Multiple pages of content
- Detailed descriptions

**Current Limit**: ~50K tokens per query

**Mitigation**:
- Truncate menu if too large
- Process in sections
- Use cheaper model (Haiku/GPT-4o-mini)

---

## 📋 Success Criteria

**The system is successful if:**

1. ✅ **Safety**: Zero allergen violations detected by evaluation (5/5 score)
2. ✅ **Relevance**: 80%+ of recommendations match user query (≥4/5 score)
3. ✅ **Performance**: P95 latency < 10 seconds
4. ✅ **Cost**: < $0.05 per query on average
5. ✅ **Coverage**: Successfully scrape 60%+ of attempted menus
6. ✅ **Accuracy**: Geo location within 10 miles of target

---

## 🔄 Future Scope (Roadmap)

### Phase 2 (Next 3-6 months)
- Redis caching with TTL
- SQL database for user profiles
- Retry logic for failed scraping
- Support for 10+ final recommendations

### Phase 3 (6-12 months)
- Mobile application (React Native)
- Cloud deployment (AWS/GCP)
- Multi-user support
- Privacy compliance (GDPR/CCPA)

### Phase 4 (12+ months)
- Meal planning (weekly schedules)
- Nutrition tracking over time
- Restaurant partnership APIs (no scraping)
- Social features (share recommendations)

---

## 📊 Metrics & Monitoring

**Current Tracking**:
- ✅ Latency per query (P50, P95, P99)
- ✅ Token usage per query
- ✅ Cost per query
- ✅ Cache hit rate
- ✅ Scraping success rate

**Not Tracked**:
- ❌ User satisfaction
- ❌ Allergen violation rate (in production)
- ❌ Menu freshness age
- ❌ Restaurant coverage percentage

---

## 🎯 Non-Goals (Explicitly NOT Building)

1. ❌ Restaurant management platform
2. ❌ Menu creation/editing tools for restaurants
3. ❌ Food delivery service
4. ❌ Restaurant reservation system
5. ❌ Social network for foodies
6. ❌ Nutrition calculator
7. ❌ Recipe generator
8. ❌ Grocery shopping assistant

---

## 📝 Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-09-26 | Initial scope definition |

---

## ✅ Approval

**Status**: Draft  
**Approved By**: [Pending]  
**Date**: [Pending]

---

**For questions or scope change requests, please create an issue or PR.**
