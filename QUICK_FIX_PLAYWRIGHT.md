# Quick Fix: Playwright Installation

## ❌ The Error

```bash
Error: Playwright executable doesn't exist at ...
Run: playwright install
```

## ✅ The Fix (30 seconds)

```bash
# Navigate to project
cd /home/pkalva/my-experiments/meal-helper-assistant

# Activate virtual environment
source .venv/bin/activate

# Install Playwright browsers
playwright install
```

**That's it!** Now run your app:
```bash
python run.py chat --profile example_user
```

---

## 🎯 Why This Happens

**Playwright has TWO installation steps:**

| Step | Command | What it does | Automatic? |
|------|---------|--------------|------------|
| 1 | `pip install playwright` | Installs Python package | ✅ Yes (in requirements.txt) |
| 2 | `playwright install` | Downloads browser binaries (~500MB) | ❌ **No - manual step!** |

**You did step 1** (via `pip install -r requirements.txt`)  
**But missed step 2** ← That's the error

---

## 🚀 Better: Use Setup Script

I created a script that does EVERYTHING automatically:

```bash
cd /home/pkalva/my-experiments/meal-helper-assistant
./setup_environment.sh
```

This will:
1. Create/activate virtual environment
2. Install Python packages (`pip install -r requirements.txt`)
3. **Install Playwright browsers** (`playwright install`) ← The missing step!
4. Verify everything works

---

## 📋 For Your Other Laptop

When you pull the latest code to another machine:

**Option 1: Quick fix**
```bash
source .venv/bin/activate
playwright install
```

**Option 2: Complete setup**
```bash
./setup_environment.sh
```

---

## 🔍 Verify It Worked

```bash
# List installed browsers
playwright list

# Should show:
# chromium 1091 (installed)
# firefox 1450 (installed)  
# webkit 2034 (installed)
```

---

## 📖 More Info

- **Complete guide:** `PLAYWRIGHT_SETUP.md`
- **Installation guide:** `INSTALL.md` (now updated with Playwright steps)

---

## ✨ Summary

**Error message:**
```
Run: playwright install
```

**Literally just run that:**
```bash
playwright install
```

**Done!** 🎉

---

**Created:** 2024-09-24  
**Issue:** Playwright browsers not installed  
**Time to fix:** 30 seconds  
**Solution:** Run `playwright install`
