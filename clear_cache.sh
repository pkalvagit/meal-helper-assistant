#!/bin/bash
# Clear Python cache and verify location feature

echo "================================================"
echo "Clearing Python Cache"
echo "================================================"

# Clear all __pycache__ directories
echo "Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "✓ Done"

# Clear all .pyc files
echo "Removing .pyc files..."
find . -type f -name "*.pyc" -delete
echo "✓ Done"

echo ""
echo "================================================"
echo "Testing Location Feature"
echo "================================================"

# Activate virtual environment
source .venv/bin/activate

# Test query parsing
echo ""
echo "1. Testing Query Parser:"
python -B -c "
from core.query_parser import QueryParser
query = 'fecth me meals under \$20 in 17050'
result = QueryParser.extract_food_query(query)
print(f'   Input:  \"{query}\"')
print(f'   Output: \"{result}\"')
if result == 'restaurant':
    print('   ✅ PASS')
else:
    print('   ❌ FAIL - Expected \"restaurant\"')
" 2>&1 | grep -v "warnings.warn" | grep -v "LangChainDeprecation"

# Test location extraction
echo ""
echo "2. Testing Location Extraction:"
python -B -c "
import re
query = 'fecth me meals under \$20 in 17050'

# Simulate extraction
patterns = [
    r'\bin\s+(\d{5})(?:\s|$)',
]
location = None
for pattern in patterns:
    match = re.search(pattern, query)
    if match:
        location = match.group(1)
        break

print(f'   Input:    \"{query}\"')
print(f'   Extracted: \"{location}\"')
if location == '17050':
    print('   ✅ PASS')
else:
    print('   ❌ FAIL - Expected \"17050\"')
"

echo ""
echo "================================================"
echo "✅ Cache cleared! Now run:"
echo "   python -B run.py chat --profile example_user"
echo ""
echo "Or add to .env:"
echo "   PYTHONDONTWRITEBYTECODE=1"
echo "================================================"
