# Economic Terminal - Complete Setup Guide

This guide walks you through setting up your economic monitoring terminal from scratch. Written for someone with basic Python experience.

**Estimated time**: 2-3 hours for initial setup

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Phase 1: Local Setup](#phase-1-local-setup-week-1)
3. [Phase 2: Cloud Deployment](#phase-2-cloud-deployment-week-2)
4. [Phase 3: Customization](#phase-3-customization-weeks-3-4)
5. [Troubleshooting](#troubleshooting)
6. [Maintenance](#maintenance)

---

## Prerequisites

### Software Installation

#### 1. Install Python 3.11+

**Windows:**
- Download from https://www.python.org/downloads/
- Run installer, **check "Add Python to PATH"**
- Verify: Open Command Prompt, type `python --version`

**Mac:**
```bash
# Using Homebrew
brew install python@3.11

# Verify
python3 --version
```

#### 2. Install Node.js 18+

- Download from https://nodejs.org/ (LTS version)
- Run installer
- Verify: `node --version` and `npm --version`

#### 3. Install Git

- Download from https://git-scm.com/
- Run installer with default options
- Verify: `git --version`

### Create API Accounts (All Free)

| Service | Purpose | Link | Notes |
|---------|---------|------|-------|
| Alpha Vantage | FX rates | [Get Key](https://www.alphavantage.co/support/#api-key) | 500 calls/day |
| FRED | Economic data | [Get Key](https://fred.stlouisfed.org/docs/api/api_key.html) | Unlimited |
| SendGrid | Email alerts | [Sign Up](https://sendgrid.com/free/) | 100 emails/day |
| Render.com | Hosting | [Sign Up](https://render.com/) | Free tier |
| GitHub | Code storage | [Sign Up](https://github.com/) | Optional but recommended |

---

## Phase 1: Local Setup (Week 1)

### Step 1: Download and Extract the Code

```bash
# Navigate to your projects folder
cd ~/Documents  # or wherever you keep projects

# If you have a zip file
unzip economic-terminal.zip
cd economic-terminal

# Or if cloning from GitHub
git clone https://github.com/yourusername/economic-terminal.git
cd economic-terminal
```

### Step 2: Create Python Virtual Environment

This keeps your project dependencies isolated.

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Mac/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# You should see (venv) at the start of your terminal prompt
```

**Important**: Always activate the virtual environment before working on the project!

### Step 3: Install Python Dependencies

```bash
# Make sure venv is activated (you see (venv) in prompt)
pip install -r requirements.txt

# This might take a few minutes
```

### Step 4: Configure Environment Variables

```bash
# Copy the template
cp .env.example .env

# Now edit .env with your API keys
# Use any text editor (VS Code, Notepad, TextEdit, etc.)
```

Edit the `.env` file and add your keys:

```env
# Database - use SQLite for local development
DATABASE_URL=sqlite:///./economic_data.db

# Add your API keys
ALPHA_VANTAGE_KEY=paste_your_key_here
FRED_API_KEY=paste_your_key_here
SENDGRID_API_KEY=paste_your_key_here

# Your email addresses
SENDGRID_FROM_EMAIL=your.email@gmail.com
RECIPIENT_EMAIL=your.work.email@company.com
```

### Step 5: Initialize the Database

```bash
python scripts/init_db.py
```

Expected output:
```
============================================================
ECONOMIC TERMINAL - DATABASE INITIALIZATION
============================================================

Database: sqlite:///./economic_data.db...
✓ Database connection successful

Creating database tables...
  ✓ Table: fx_rates
  ✓ Table: yield_curves
  ✓ Table: credit_spreads
  ✓ Table: economic_releases
  ✓ Table: news_articles
  ✓ Table: risk_alerts
  ✓ Table: system_health

============================================================
DATABASE INITIALIZATION COMPLETE
============================================================
```

### Step 6: Test the Modules

```bash
python scripts/test_modules.py
```

This tests each component:
- Database connection
- FX rate fetching
- Yield curve fetching
- Risk detection

If a test fails, check your API keys in `.env`.

### Step 7: Run the Backend

```bash
# Make sure venv is activated
uvicorn backend.main:app --reload
```

Expected output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**Test it**: Open http://127.0.0.1:8000 in your browser. You should see:
```json
{
  "name": "Economic Terminal API",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs"
}
```

Visit http://127.0.0.1:8000/docs to see the interactive API documentation!

### Step 8: Run the Frontend (Optional)

Open a **new terminal window** (keep the backend running):

```bash
cd frontend
npm install
npm start
```

This will open http://localhost:3000 with the React dashboard.

---

## Phase 2: Cloud Deployment (Week 2)

### Step 1: Push Code to GitHub

```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Economic Terminal"

# Create a new repository on GitHub.com
# Then connect your local code:
git remote add origin https://github.com/YOUR_USERNAME/economic-terminal.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Render.com

1. **Log in to Render.com**

2. **Create PostgreSQL Database**:
   - Click "New +" → "PostgreSQL"
   - Name: `economic-terminal-db`
   - Plan: **Free**
   - Click "Create Database"
   - Wait for it to be ready (~2 minutes)
   - **Copy the "External Database URL"** (you'll need this)

3. **Create Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - Name: `economic-terminal`
     - Environment: Python
     - Build Command:
       ```
       pip install -r requirements.txt
       ```
     - Start Command:
       ```
       python scripts/init_db.py && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
       ```

4. **Add Environment Variables**:
   Click "Environment" and add each variable:
   
   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | (paste the PostgreSQL URL from step 2) |
   | `ALPHA_VANTAGE_KEY` | (your key) |
   | `FRED_API_KEY` | (your key) |
   | `SENDGRID_API_KEY` | (your key) |
   | `SENDGRID_FROM_EMAIL` | (your email) |
   | `RECIPIENT_EMAIL` | (your work email) |
   | `PYTHON_VERSION` | `3.11.0` |

5. **Deploy**:
   - Click "Create Web Service"
   - Wait 5-10 minutes for deployment
   - Your app will be live at: `https://economic-terminal.onrender.com`

### Step 3: Verify Deployment

```bash
# Test your live API
curl https://economic-terminal.onrender.com/api/health

# Should return:
# {"status": "healthy", "timestamp": "..."}
```

---

## Phase 3: Customization (Weeks 3-4)

### Adjust FX Risk Thresholds

Edit `modules/risk_detector/config.py`:

```python
ALERT_THRESHOLDS = {
    # Lower to 0.8% if you want more alerts
    'FX_HIGH': 0.8,
    'FX_CRITICAL': 1.5,
    
    # Adjust for specific currencies
    'FX_MXN_HIGH': 1.5,
    'FX_MXN_CRITICAL': 3.0,
}
```

### Add Critical Keywords

Edit `modules/risk_detector/config.py`:

```python
CRITICAL_KEYWORDS = [
    # Add your custom keywords
    'USMCA renegotiation',
    'Pemex default',
    'Brazil impeachment',
    # ... existing keywords
]
```

### Change Email Schedule

Edit `backend/scheduler.py`:

```python
# Change daily digest time (currently 7 AM ET)
scheduler.add_job(
    send_daily_digest,
    CronTrigger(hour=6, minute=30, timezone='America/New_York'),  # 6:30 AM
    id='daily_digest'
)
```

---

## Troubleshooting

### "API key invalid" Error

1. Check your `.env` file has correct keys
2. Make sure there are no extra spaces around the keys
3. Try generating a new key from the provider

### "ModuleNotFoundError"

```bash
# Make sure venv is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### "Port already in use"

```bash
# Mac/Linux - find and kill process on port 8000
lsof -ti:8000 | xargs kill

# Windows
netstat -ano | findstr :8000
# Note the PID, then:
taskkill /PID [the_pid] /F
```

### Frontend Won't Build

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

### Render Deployment Fails

1. Check Render dashboard → Logs tab for error messages
2. Make sure all environment variables are set
3. Verify DATABASE_URL starts with `postgresql://`

---

## Maintenance

### Daily
- Check the email digest arrives at 7 AM
- Verify dashboard shows recent data

### Weekly
- Review any ERROR status in system health
- Check Render dashboard for any warnings

### Monthly
- Update dependencies:
  ```bash
  pip install -r requirements.txt --upgrade
  ```
- Review and rotate API keys if needed

---

## Getting Help

1. **Check the logs**:
   - Local: Look at terminal output
   - Render: Dashboard → Logs tab

2. **API Documentation**:
   - Local: http://localhost:8000/docs
   - Deployed: https://your-app.onrender.com/docs

3. **Module Tests**:
   ```bash
   python scripts/test_modules.py --module fx  # Test specific module
   ```

---

## Development Timeline

| Week | Focus | Goal |
|------|-------|------|
| 1 | Local Setup | FX module working, API running locally |
| 2 | Database + Deploy | PostgreSQL setup, deployed to Render |
| 3 | All Modules | Yields, credit, news working |
| 4 | Risk Detection | Alerts generating correctly |
| 5-6 | Email System | Daily digest, critical alerts |
| 7-8 | Polish | Dashboard refinement, team sharing |

---

**You've got this!** The modular architecture means even if one component has issues, the others will keep working. Start with FX (it's the simplest) and build from there.
