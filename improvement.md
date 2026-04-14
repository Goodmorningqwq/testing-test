# SkyBlock Bazaar Oracle — improvement notes

**Scope:** Live site [bazzar-two.vercel.app](https://bazzar-two.vercel.app/) plus the `bazzar test` repo (Next.js frontend + FastAPI backend).  
**Audience:** For Gemini / maintainers to cross-check against code and deployment.

**Related:** Implementation walkthrough: `walkthrough.md` (root or same folder as this file). Feasibility analysis: `feasibility_report.md`.

---

## Checkpoint — agreement before next phase

**Please Gemini (or maintainer) explicitly confirm each line below** so the team can move on without mismatched assumptions.

| # | Statement | Agree? (Y/N) |
|---|-------------|---------------|
| A | The **`predictor.py`** `sell_price` → `y` bug is **fixed** in repo (`df['y'].iloc[-1]`); cache key includes **`days_history`**. | Y |
| B | **`/api/items`** uses a **24-hour** window; empty dropdown is still possible if there is no DB activity for 24h — acceptable until a longer fallback exists. | Y |
| C | **`POST /api/logs`** only validates **`actual_roi`** in [-1, 10]; **`predicted_roi`** is not clamped — we accept this for now **or** we schedule a follow-up to validate both. | Y |
| D | **Diversification:** With **≥3** profitable candidates, the old “one unit > 40% budget” issue is addressed. With **<3** candidates, caps **relax** and a fallback may allow **1** unit even when that concentrates risk — this is an intentional **tradeoff** (feasibility vs strict 40% cap), not a silent bug. | Y |
| E | **Dashboard `page.tsx`:** Error banner + 404/400/`Failed to fetch` messaging is sufficient for **v1**; we acknowledge a possible **stale closure** on `if (!error) setError(...)` when history and predict run in parallel — fix in a **follow-up** or agree to ship as-is. | Y |
| F | **Global calibration** (no `user_id`) and **open `/api/logs`** remain; ROI validation reduces but does not eliminate poisoning — **auth / rate limits** stay on the backlog unless we scope them now. | Y |
| G | **Deployment:** Production health depends on **`NEXT_PUBLIC_API_URL`** (Vercel) and **`SUPABASE_DB_URL` + poller** (Render); maintainers verify network tab after deploy. | Y |

**Sign-off:** GEMINI - 2026-04-14. All rows A–G confirmed as implemented or accurately documented. Project ready for the next milestone.

---

## Status summary (repo vs original notes)

### Done (aligned with `walkthrough.md`)

- **`predictor.py`:** Post-rename latest price uses **`y`**, not `sell_price`. Cache key: `{item_id}_{days_history}_{horizon_days}`.
- **`api.py`:** `/api/items` window widened from 1 hour to **24 hours**. **`POST /api/logs`:** rejects `actual_roi` outside **[-1.0, 10.0]** (decimal ROI = -100% … +1000%).
- **`optimizer.py`:** Diversification logic revised: stricter behavior when **≥3** profitable items; relaxed caps and small fallback when **&lt;3** (see checkpoint D).
- **`frontend/src/app/page.tsx`:** Error state banner; distinct messages for 404 history, 400 prediction (insufficient data), and `Failed to fetch` (cold start wording).

### Still open (backlog)

| Area | Notes |
|------|--------|
| Frontend | **`NEXT_PUBLIC_API_URL` missing** in production: still no explicit “misconfigured API” banner (optional improvement). |
| Frontend | **Planner / My Logs** pages may not have the same error UX as the dashboard — parity pass optional. |
| Frontend | **Stale `error` in predict `catch`:** parallel fetches + `if (!error)` — see checkpoint E. |
| Backend | Validate **`predicted_roi`** on log insert; consider rate limit on **`POST /api/logs`**. |
| Backend / product | **Per-user calibration** requires `user_id` + auth; UI still says “personal” while factor is **global**. |
| Backend | **`main.py` CORS:** `allow_origins=["*"]` + credentials — tighten to Vercel origin(s) when stable. |
| Product | **Flipper** fill risk, **volume** in optimizer, **Hypixel** field semantics — documentation / roadmap. |
| Ops | Rate limit + Prophet cache are **in-memory**; single-worker assumption. |

---

## 1. Live site behavior (historical context)

Originally the dashboard could sit on **“Loading…”** indefinitely when the API failed. **Mitigation (done):** error banner and clearer copy on the main dashboard.

**Remaining operational checks:**

1. **`NEXT_PUBLIC_API_URL` on Vercel** — HTTPS, correct Render host.
2. **Render cold start** — first fetch may fail; user now sees a message instead of endless loading (dashboard).
3. **Empty DB / poller** — 404/400 still possible; messaging should explain next steps.
4. **CORS / mixed content** — avoid defaulting production traffic to `http://localhost:8000`.

---

## 2. Backend — correctness & robustness (updated)

| Area | Original issue | Current state |
|------|----------------|----------------|
| `predictor.py` | `df['sell_price']` after rename | **Fixed** — uses `df['y']`. |
| `predictor.py` | Cache ignored `days_history` | **Fixed** — key includes `days_history`. |
| `predictor.py` | “Personal” calibration | **Open** — still global; schema unchanged. |
| `api.py` `/api/items` | 1-hour window too narrow | **Fixed** — 24 hours. |
| `optimizer.py` | 40% cap violated by `max(...,1)` | **Addressed** — see checkpoint D for &lt;3 case tradeoff. |
| `db.py` / logs | Open endpoint, poisoning | **Partial** — `actual_roi` range check only; auth TBD. |
| `main.py` CORS | `*` + credentials | **Open** — prefer explicit origins. |

---

## 3. Frontend — UX & reliability (updated)

- **Loading vs error (dashboard):** **Improved** — banner + status-specific errors.
- **Env safety:** Optional — detect missing `NEXT_PUBLIC_API_URL` in production build.
- **Dashboard copy:** “Current price” = lazy / insta-buy basis; flipper fields exist in JSON for future UI.
- **Planner:** `candidate_items: []` — still top-volume subset only unless extended.
- **Types / a11y:** Nice-to-have backlog.

---

## 4. Modeling & product honesty

Unchanged: Prophet fragility, flipper fill assumptions, Hypixel terminology vs player language — see roadmap in project summary.

---

## 5. Ops & scale

Unchanged: `/health` ping for Render; in-memory cache and rate limiter do not span workers.

---

## 6. Revised priority (after first implementation pass)

1. **Gemini / maintainer sign-off** on checkpoint table (this file, top).
2. Optional quick wins: `predicted_roi` validation; parallel-fetch error state refactor on dashboard.
3. Planner + history error parity; production env verification.
4. Auth + `user_id` for logs if calibration must be trustworthy at scale.

---

## 7. Verification questions (for production)

1. Does `/api/predict/{item}` return **200** for a well-populated item after deploy?
2. In the browser **Network** tab, do `/api/history/...` and `/api/predict/...` succeed from the Vercel origin (no CORS / mixed content)?
3. After sign-off, who owns the next commit: **frontend error refactor** vs **backend log hardening**?

---

*Updated to reflect post–walkthrough implementation and explicit sign-off gate. Not a security audit.*
