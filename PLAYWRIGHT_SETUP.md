# Playwright Setup Guide

## The Problem

```bash
$ python run.py chat --profile example_user
...
Error: Playwright executable doesn't exist
Run: playwright install
```

## Why This Happens

Playwright has a **two-step installation**:

1. ✅ **Python package** → Installed via `pip install playwright` (in requirements.txt)
2. ❌ **Browser binaries** → Must be installed separately with `playwright install`

The Python package is just a wrapper. The actual browsers (Chromium, Firefox, WebKit) must be downloaded separately (~500MB).

## Quick Fix

### Option 1: Use the Setup Script (Easiest)

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant
./setup_environment.sh
```

This will:
- Create/activate virtual environment
- Install all Python packages
- **Download Playwright browsers** ← The missing step!

### Option 2: Manual Installation

```bash
# Activate virtual environment
source .venv/bin/activate

# Install Playwright browsers
playwright install

# Or install only Chromium (lighter)
playwright install chromium
```

### Option 3: Install System Dependencies First (If Needed)

On some Linux systems, you need system libraries first:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2

# Or let Playwright install them automatically
playwright install-deps
```

## Verify Installation

```bash
source .venv/bin/activate

# List installed browsers
playwright list

# Should show:
# chromium 1091 (installed)
# firefox 1450 (installed)
# webkit 2034 (installed)
```

## Testing

```bash
# Test browser launch
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://example.com')
    print('✅ Playwright works!')
    browser.close()
"
```

## What Gets Installed

| Browser | Size | Purpose |
|---------|------|---------|
| **Chromium** | ~150MB | Primary browser (Chrome-based) |
| **Firefox** | ~90MB | Backup browser |
| **WebKit** | ~70MB | Safari engine (macOS) |

**Total:** ~310MB + dependencies (~200MB) = **~500MB**

## Where Are Browsers Stored?

```bash
# Linux/WSL
~/.cache/ms-playwright/

# macOS
~/Library/Caches/ms-playwright/

# Windows
%USERPROFILE%\AppData\Local\ms-playwright\
```

## Playwright in This Project

### Used For:
- **Menu scraping** - Renders JavaScript-heavy restaurant websites
- **Dynamic content** - Waits for menus to load
- **Navigation** - Finds "Menu" links automatically

### Configuration (`.env`):
```env
SCRAPE_RENDER_WAIT_MS=8000      # Wait for page load
SCRAPE_NAV_TIMEOUT_MS=45000     # Navigation timeout
SCRAPE_MAX_DEPTH=2              # How deep to search
```

## Troubleshooting

### Error: "Executable doesn't exist at ..."

**Solution:**
```bash
playwright install chromium
```

### Error: "Host system is missing dependencies"

**Solution:**
```bash
# Install system dependencies
playwright install-deps

# Or install manually (Ubuntu/Debian)
sudo apt-get install -y libnss3 libatk1.0-0 libgbm1 ...
```

### Error: "Browser closed" or "Target closed"

**Possible causes:**
1. System out of memory
2. Missing system dependencies
3. Corporate proxy blocking downloads

**Solution:**
```bash
# Check available memory
free -h

# Install dependencies
playwright install-deps

# Test with headless mode disabled (shows browser window)
# Add to your code: browser = p.chromium.launch(headless=False)
```

### Error: "Cannot connect to browser"

**Solution:**
```bash
# Remove and reinstall browsers
rm -rf ~/.cache/ms-playwright/
playwright install
```

## Lighter Alternative: Chromium Only

If you have limited disk space:

```bash
# Install only Chromium (smallest footprint)
playwright install chromium

# Update utils/menu_url_finder.py to use only chromium
# (already defaults to chromium)
```

## Development vs Production

### Development (Local Testing):
```bash
# Install all browsers for testing
playwright install
```

### Production (Docker/Server):
```bash
# Install only Chromium + dependencies
playwright install chromium
playwright install-deps chromium
```

**Dockerfile example:**
```dockerfile
FROM python:3.11-slim

# Install Playwright system dependencies
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libgbm1 && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
```

## Adding to requirements.txt Won't Help

**Why not add `playwright install` to requirements.txt?**

Because `requirements.txt` only installs Python packages. Browser binaries must be installed via a **post-install script**.

**Options:**

### Option A: Post-Install Script (setup_environment.sh)
```bash
#!/bin/bash
pip install -r requirements.txt
playwright install
```

### Option B: Add to README
```markdown
## Installation
pip install -r requirements.txt
playwright install  # Don't forget this!
```

### Option C: Use Makefile
```makefile
install:
    pip install -r requirements.txt
    playwright install
```

## Summary

**The Fix:**
```bash
source .venv/bin/activate
playwright install
```

**Why It's Needed:**
- Playwright Python package = just a wrapper
- Actual browsers = separate download (~500MB)
- This is by design (keeps pip package small)

**Verification:**
```bash
playwright list
# Should show 3 installed browsers
```

---

**Created:** 2024-09-24  
**Issue:** Playwright browsers not auto-installed  
**Status:** ✅ Fixed with setup_environment.sh script
