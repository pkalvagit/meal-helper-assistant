#!/usr/bin/env python3
"""
Quick test to verify all imports work.
"""

print("Testing imports...")

try:
    print("1. Core imports...")
    from core.models import UserProfile, Intent, GuardrailResult
    print("   ✓ Models")

    from core.llm_factory import get_llm_factory
    print("   ✓ LLM Factory")

    from core.guardrails import RestaurantGuardrail
    print("   ✓ Guardrails")

    from core.simple_agent import SimpleMealHelperAgent
    print("   ✓ Simple Agent")

    print("\n2. Tool imports...")
    from tools.search_tool import search_restaurants_nearby
    print("   ✓ Search tools")

    from tools.menu_tool import get_restaurant_menu
    print("   ✓ Menu tools")

    from tools.filter_tool import filter_menu_by_user_profile
    print("   ✓ Filter tools")

    print("\n3. Testing factory...")
    factory = get_llm_factory()
    print(f"   ✓ Factory created")
    print(f"   Primary provider: {factory.config['primary']['provider']}")
    print(f"   Guardrail provider: {factory.config['guardrail']['provider']}")

    print("\n✅ All imports successful!")
    print("\nNow try: python run.py chat --profile example_user")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
