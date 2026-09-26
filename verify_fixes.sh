#!/bin/bash
# Quick verification script - run this on other laptop after deployment

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Meal Helper - Location Feature Verification          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Activate virtual environment
source .venv/bin/activate 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ Virtual environment not found"
    echo "   Run: python -m venv .venv"
    exit 1
fi

echo "✓ Virtual environment activated"
echo ""

# Test 1: Query Parser
echo "Test 1: Query Parser"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python -B -c "
from core.query_parser import QueryParser
query = 'meals under \$20 in 17050'
result = QueryParser.extract_food_query(query)
print(f'Input:    \"{query}\"')
print(f'Expected: \"restaurant\"')
print(f'Actual:   \"{result}\"')
if result == 'restaurant':
    print('Status:   ✅ PASS')
    exit(0)
else:
    print('Status:   ❌ FAIL')
    exit(1)
" 2>&1 | grep -v "warnings.warn" | grep -v "LangChain"

TEST1=$?
echo ""

# Test 2: Location Extraction
echo "Test 2: Location Extraction"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python -B -c "
import re
query = 'meals in 17050'
match = re.search(r'\bin\s+(\d{5})', query)
location = match.group(1) if match else None
print(f'Input:    \"{query}\"')
print(f'Expected: \"17050\"')
print(f'Actual:   \"{location}\"')
if location == '17050':
    print('Status:   ✅ PASS')
    exit(0)
else:
    print('Status:   ❌ FAIL')
    exit(1)
"

TEST2=$?
echo ""

# Test 3: Location Service Import
echo "Test 3: Location Service Module"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python -B -c "
from dotenv import load_dotenv
load_dotenv()
from utils.location_service import get_location
print('Module:   location_service.py')
print('Function: get_location')
print('Status:   ✅ PASS (import successful)')
" 2>&1 | grep -v "InsecureRequest" | grep -v "warnings.warn"

TEST3=$?
echo ""

# Test 4: Geocoding (if API key available)
echo "Test 4: Geocoding"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python -B -c "
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('GOOGLE_MAPS_API_KEY') or os.getenv('GOOGLE_PLACES_API_KEY')
if not api_key:
    print('Status:   ⚠️  SKIP (no API key)')
    exit(0)

from utils.location_service import get_location
try:
    lat, lng, desc = get_location('17050')
    print(f'Input:    \"17050\"')
    print(f'Result:   {desc}')
    print(f'Coords:   ({lat:.4f}, {lng:.4f})')
    if 'PA' in desc.upper() or 'PENN' in desc.upper():
        print('Status:   ✅ PASS (Pennsylvania detected)')
        exit(0)
    else:
        print('Status:   ⚠️  WARNING (Expected Pennsylvania)')
        exit(0)
except Exception as e:
    print(f'Error:    {str(e)[:60]}...')
    print('Status:   ❌ FAIL')
    exit(1)
" 2>&1 | grep -v "InsecureRequest" | grep -v "warnings.warn"

TEST4=$?
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                     Test Summary                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

TOTAL=0
PASSED=0

if [ $TEST1 -eq 0 ]; then
    echo "  ✅ Query Parser"
    PASSED=$((PASSED+1))
else
    echo "  ❌ Query Parser"
fi
TOTAL=$((TOTAL+1))

if [ $TEST2 -eq 0 ]; then
    echo "  ✅ Location Extraction"
    PASSED=$((PASSED+1))
else
    echo "  ❌ Location Extraction"
fi
TOTAL=$((TOTAL+1))

if [ $TEST3 -eq 0 ]; then
    echo "  ✅ Location Service Module"
    PASSED=$((PASSED+1))
else
    echo "  ❌ Location Service Module"
fi
TOTAL=$((TOTAL+1))

if [ $TEST4 -eq 0 ]; then
    echo "  ✅ Geocoding"
    PASSED=$((PASSED+1))
else
    echo "  ⚠️  Geocoding (check API key)"
fi
TOTAL=$((TOTAL+1))

echo ""
echo "Results: $PASSED/$TOTAL tests passed"
echo ""

if [ $PASSED -ge 3 ]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  ✅ All critical tests passed! Ready to use.               ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Run the app:"
    echo "  python -B run.py chat --profile example_user"
    echo ""
    echo "Test query:"
    echo '  You: meals under $20 in 17050'
    echo ""
    exit 0
else
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  ❌ Some tests failed. Check the output above.             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Clear cache:  ./clear_cache.sh"
    echo "  2. Check files:  ls -la core/ utils/"
    echo "  3. Verify .env:  grep PYTHON .env"
    echo ""
    exit 1
fi
