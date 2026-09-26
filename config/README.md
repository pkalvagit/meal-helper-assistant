# Configuration Guide

## User Profiles

### Quick Setup

1. **Copy the example template**:
   ```bash
   cp config/user_profiles.json.example config/user_profiles.json
   ```

2. **Edit with your details**:
   ```bash
   nano config/user_profiles.json  # or vim, code, etc.
   ```

3. **Update basic fields**:
   - `name`: Use an alias (e.g., "JD", "User1", "Me")
   - `allergies`: List of allergens to avoid
   - `dietary_restrictions`: Diet preferences
   - `budget.max_per_meal`: Your budget per meal
   - `location`: Your default location (optional)

### Example User Profiles Included

The template includes 5 ready-to-use profiles:

| Profile | Use Case | Allergies | Budget |
|---------|----------|-----------|--------|
| `example_user` | General with restrictions | Peanuts, Shellfish | $15 |
| `vegan_user` | Vegan diet | None | $20 |
| `gluten_free_user` | Gluten-free | Gluten | $18 |
| `keto_user` | Keto/low-carb | None | $25 |
| `budget_conscious` | Budget-focused | None | $10 |

### Quick Customization

**Minimal setup** (copy and edit 3 fields):
```json
{
  "my_profile": {
    "name": "YourAlias",           // ← Change this
    "allergies": ["peanuts"],      // ← Change this
    "budget": {
      "max_per_meal": 15.00        // ← Change this
    }
  }
}
```

**Full setup** (all fields):
```json
{
  "my_profile": {
    "name": "YourAlias",
    "allergies": ["peanuts", "shellfish"],
    "dietary_restrictions": ["vegan", "gluten_free"],
    "preferences": {
      "high_protein": true,
      "organic": true
    },
    "budget": {
      "max_per_meal": 20.00,
      "currency": "USD"
    },
    "location": {
      "default_lat": 40.7589,
      "default_lng": -73.9851,
      "default_radius": 5000
    },
    "nutrition_targets": {
      "min_protein_g": 25,
      "max_calories": 800
    }
  }
}
```

### Common Dietary Restrictions

Use these exact values for `dietary_restrictions`:
- `"vegan"` - No animal products
- `"vegetarian"` - No meat/fish
- `"gluten_free"` - No gluten
- `"dairy_free"` - No dairy
- `"keto"` - Keto diet
- `"low_carb"` - Low carb
- `"paleo"` - Paleo diet
- `"halal"` - Halal only
- `"kosher"` - Kosher only
- `"no_beef"` - No beef
- `"no_pork"` - No pork

### Common Allergens

Use these for `allergies`:
- `"peanuts"` - Peanuts
- `"tree_nuts"` - Almonds, cashews, walnuts
- `"shellfish"` - Shrimp, crab, lobster
- `"fish"` - All fish
- `"dairy"` - Milk, cheese
- `"eggs"` - Eggs
- `"soy"` - Soy products
- `"wheat"` - Wheat/gluten
- `"sesame"` - Sesame seeds

### Usage

Run with your profile:
```bash
python run.py chat --profile my_profile
```

Or use one of the examples:
```bash
python run.py chat --profile vegan_user
python run.py chat --profile keto_user
```

### Privacy Note

🔒 **Your profile is stored locally only**:
- File: `config/user_profiles.json`
- **Never committed to Git** (protected by .gitignore)
- Only you can access it
- Location sent to Google Places API for restaurant search
- Queries sent to OpenAI/Anthropic for processing

### Tips

1. **Use aliases**: Use "JD" instead of "John Doe"
2. **Start simple**: Just set name, allergies, and budget
3. **Test with example profiles first**: Try `example_user` before creating your own
4. **Multiple profiles**: Create different profiles for different scenarios (work lunch, date night, etc.)

### Troubleshooting

**Profile not found**:
```bash
# Make sure file exists
ls config/user_profiles.json

# If not, copy from example
cp config/user_profiles.json.example config/user_profiles.json
```

**Invalid JSON**:
```bash
# Validate JSON syntax
python -m json.tool config/user_profiles.json
```

**Need help**:
```bash
python run.py --help
```

---

## LLM Configuration

See `llm_config.yaml` for model selection (Claude vs OpenAI).

## Environment Variables

See `.env.example` for required API keys.
