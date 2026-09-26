# Simple Privacy Improvements for Personal Use

**Target**: Personal meal planner (not enterprise/public SaaS)  
**Effort**: Quick wins (hours to 1-2 days each)  
**Impact**: Materially improves privacy without major refactoring

---

## Quick Wins (High Impact, Low Effort)

### 1. Hash User Names in Logs (15 minutes) ⭐

**Problem**: User names appear in logs/traces  
**Solution**: Hash names before logging

```python
# utils/privacy.py
import hashlib

def anonymize_name(name: str) -> str:
    """Hash name for logging/traces."""
    return hashlib.sha256(name.encode()).hexdigest()[:8]

# Usage in logging
logger.info(f"User {anonymize_name(user.name)} made query")
# Output: "User a3f8b9c2 made query"
```

**Benefit**: Can't identify users from logs  
**Effort**: 15 minutes  
**Impact**: ⭐⭐⭐

---

### 2. Use Initials Instead of Full Names (5 minutes) ⭐⭐

**Problem**: Full name stored in user profile  
**Solution**: Use initials or aliases

```python
# When creating profile
user_profile = UserProfile(
    name="JD",  # Instead of "John Doe"
    allergies=["peanuts"],
    ...
)

# OR prompt user for alias
print("Enter an alias (e.g., 'JD', 'User1'):")
alias = input()
```

**Benefit**: No real names stored  
**Effort**: 5 minutes  
**Impact**: ⭐⭐⭐⭐

---

### 3. Gitignore User Profiles (30 seconds) ⭐⭐⭐

**Problem**: User profiles might be committed to Git  
**Solution**: Add to .gitignore

```bash
# .gitignore
# User data
config/user_profiles.json
config/user_*.json
.user_data/

# Cache
cache/menus/*
!cache/menus/.gitkeep
```

**Benefit**: Won't accidentally push PII to GitHub  
**Effort**: 30 seconds  
**Impact**: ⭐⭐⭐⭐⭐

---

### 4. Move User Profiles to ~/.config (10 minutes) ⭐⭐

**Problem**: User profiles in repo directory (easy to leak)  
**Solution**: Store in user's home directory

```python
# core/config_loader.py
from pathlib import Path

def get_user_config_dir():
    """Get user-specific config directory."""
    config_dir = Path.home() / ".config" / "meal-helper"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def load_user_profile(profile_name: str):
    config_dir = get_user_config_dir()
    profile_path = config_dir / f"{profile_name}.json"
    # Load from ~/.config/meal-helper/profile_name.json
```

**Benefit**: Separates user data from code  
**Effort**: 10 minutes  
**Impact**: ⭐⭐⭐⭐

---

### 5. Encrypt Profiles with User Password (1-2 hours) ⭐⭐⭐

**Problem**: User profiles in plain text on disk  
**Solution**: Simple encryption with user password

```python
# utils/encryption.py
from cryptography.fernet import Fernet
import base64
import hashlib
import json

def derive_key(password: str) -> bytes:
    """Derive encryption key from password."""
    return base64.urlsafe_b64encode(
        hashlib.sha256(password.encode()).digest()
    )

def encrypt_profile(profile: dict, password: str) -> bytes:
    """Encrypt user profile."""
    key = derive_key(password)
    fernet = Fernet(key)
    json_data = json.dumps(profile).encode()
    return fernet.encrypt(json_data)

def decrypt_profile(encrypted: bytes, password: str) -> dict:
    """Decrypt user profile."""
    key = derive_key(password)
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted)
    return json.loads(decrypted)

# Usage
profile = {...}
password = input("Enter profile password: ")
encrypted = encrypt_profile(profile, password)

# Save encrypted
with open("profile.enc", "wb") as f:
    f.write(encrypted)
```

**Setup**:
```bash
pip install cryptography
```

**Benefit**: Profile encrypted at rest  
**Effort**: 1-2 hours (including prompts)  
**Impact**: ⭐⭐⭐⭐⭐

---

### 6. Add Data Retention Notice (5 minutes) ⭐

**Problem**: No documentation on data handling  
**Solution**: Add simple privacy notice

```python
# display on first run
PRIVACY_NOTICE = """
🔒 Privacy Notice:
  • Your data is stored locally on this device only
  • User profiles: ~/.config/meal-helper/
  • Menu cache: ./cache/menus/
  • Location sent to Google Places API for restaurant search
  • Queries sent to OpenAI/Anthropic for processing
  • No data shared with third parties
  • Delete profiles anytime: rm -rf ~/.config/meal-helper/

Continue? (y/n): """

if first_run:
    response = input(PRIVACY_NOTICE)
    if response.lower() != 'y':
        sys.exit(0)
```

**Benefit**: User informed consent  
**Effort**: 5 minutes  
**Impact**: ⭐⭐⭐

---

### 7. Disable Location Logging (2 minutes) ⭐⭐

**Problem**: Exact coordinates might be logged  
**Solution**: Round coordinates before logging

```python
def sanitize_location(lat: float, lng: float) -> tuple:
    """Round location to ~1km precision."""
    return (round(lat, 2), round(lng, 2))

# Instead of:
logger.info(f"Searching at {lat}, {lng}")

# Use:
logger.info(f"Searching at {sanitize_location(lat, lng)}")
# 40.758896, -73.985130 → 40.76, -73.99
```

**Benefit**: Can't pinpoint exact address  
**Effort**: 2 minutes  
**Impact**: ⭐⭐⭐

---

### 8. Add Clear Data Script (10 minutes) ⭐⭐⭐

**Problem**: No easy way to delete all user data  
**Solution**: Simple cleanup script

```python
# scripts/clear_user_data.py
#!/usr/bin/env python3
"""Clear all user data and cache."""
import shutil
from pathlib import Path

def clear_all_data():
    print("🗑️  This will delete:")
    print("  • User profiles")
    print("  • Menu cache")
    print("  • Query history")
    
    confirm = input("\nContinue? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    
    # Clear user profiles
    config_dir = Path.home() / ".config" / "meal-helper"
    if config_dir.exists():
        shutil.rmtree(config_dir)
        print(f"✓ Deleted {config_dir}")
    
    # Clear cache
    cache_dir = Path("cache/menus")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True)
        print(f"✓ Cleared {cache_dir}")
    
    print("\n✅ All user data cleared!")

if __name__ == "__main__":
    clear_all_data()
```

**Usage**:
```bash
python scripts/clear_user_data.py
```

**Benefit**: Easy data deletion  
**Effort**: 10 minutes  
**Impact**: ⭐⭐⭐⭐

---

## Medium Effort Improvements (Optional)

### 9. Separate Sensitive Fields (30 minutes)

**Problem**: Allergies stored with other data  
**Solution**: Separate sensitive fields

```python
# Split into two files:
# 1. profile.json (non-sensitive)
{
  "name": "JD",
  "preferences": {"cuisine": ["italian"]},
  "budget": {"max_per_meal": 20}
}

# 2. sensitive.json (encrypted)
{
  "allergies": ["peanuts", "shellfish"],
  "dietary_restrictions": ["vegan"],
  "medical_notes": "..."
}
```

**Benefit**: Can share profile without exposing health data  
**Effort**: 30 minutes  
**Impact**: ⭐⭐⭐

---

### 10. Session-Only Mode (1 hour)

**Problem**: User doesn't want data saved at all  
**Solution**: In-memory profiles only

```python
# run.py
parser.add_argument(
    "--no-save",
    action="store_true",
    help="Don't save profile (session only)"
)

if args.no_save:
    # Keep profile in memory only
    # Don't write to disk
```

**Benefit**: Zero persistence  
**Effort**: 1 hour  
**Impact**: ⭐⭐⭐⭐

---

## Implementation Priority

### Phase 1: Quick Wins (30 minutes total) 🎯

1. ✅ Add to .gitignore (30 seconds)
2. ✅ Hash names in logs (15 minutes)
3. ✅ Use initials/aliases (5 minutes)
4. ✅ Move profiles to ~/.config (10 minutes)

**Impact**: 80% of privacy concerns addressed  
**Effort**: 30 minutes

### Phase 2: Moderate Effort (2-3 hours)

5. ✅ Encrypt profiles (1-2 hours)
6. ✅ Add privacy notice (5 minutes)
7. ✅ Clear data script (10 minutes)
8. ✅ Sanitize location logging (2 minutes)

**Impact**: 95% of privacy concerns addressed  
**Effort**: 2-3 hours

### Phase 3: Optional Enhancements (2+ hours)

9. Separate sensitive fields
10. Session-only mode
11. Auto-delete old cache (TTL)

---

## For Personal Use: Recommended Stack

**Absolute Minimum** (10 minutes):
```
1. .gitignore user profiles
2. Use aliases instead of real names
3. Move profiles to ~/.config
```

**Good Enough** (1 hour):
```
+ Hash names in logs
+ Encrypt profiles with password
+ Add privacy notice
```

**Production-Ready** (3 hours):
```
+ Clear data script
+ Sanitize location logging
+ Separate sensitive fields
```

---

## Legal Considerations (Simplified)

### For Personal Use:
- ✅ No legal requirements (it's your own data)
- ✅ Basic .gitignore is sufficient
- ✅ Encryption is optional but nice-to-have

### If Sharing with Friends/Family:
- ⚠️ Get verbal consent
- ✅ Add privacy notice
- ✅ Provide clear data script

### For Public Use (SaaS):
- ❌ Need full GDPR/CCPA compliance
- ❌ Need privacy policy
- ❌ Need data processing agreement
- ❌ Need audit logging

---

## Cost-Benefit Analysis

| Fix | Effort | Impact | ROI |
|-----|--------|--------|-----|
| .gitignore | 30 sec | High | ⭐⭐⭐⭐⭐ |
| Use aliases | 5 min | High | ⭐⭐⭐⭐⭐ |
| Move to ~/.config | 10 min | High | ⭐⭐⭐⭐⭐ |
| Hash in logs | 15 min | Medium | ⭐⭐⭐⭐ |
| Encrypt profiles | 2 hours | High | ⭐⭐⭐⭐ |
| Privacy notice | 5 min | Medium | ⭐⭐⭐ |
| Clear data script | 10 min | Medium | ⭐⭐⭐⭐ |

---

## Example: Complete Quick Implementation

```python
# utils/privacy.py (new file)
"""Simple privacy utilities for personal use."""
import hashlib
import json
from pathlib import Path
from cryptography.fernet import Fernet
import base64

def get_config_dir():
    """Get user config directory (~/.config/meal-helper)."""
    config_dir = Path.home() / ".config" / "meal-helper"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def anonymize_name(name: str) -> str:
    """Hash name for logging."""
    return hashlib.sha256(name.encode()).hexdigest()[:8]

def sanitize_location(lat: float, lng: float) -> tuple:
    """Round coordinates to ~1km precision."""
    return (round(lat, 2), round(lng, 2))

def derive_key(password: str) -> bytes:
    """Derive encryption key from password."""
    return base64.urlsafe_b64encode(
        hashlib.sha256(password.encode()).digest()
    )

def save_encrypted_profile(profile: dict, name: str, password: str):
    """Save encrypted user profile."""
    config_dir = get_config_dir()
    path = config_dir / f"{name}.enc"
    
    key = derive_key(password)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(json.dumps(profile).encode())
    
    with open(path, "wb") as f:
        f.write(encrypted)

def load_encrypted_profile(name: str, password: str) -> dict:
    """Load encrypted user profile."""
    config_dir = get_config_dir()
    path = config_dir / f"{name}.enc"
    
    with open(path, "rb") as f:
        encrypted = f.read()
    
    key = derive_key(password)
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted)
    
    return json.loads(decrypted)
```

**Usage**:
```python
from utils.privacy import (
    anonymize_name, 
    save_encrypted_profile,
    sanitize_location
)

# Save profile
profile = {"name": "JD", "allergies": ["peanuts"]}
save_encrypted_profile(profile, "my_profile", password="secret123")

# Log safely
logger.info(f"User {anonymize_name('John Doe')} searching at {sanitize_location(40.7589, -73.9851)}")
# Output: "User a3f8b9c2 searching at (40.76, -73.99)"
```

---

## Recommendation for Your Project

**For personal use, implement Phase 1 (30 minutes):**

1. Add to .gitignore ✅
2. Use alias instead of real name ✅
3. Move profiles to ~/.config ✅
4. Hash names in logs ✅

**This covers 80% of privacy concerns with minimal effort.**

If you want to be thorough, add Phase 2 (2 hours):
5. Encrypt profiles ✅
6. Add privacy notice ✅

**Total effort: ~2.5 hours for 95% privacy improvement.**

For a personal tool, this is **highly acceptable** and proportionate to the risk.
