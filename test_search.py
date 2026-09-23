#!/usr/bin/env python3
"""
Test restaurant search tools.
"""
from dotenv import load_dotenv
load_dotenv()

from tools.search_tool import search_restaurants_nearby, search_restaurants_by_query

print("Testing restaurant search...")
print()

# Test 1: Search nearby
print("1. Testing search_restaurants_nearby...")
try:
    results = search_restaurants_nearby.invoke({
        "lat": 38.9586,
        "lng": -77.3570,
        "radius": 5000,
        "types": "restaurant",
        "max_results": 3
    })

    if results and len(results) > 0:
        if "error" in results[0]:
            print(f"   ❌ Error: {results[0]['error']}")
        else:
            print(f"   ✅ Found {len(results)} restaurants")
            for r in results[:2]:
                print(f"      - {r.get('name')} ({r.get('rating', 'N/A')} stars)")
    else:
        print("   ⚠️  No results returned")
except Exception as e:
    print(f"   ❌ Exception: {e}")

print()

# Test 2: Search by query
print("2. Testing search_restaurants_by_query...")
try:
    results = search_restaurants_by_query.invoke({
        "query": "italian restaurant",
        "lat": 38.9586,
        "lng": -77.3570,
        "radius": 5000,
        "max_results": 3
    })

    if results and len(results) > 0:
        if "error" in results[0]:
            print(f"   ❌ Error: {results[0]['error']}")
        else:
            print(f"   ✅ Found {len(results)} restaurants")
            for r in results[:2]:
                print(f"      - {r.get('name')} at {r.get('address')}")
    else:
        print("   ⚠️  No results returned")
except Exception as e:
    print(f"   ❌ Exception: {e}")

print()
print("If both tests passed, the search tools are working!")
print("Now try: python run.py chat --profile example_user")
