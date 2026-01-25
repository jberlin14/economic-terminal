# Render.com Deployment Guide

## Overview
This guide walks you through deploying the Economic Terminal to Render.com with separate frontend and backend services.

## Architecture
- **Backend Service**: Python FastAPI application (Web Service)
- **Frontend Service**: React static site (Static Site)
- **Database**: SQLite (stored on backend disk)

## Step-by-Step Deployment

### 1. Deploy Backend (Web Service)

#### Create Web Service
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `economic-terminal-backend` (or your choice)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: Leave blank (or `.`)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (or paid for better performance)

#### Set Environment Variables
In the "Environment" tab, add these variables:

**Required:**
```
DATABASE_URL=sqlite:///./economic_data.db
ALPHA_VANTAGE_KEY=your_alpha_vantage_key_here
FRED_API_KEY=your_fred_api_key_here
```

**Optional (but recommended):**
```
NEWS_API_KEY=your_news_api_key_here
TWITTER_BEARER_TOKEN=your_twitter_token_here
SENDGRID_API_KEY=your_sendgrid_key_here
SENDGRID_FROM_EMAIL=your_email@example.com
RECIPIENT_EMAIL=your_email@example.com
DEBUG=false
LOG_LEVEL=INFO
TIMEZONE=America/New_York
```

#### Add Disk Storage (Important!)
1. In your backend service, go to "Disks"
2. Click "Add Disk"
3. Configure:
   - **Name**: `economic-data`
   - **Mount Path**: `/data`
   - **Size**: 1 GB (free tier)

This ensures your SQLite database persists across deployments.

**Then update your DATABASE_URL environment variable:**
```
DATABASE_URL=sqlite:////data/economic_data.db
```
Note: Use 4 slashes (`sqlite:////`) for absolute paths.

#### Deploy
1. Click "Create Web Service"
2. Wait for deployment (5-10 minutes)
3. Note your backend URL: `https://economic-terminal-backend.onrender.com` (example)

---

### 2. Deploy Frontend (Static Site)

#### Create Static Site
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Static Site"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `economic-terminal-frontend` (or your choice)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `build`

#### Set Environment Variables
In the "Environment" tab, add these variables (CRITICAL!):

```
REACT_APP_API_URL=https://economic-terminal-backend.onrender.com
REACT_APP_WS_URL=wss://economic-terminal-backend.onrender.com/ws
```

**Important:** Replace `economic-terminal-backend.onrender.com` with YOUR actual backend URL from Step 1!

#### Deploy
1. Click "Create Static Site"
2. Wait for deployment (3-5 minutes)
3. Your frontend will be available at: `https://economic-terminal-frontend.onrender.com`

---

## 3. Verify Deployment

### Backend Health Check
Visit: `https://your-backend-url.onrender.com/api/health`

You should see:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-25T10:00:00Z",
  "database": "connected"
}
```

### Frontend Check
Visit: `https://your-frontend-url.onrender.com`

You should see the Economic Terminal dashboard loading data.

---

## 4. Initial Data Population

After deployment, populate your database:

1. SSH into Render or use their Shell feature
2. Run the manual fetch script:
```bash
python scripts/manual_fetch.py
```

Or run it locally with your production DATABASE_URL:
```bash
DATABASE_URL=your_render_postgres_url python scripts/manual_fetch.py
```

---

## Troubleshooting

### Frontend shows "Failed to fetch dashboard"

**Cause**: Frontend can't reach backend

**Solutions**:
1. Verify backend is running: Check `https://your-backend-url.onrender.com/api/health`
2. Check environment variables in frontend:
   - `REACT_APP_API_URL` must be set to your backend URL
   - `REACT_APP_WS_URL` must be set to your backend WebSocket URL
3. Verify CORS is enabled in backend (it is by default)
4. Check backend logs for errors

### Backend crashes or restarts frequently

**Cause**: Usually memory limits on free tier

**Solutions**:
1. Upgrade to paid instance type
2. Reduce scheduler frequency in `backend/scheduler.py`
3. Check logs for memory errors

### Database resets after deployment

**Cause**: Disk not configured

**Solution**:
1. Add persistent disk to backend service (see Step 1)
2. Mount at `/data`
3. Update `DATABASE_URL` to `sqlite:////data/economic_data.db`

### WebSocket connection fails

**Cause**: Wrong WebSocket URL

**Solution**:
1. Ensure `REACT_APP_WS_URL` uses `wss://` (not `ws://`)
2. Verify URL matches your backend URL

### API rate limits hit

**Cause**: Scheduler running too frequently

**Solution**:
1. Increase intervals in `backend/scheduler.py`
2. For free APIs:
   - FX: every 10-15 minutes (currently 5)
   - Yields: every 15-30 minutes (currently 5)
   - Credit: every 1-2 hours (currently 30 minutes)
   - News: every 30-60 minutes (currently 15)

---

## Local Development After Deployment

Your local setup still works! The `.env.local` file keeps local URLs:
```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws
```

---

## Updating the Deployment

### Backend Updates
1. Push to GitHub
2. Render auto-deploys from `main` branch
3. Check deployment logs

### Frontend Updates
1. Push to GitHub
2. Render auto-deploys and rebuilds
3. May need to clear browser cache

### Environment Variable Changes
1. Update in Render dashboard
2. Click "Manual Deploy" to apply changes

---

## Free Tier Limitations

**Render Free Tier:**
- Backend spins down after 15 minutes of inactivity
- First request after spin-down takes 30-60 seconds
- 750 hours/month free compute
- Limited memory/CPU

**Recommendations:**
- Keep scheduler intervals longer to reduce CPU usage
- Consider paid tier ($7/month) for always-on backend
- Use external cron job to ping `/api/health` every 10 minutes to keep warm

---

## Production Recommendations

### Security
1. Update CORS in `backend/main.py` to specific frontend URL:
   ```python
   allow_origins=["https://your-frontend-url.onrender.com"]
   ```

2. Use environment variables for all secrets (already configured)

3. Enable HTTPS (automatic on Render)

### Performance
1. Upgrade to paid instance for faster response
2. Add Redis for caching (future enhancement)
3. Use PostgreSQL instead of SQLite for production scale

### Monitoring
1. Set up Render's built-in monitoring
2. Configure email alerts via SendGrid
3. Monitor logs regularly

---

## Cost Estimation

**Free Tier (Current):**
- Backend: Free (with spin-down)
- Frontend: Free
- Total: $0/month

**Starter Tier (Recommended):**
- Backend: $7/month (always-on, 512MB RAM)
- Frontend: Free
- PostgreSQL: $7/month (optional, better than SQLite)
- Total: $7-14/month

---

## Support

For issues:
1. Check Render logs in dashboard
2. Review backend logs at `/logs/`
3. Test endpoints with `/docs` (FastAPI Swagger UI)
4. Check browser console for frontend errors