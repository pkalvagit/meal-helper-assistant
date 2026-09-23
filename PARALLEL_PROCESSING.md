# Parallel Menu Fetching

## **Overview**

Menu fetching now runs **in parallel** with configurable concurrency, significantly reducing wait times.

## **Configuration**

### **.env Settings**

```bash
MENU_BATCH_SIZE=5          # Maximum restaurants to process
MENU_FETCH_CONCURRENCY=3   # Number of parallel workers
```

### **Recommended Settings**

| Scenario | Batch Size | Concurrency | Why |
|----------|-----------|-------------|-----|
| **Fast queries** | 3 | 2 | Quick results, less API load |
| **Balanced** (default) | 5 | 3 | Good speed/coverage balance |
| **Thorough** | 10 | 4 | More options, longer wait |
| **Conservative** | 5 | 1 | Sequential (debugging) |

**Note:** Higher concurrency = faster BUT more simultaneous browser instances and API calls.

## **Performance Comparison**

### **Sequential (Old Way)**
```
Restaurant 1: 15s ────────────────►
Restaurant 2:                     15s ────────────────►
Restaurant 3:                                         15s ────────────────►
Total: 45 seconds
```

### **Parallel (New Way, concurrency=3)**
```
Restaurant 1: 15s ────────────────►
Restaurant 2: 15s ────────────────►
Restaurant 3: 15s ────────────────►
Total: 15 seconds (3x faster!)
```

## **User Experience**

### **What You'll See**

```
━━━ Processing your request ━━━

🔍 Searching for biryani...
📋 Fetching menus from 5 restaurants...
  ✓ Masti: 150 items (1/5)
  ✓ Biryani Factory: 87 items (2/5)
  ✗ Spice Xing: No website (3/5)
  ✓ Taj Palace: 112 items (4/5)
  ✗ Curry House: Menu scraping failed (5/5)
✓ Filtering 349 menu items...

━━━ Results ━━━
...
```

**Note:** Results appear **as they complete**, not in order. Fastest restaurants show first!

## **Error Handling**

### **Individual Failures Don't Block Others**

```python
# Restaurant 1: Success (completes in 10s)
# Restaurant 2: FAILS (times out at 30s)
# Restaurant 3: Success (completes in 12s)

# Old way: Wait 10s + 30s + 12s = 52s total
# New way: Max(10s, 30s, 12s) = 30s total
#          AND Restaurant 1 & 3 show results before Restaurant 2 fails!
```

### **Timeout Protection**

Each restaurant has independent timeout:
- If one restaurant hangs → others continue
- Failed restaurants are logged and skipped
- User gets results from successful restaurants

## **Implementation Details**

### **ThreadPoolExecutor**

Uses Python's `concurrent.futures.ThreadPoolExecutor`:
- Thread-safe
- Bounded resource usage (max_workers limit)
- Handles exceptions gracefully
- Results collected as they complete (`as_completed()`)

### **Why Threads, Not Async?**

Menu fetching is mostly I/O-bound:
- Playwright (browser automation)
- HTTP requests (API calls)
- LLM calls (extraction)

Threads work well for I/O-bound tasks with blocking libraries.

## **Monitoring**

### **Logs**

```
2026-09-23 16:30:00 | INFO | Batch processing 5 restaurants with concurrency=3...
2026-09-23 16:30:01 | INFO | [1/5] Fetching menu from Masti...
2026-09-23 16:30:01 | INFO | [2/5] Fetching menu from Spice Xing...
2026-09-23 16:30:01 | INFO | [3/5] Fetching menu from Biryani Factory...
2026-09-23 16:30:12 | INFO | ✓ Masti: 150 items
2026-09-23 16:30:13 | INFO | ✗ Spice Xing: No website
2026-09-23 16:30:14 | INFO | ✓ Biryani Factory: 87 items
2026-09-23 16:30:15 | INFO | Batch complete: 2 successful, 1 failed
```

## **Tuning Guide**

### **Increase Concurrency If:**
- ✅ You have good internet bandwidth
- ✅ Most restaurants have simple menus (fast scraping)
- ✅ You want faster results
- ✅ System has available resources

### **Decrease Concurrency If:**
- ⚠️ Getting rate-limited by websites
- ⚠️ System running out of memory (Playwright is heavy)
- ⚠️ Scraping very complex JavaScript sites (each takes 30s+)
- ⚠️ SSL proxy causing issues

### **Sweet Spot**

**Concurrency = 3** works for most cases:
- Fast enough (3x speedup with 5 restaurants)
- Safe (doesn't overwhelm system or APIs)
- Reliable (handles failures gracefully)

## **Testing**

```bash
# Test with different concurrency levels
MENU_FETCH_CONCURRENCY=1 python run.py chat -p example_user  # Sequential
MENU_FETCH_CONCURRENCY=3 python run.py chat -p example_user  # Default
MENU_FETCH_CONCURRENCY=5 python run.py chat -p example_user  # Aggressive
```

Compare total time and success rate to find your optimal setting.
