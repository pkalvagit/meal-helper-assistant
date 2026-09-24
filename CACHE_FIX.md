# Python Cache Issue - Quick Fix

## Problem

When you update code, Python might still run old cached `.pyc` files, causing your changes to not take effect.

**Symptoms:**
```
Using profile location: (38.9586, -77.357)  ← Should extract ZIP from query
Parsed query: '... in 17050' -> 'meals in'  ← Should be 'restaurant'
```

## Quick Fix (Run This)

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant

# Option 1: Use the helper script (easiest)
./clear_cache.sh

# Option 2: Manual clearing
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
```

## Permanent Fix (Already Done)

I added this to your `.env` file:
```env
PYTHONDONTWRITEBYTECODE=1  # Prevent .pyc cache files
```

This prevents Python from creating cache files in the future.

## How to Run After Fixing

```bash
# Make sure you're in the project directory
cd /home/pkalva/my-experiments/meal-helper-assistant

# Activate virtual environment
source .venv/bin/activate

# Run with cache disabled (recommended during development)
python -B run.py chat --profile example_user

# Or just run normally (after setting PYTHONDONTWRITEBYTECODE=1)
python run.py chat --profile example_user
```

## Test It Works

After clearing cache, this query should work:
```
You: fecth me meals under $20 in 17050
```

**Expected behavior:**
```
✓ Detected location in query: 17050
✓ Geocoded: Hampden Township, PA 17050, USA
✓ Searching for: restaurant
✓ Found 20 restaurants near Mechanicsburg, PA
```

**Old behavior (if cache not cleared):**
```
✗ Using profile location: (38.9586, -77.357)  [Reston, VA]
✗ Parsed query: 'meals in'
✗ Searching for: meals in
```

## For Multiple Machines

If you're testing on different laptops:

1. **Pull latest code:**
   ```bash
   cd /home/pkalva/my-experiments/meal-helper-assistant
   git pull  # or sync your files
   ```

2. **Clear cache on EACH machine:**
   ```bash
   ./clear_cache.sh
   ```

3. **Or run with -B flag:**
   ```bash
   python -B run.py chat --profile example_user
   ```

## Verification Test

Run this to verify the fixes are active:
```bash
source .venv/bin/activate
python -B -c "
from core.query_parser import QueryParser
query = 'meals under \$20 in 17050'
result = QueryParser.extract_food_query(query)
print('Query:', query)
print('Parsed:', result)
print('Status:', '✅ PASS' if result == 'restaurant' else '❌ FAIL')
" 2>&1 | grep -v warnings
```

**Expected output:**
```
Query: meals under $20 in 17050
Parsed: restaurant
Status: ✅ PASS
```

## Why This Happens

Python compiles `.py` files to `.pyc` bytecode for faster loading:
```
your_code.py  →  __pycache__/your_code.cpython-314.pyc
```

When you edit `your_code.py`, Python sometimes doesn't notice and keeps using the old `.pyc` file.

**Solution:** Delete cache or disable caching during development.

## Development Best Practices

**During development:**
```bash
# Always use -B flag to avoid cache issues
python -B run.py chat --profile example_user
```

**Or set in your shell profile (~/.bashrc or ~/.zshrc):**
```bash
export PYTHONDONTWRITEBYTECODE=1
```

**For production:**
Remove the flag for better performance (caching is good in production).

---

**Status:** ✅ Fixed - Cache clearing script created  
**Script:** `./clear_cache.sh`  
**Setting:** Added `PYTHONDONTWRITEBYTECODE=1` to `.env`
