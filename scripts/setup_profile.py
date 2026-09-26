#!/usr/bin/env python3
"""
Quick profile setup helper.
Creates a personalized user profile from template.
"""
import json
from pathlib import Path

def setup_profile():
    """Interactive profile setup."""
    print("🍽️  Meal Helper - Profile Setup")
    print("=" * 50)
    print()

    # Check if file exists
    config_dir = Path(__file__).parent.parent / "config"
    profiles_file = config_dir / "user_profiles.json"
    example_file = config_dir / "user_profiles.json.example"

    # Copy example if doesn't exist
    if not profiles_file.exists():
        if example_file.exists():
            print("📋 Creating user_profiles.json from template...")
            import shutil
            shutil.copy(example_file, profiles_file)
            print("✓ Created config/user_profiles.json")
        else:
            print("❌ Error: user_profiles.json.example not found!")
            return

    print("Let's create your profile!")
    print()

    # Get basic info
    profile_name = input("Profile name (e.g., 'my_profile'): ").strip()
    if not profile_name:
        profile_name = "my_profile"

    alias = input("Your alias (e.g., 'JD', 'User1'): ").strip()
    if not alias:
        alias = "User1"

    print()
    print("🔍 Allergies (comma-separated, or press Enter to skip):")
    print("   Examples: peanuts, shellfish, dairy, gluten")
    allergies_input = input("Your allergies: ").strip()
    allergies = [a.strip().lower() for a in allergies_input.split(",") if a.strip()]

    print()
    print("🥗 Dietary restrictions (comma-separated, or press Enter to skip):")
    print("   Examples: vegan, gluten_free, keto, halal")
    restrictions_input = input("Your restrictions: ").strip()
    restrictions = [r.strip().lower() for r in restrictions_input.split(",") if r.strip()]

    print()
    budget = input("Budget per meal (e.g., 15, 20, 25) [default: 15]: ").strip()
    try:
        budget = float(budget) if budget else 15.0
    except ValueError:
        budget = 15.0

    # Create profile
    new_profile = {
        "name": alias,
        "allergies": allergies,
        "dietary_restrictions": restrictions,
        "preferences": {},
        "budget": {
            "max_per_meal": budget,
            "currency": "USD"
        }
    }

    # Load existing profiles
    try:
        with open(profiles_file, "r") as f:
            profiles = json.load(f)
    except Exception as e:
        print(f"⚠️  Error reading profiles: {e}")
        profiles = {}

    # Add new profile
    profiles[profile_name] = new_profile

    # Save
    try:
        with open(profiles_file, "w") as f:
            json.dump(profiles, f, indent=2)

        print()
        print("=" * 50)
        print("✅ Profile created successfully!")
        print()
        print(f"Profile name: {profile_name}")
        print(f"Alias: {alias}")
        print(f"Allergies: {', '.join(allergies) if allergies else 'None'}")
        print(f"Restrictions: {', '.join(restrictions) if restrictions else 'None'}")
        print(f"Budget: ${budget}/meal")
        print()
        print("📝 To use this profile:")
        print(f"   python run.py chat --profile {profile_name}")
        print()
        print("✏️  To edit:")
        print(f"   nano config/user_profiles.json")
        print()

    except Exception as e:
        print(f"❌ Error saving profile: {e}")

if __name__ == "__main__":
    try:
        setup_profile()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
