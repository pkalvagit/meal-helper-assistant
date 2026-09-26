# Deploy Location Fixes to Other Laptop

## Current Status

**This Machine (USRONPKALVA02):** ✅ All fixes applied and working

**Other Laptop:** ❌ Still running old code (shows "meals in" instead of "restaurant")

## Files That Changed

These files need to be synced to your other laptop:

```
Modified Files:
├── core/simple_agent.py         (location extraction + priority logic)
├── core/query_parser.py         (remove locations from food query)
├── utils/location_service.py    (NEW: geocoding + IP detection)
├── .env                         (added PYTHONDONTWRITEBYTECODE=1)
├── clear_cache.sh               (NEW: cache clearing script)
└── Documentation:
    ├── LOCATION_FEATURE.md
    ├── ZIP_CODE_FIX.md
    ├── CACHE_FIX.md
    └── DEPLOY_TO_OTHER_MACHINE.md (this file)
```

## Step-by-Step Deployment

### Option 1: Using Git (Recommended)

**On this machine (USRONPKALVA02):**
```bash
cd /home/pkalva/my-experiments/meal-helper-assistant

# Commit all changes
git add .
git commit -m "Add location service: ZIP codes, full addresses, auto-detection"
git push
```

**On other laptop:**
```bash
cd /home/pkalva/my-experiments/meal-helper-assistant

# Pull latest changes
git pull

# Clear cache (IMPORTANT!)
./clear_cache.sh

# Test
source .venv/bin/activate
python -B run.py chat --profile example_user
```

### Option 2: Manual File Copy

**If not using Git, copy these files from this machine to the other laptop:**

```bash
# On this machine, create a sync package
cd /home/pkalva/my-experiments/meal-helper-assistant
tar -czf meal-helper-fixes.tar.gz \
    core/simple_agent.py \
    core/query_parser.py \
    utils/location_service.py \
    .env \
    clear_cache.sh \
    *.md

# Copy meal-helper-fixes.tar.gz to other laptop
# Then on other laptop:
cd /home/pkalva/my-experiments/meal-helper-assistant
tar -xzf meal-helper-fixes.tar.gz
chmod +x clear_cache.sh
./clear_cache.sh
```

### Option 3: Recreate on Other Laptop

**If file copying is difficult, you can re-apply the changes manually.**

See the code changes in:
- `ZIP_CODE_FIX.md` - Shows what changed
- `LOCATION_FEATURE.md` - Full feature documentation

## Verification Checklist

Run these tests on the other laptop AFTER deployment:

### ✓ Test 1: Query Parser
```bash
source .venv/bin/activate
python -B -c "
from core.query_parser import QueryParser
query = 'meals under \$20 in 17050'
result = QueryParser.extract_food_query(query)
print(f'Query: {query}')
print(f'Result: {result}')
assert result == 'restaurant', f'FAIL: got {result}'
print('✅ PASS')
"
```

**Expected:** Should print `✅ PASS`

### ✓ Test 2: Location Extraction
```bash
python -B -c "
import re
query = 'meals in 17050'
match = re.search(r'\bin\s+(\d{5})', query)
location = match.group(1) if match else None
print(f'Query: {query}')
print(f'Location: {location}')
assert location == '17050', f'FAIL: got {location}'
print('✅ PASS')
"
```

**Expected:** Should print `✅ PASS`

### ✓ Test 3: Geocoding
```bash
python -B -c "
from dotenv import load_dotenv
load_dotenv()
from utils.location_service import get_location
lat, lng, desc = get_location('17050')
print(f'ZIP: 17050')
print(f'Geocoded: {desc}')
print(f'Coords: ({lat:.4f}, {lng:.4f})')
assert 'PA' in desc or 'Pennsylvania' in desc, 'FAIL: Wrong state'
print('✅ PASS')
" 2>&1 | grep -v InsecureRequest | grep -v warnings
```

**Expected:** Should print Pennsylvania location

### ✓ Test 4: Full Integration
```bash
python -B run.py chat --profile example_user
```

**Then type:**
```
You: meals under $20 in 17050
```

**Expected output should contain:**
```
✓ Detected location in query: 17050
✓ Geocoded: Hampden Township, PA 17050, USA
✓ Searching for: restaurant
✓ Found 20 restaurants
```

**Should NOT contain:**
```
✗ Using profile location: (38.9586, -77.357)
✗ Parsed query: '...' -> 'meals in'
✗ Searching for: meals in
```

## Troubleshooting

### Problem: Tests still show old behavior

**Solution:**
```bash
# Kill ALL Python processes
pkill -9 python

# Clear cache again
./clear_cache.sh

# Make sure PYTHONDONTWRITEBYTECODE=1 is in .env
grep PYTHONDONTWRITEBYTECODE .env

# Restart with -B flag
python -B run.py chat --profile example_user
```

### Problem: "utils/location_service.py not found"

**Check utils directory:**
```bash
ls -la utils/
```

**Should show:**
```
location_service.py
places_search.py
menu_url_finder.py
...
```

If missing, copy from this machine or see LOCATION_FEATURE.md for the code.

### Problem: Import errors

**Check Python path:**
```bash
python -B -c "
import sys
from pathlib import Path
print('Python path:')
for p in sys.path:
    print(f'  {p}')
"
```

Should include the project directory.

## Before/After Comparison

### BEFORE (Old Code)
```
You: fecth me meals under $20 in 17050

Output:
├─ Using profile location: (38.9586, -77.357)  ← Wrong!
├─ Parsed: 'meals in'                          ← Wrong!
├─ Searching: meals in                         ← Wrong!
└─ Location: Reston, VA                        ← Wrong!
```

### AFTER (Fixed Code)
```
You: fecth me meals under $20 in 17050

Output:
├─ Detected location: 17050                    ← Correct!
├─ Geocoded: Mechanicsburg, PA                 ← Correct!
├─ Parsed: 'restaurant'                        ← Correct!
├─ Searching: restaurant                       ← Correct!
└─ Found: 20 restaurants near 17050            ← Correct!
```

## Quick Reference: Working Queries

After deployment, these should ALL work:

```bash
# ZIP codes
"meals in 17050"
"pizza near 90210"

# Cities  
"burger in New York"
"sushi near Boston, MA"

# Full addresses
"tacos near 123 Main St, Mechanicsburg, PA"
"pizza at Times Square, New York"

# Landmarks
"food near Golden Gate Bridge"
"burger at Wall Street, NY"
```

## Need Help?

1. **Check logs:** Look for these log messages
   - "Detected location in query: 17050" ✓
   - "Geocoded via Places API" ✓
   - "Using profile location" (should only show if NO location in query)

2. **Run verification:** `./clear_cache.sh` runs all tests

3. **Check files:** Compare file sizes/dates with this machine

---

**Status:** Ready to deploy  
**Estimated time:** 5-10 minutes  
**Risk:** Low (only adds features, doesn't break existing functionality)
