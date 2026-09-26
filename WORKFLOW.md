# Meal Helper Assistant - Workflow Architecture

## **Correct Workflow Pattern**

```
User Query
    ↓
[1] Guardrails Check
    ↓
[2] Search Restaurants (Google Places)
    ↓
[3] FOR EACH Restaurant (with error handling):
    ├─ Check cache by place_id
    ├─ If not cached:
    │   ├─ Find menu URL
    │   ├─ Scrape menu page → MD file
    │   ├─ Extract items (pattern or LLM)
    │   └─ Cache result
    └─ If error → Log and continue to next
    ↓
[4] Combine ALL successful menus
    ↓
[5] Filter by allergies/restrictions/price
    ↓
[6] LLM formats recommendations
    ↓
User Response
```

## **Key Components**

### **1. Guardrails** (`core/guardrails.py`)
- Checks if query is meal-related
- Extracts intent
- Rejects off-topic queries

### **2. Search** (`tools/search_tool.py`)
- Uses Google Places API
- Configurable radius (env: `SEARCH_RADIUS_METERS`, default: 5000)
- Returns list of restaurants with place_id, website, address, rating

### **3. Batch Processing** (`core/batch_agent.py`)
- **NEW** - Processes multiple restaurants **IN PARALLEL**
- Error handling: if one fails, continues with rest
- Configurable:
  - Batch size (env: `MENU_BATCH_SIZE`, default: 5)
  - Concurrency (env: `MENU_FETCH_CONCURRENCY`, default: 3)
- Uses ThreadPoolExecutor for parallel I/O
- Shows real-time progress as menus complete

### **4. Menu Fetching** (`tools/menu_tool.py`)
- Check cache first (by place_id or URL)
- If not cached:
  - Find menu URL (`menu_url_finder.py`)
  - Scrape with Playwright (`scrape_and_find_menu.py`)
  - Extract items (pattern matching or LLM)
  - Cache result
- Configuration:
  - `SCRAPE_MAX_DEPTH` (default: 2)
  - `SCRAPE_MAX_LINKS_PER_PAGE` (default: 3)
  - `SCRAPE_RENDER_WAIT_MS` (default: 8000)

### **5. Filtering** (`tools/filter_tool.py`)
- Combines all menu items from all restaurants
- Filters by:
  - Allergies (exact match in description/ingredients)
  - Dietary restrictions (no_beef, no_pork, etc.)
  - Max price
- Returns items with restaurant source preserved

### **6. Formatting** (`core/simple_agent.py`)
- Groups filtered items by restaurant
- Formats as markdown with:
  - Restaurant name, rating, address
  - Google Maps link
  - Website
  - Top 5 items per restaurant

## **Configuration (.env)**

```bash
# Search
SEARCH_RADIUS_METERS=5000
SEARCH_MAX_RESULTS=20

# Scraping
SCRAPE_MAX_DEPTH=2
SCRAPE_MAX_LINKS_PER_PAGE=3
SCRAPE_RENDER_WAIT_MS=8000
SCRAPE_NAV_TIMEOUT_MS=45000

# Processing
MENU_BATCH_SIZE=5          # Max restaurants to process
MENU_FETCH_CONCURRENCY=3   # Parallel workers (1-5 recommended)
MENU_FETCH_TIMEOUT=60

# SSL (for corporate proxies)
DISABLE_SSL_VERIFY=true
```

## **Error Handling**

### **Restaurant Level**
```python
for restaurant in restaurants:
    try:
        menu = fetch_menu(restaurant)
        successful_menus.append(menu)
    except Exception as e:
        logger.error(f"Failed: {restaurant.name}: {e}")
        # Continue with next restaurant
```

### **Graceful Degradation**
- If 0 restaurants found → "No restaurants found"
- If 0 menus fetched → "Could not fetch any menus"
- If 0 items pass filter → "No items match your criteria"
- If N/M restaurants fail → Process continues with M-N successful

## **Example Flow**

```
User: "find biryani under $20 near me"

1. Guardrails: ✓ Valid (meal-related)

2. Search: Found 15 restaurants

3. Batch Processing (top 5, concurrency=3):
   [Parallel Workers: 3]
   ├─ Worker 1: Masti → ✓ 150 items
   ├─ Worker 2: Spice Xing → ✗ No website
   ├─ Worker 3: Biryani Factory → ✓ 87 items  
   ├─ Worker 1: Curry House → ✗ Menu scraping failed
   └─ Worker 2: Taj Palace → ✓ 112 items
   [Time saved: ~60% vs sequential]

4. Combined: 349 items from 3 restaurants

5. Filtered:
   - Remove peanuts/shellfish → 312 items
   - Remove beef/pork → 245 items
   - Under $20 → 189 items

6. Format & Respond:
   ## Masti ⭐ 4.7
   1. Chicken Biryani — $16.99
   2. Vegetable Biryani — $14.99
   ...
```

## **Benefits**

1. ✅ **Resilient** - One failure doesn't break everything
2. ✅ **Efficient** - Processes restaurants in parallel
3. ✅ **Accurate** - Only recommends actual menu items
4. ✅ **Configurable** - All parameters in .env
5. ✅ **Logged** - Full error tracking
6. ✅ **Cached** - Repeated queries are fast
