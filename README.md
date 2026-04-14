# SkyBlock Bazaar Oracle

A full-stack, AI-powered MVP that tracks Hypixel SkyBlock Bazaar prices, executes Prophet Time-Series Forecasting, and utilizes Linear Programming (PuLP) to calculate optimal coin allocation. It also implements a full feedback loop based on your personal trading history to correct standard errors out of the prediction curve.

## Technology Stack (100% Free Tier)
- **Database:** Supabase Free Tier (Postgres connection pooling)
- **Backend:** FastAPI + Python 3.12 (Deployed to Render Free Web Service)
- **Frontend:** Next.js 15 App Router + Tailwind + shadcn/ui (Deployed to Vercel)
- **Machine Learning:** Facebook Prophet + PuLP Linear Programming

---

## Deployment Guide (One-Click Setup)

### 1. Database (Supabase)
1. Set up a free Postgres DB on [Supabase](https://supabase.com).
2. Grab the connection URL (`Project Settings -> Database -> Connection String (URI)`).

### 2. Backend (Render)
1. Push this repository to your GitHub.
2. Sign in to [Render](https://render.com) and create a **New Web Service**.
3. Select your repository. Use the following settings:
   - **Language:** `Python 3`
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables:** Set `SUPABASE_DB_URL`
   - **Health Check Path:** `/health`
4. Deploy! Render will give you a URL like `https://skyblock-oracle.onrender.com`.

*(Important Keep-Alive)*: Render spins down after 15 minutes of inactivity. To prevent this, create a free ping on [cron-job.org](https://cron-job.org) targeting `https://[YOUR_RENDER_URL]/health` every 10 minutes. 
*Note: Any "Output is too big" errors from cron-job.org initially just mean Render is still booting up and serving its loading screen.*

### 3. Frontend (Vercel)
1. Go to [Vercel](https://vercel.com) and click **Add New Project**.
2. Import your GitHub repository.
3. Use the following settings:
   - **Framework Preset:** `Next.js`
   - **Root Directory:** `frontend`
   - **Environment Variables:** Set `NEXT_PUBLIC_API_URL` to your Render URL (e.g. `https://skyblock-oracle.onrender.com`)
4. Click Deploy!
