#!/usr/bin/env python3
"""
Quick test to verify UserProfile loads correctly.
"""
from core.models import UserProfile
import json

print("Testing UserProfile loading...")

with open('config/user_profiles.json') as f:
    profiles = json.load(f)

try:
    profile = UserProfile(**profiles['example_user'])
    print("✅ UserProfile loads successfully!")
    print(f"\nProfile Details:")
    print(f"  Name: {profile.name}")
    print(f"  Budget: ${profile.budget.max_per_meal} {profile.budget.currency}")
    print(f"  Allergies: {', '.join(profile.allergies) or 'None'}")
    print(f"  Restrictions: {', '.join(profile.dietary_restrictions) or 'None'}")
    print(f"  Preferences: {profile.preferences}")
    print("\n✅ All validation passed!")
    print("\nNow try: python run.py chat --profile example_user")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
