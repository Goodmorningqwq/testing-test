# SkyBlock Bazaar Oracle — improvement notes

**Scope:** Live site [bazzar-two.vercel.app](https://bazzar-two.vercel.app/) plus the `bazzar test` repo (Next.js frontend + FastAPI backend).  
**Audience:** For Gemini / maintainers to cross-check against code and deployment.

---

## 1. Live site behavior (observed)

- Dashboard stays on **“Loading historical data…”** and **“Loading prediction…”** instead of resolving to charts or error messages.
- **Likely causes to verify (in order):**
  1. **`NEXT_PUBLIC_API_URL` on Vercel** — must point to the live Render (or other) backend URL, no trailing slash issues, HTTPS.
  2. **Backend cold start / sleep** (Render free tier) — first requests can time out; frontend has no timeout or retry UX.
  3. **Empty database** — poller never ran or `SUPABASE_DB_URL` wrong on backend; `/api/history/...` returns 404 and `/api/predict` returns 400 with insufficient data.
  4. **CORS / mixed content** — browser blocks `http://` API from HTTPS page if env var missing (defaults to `http://localhost:8000` in code).
  5. **Predictor bug** — after Prophet fit, code references `df['sell_price']` but the column was renamed to `y`; can yield empty prediction and 400 responses.

**Improvement:** Surface API failures (status, `detail`), empty states (“no data yet”), and optional “API URL not configured” when `NEXT_PUBLIC_API_URL` is missing in production.

---

## 2. Backend — correctness & robustness

| Area | Issue | Suggested direction |
|------|--------|---------------------|
| `predictor.py` | Uses `df['sell_price']` after renaming `sell_price` → `y` | Use the correct column (e.g. `y`) for latest insta-sell, or avoid rename until after extracting last prices |
| `predictor.py` | Cache key is `{item_id}_{horizon_days}` only | Include `days_history` (and optionally mode) in cache key if API exposes different windows |
| `predictor.py` | Calibration described as “per user” in product copy | DB has no `user_id`; calibration is **global** across all log rows — add user identity or reword product/docs |
| `api.py` `/api/items` | Distinct items only in **last 1 hour** | Empty dropdown after downtime; widen window or cap “recent distinct” + fallback |
| `optimizer.py` | `max(..., 1)` for quantity can **exceed 40% budget** on a single asset when one unit is expensive | Enforce cap strictly or drop infeasible items from the candidate set |
| `db.py` / logs | No auth on `POST /api/logs` | Anyone can poison calibration data — add minimal auth or rate limits per IP + validation |
| `main.py` CORS | `allow_origins=["*"]` + `allow_credentials=True` | Prefer explicit Vercel origin(s) |

---

## 3. Frontend — UX & reliability

- **Loading vs error:** `fetch` errors and non-OK responses are mostly `console.error` only; users see infinite loading. Add error banners and 404/400-specific copy.
- **Env safety:** If `NEXT_PUBLIC_API_URL` is unset in production, show a warning instead of silently calling localhost.
- **Dashboard:** “Current price” reflects lazy (insta-buy) basis; consider labeling **Insta-buy** vs **Buy-order** when you expose flipper metrics in the UI.
- **Planner:** `candidate_items` is always `[]` — document that optimization is **top-volume subset**, not full bazaar; optional advanced “paste item list.”
- **Types:** Replace pervasive `any` with response types for maintainability.
- **Accessibility:** Emoji mode toggles are cute but ensure labels/ARIA for screen readers.

---

## 4. Modeling & product honesty

- Prophet on hourly bazaar data is **fragile** around patches and manipulation; roadmap items (volume, liquidity) matter.
- **Flipper mode** assumes fills at buy-order price; optimizer does not model fill probability or time-to-fill.
- **Hypixel field semantics:** Confirm `buyPrice` / `sellPrice` vs in-game insta-buy/insta-sell once against official docs so ROI terminology stays correct end-to-end.

---

## 5. Ops & scale

- Render sleep: document **cron ping** on `/health` (already in README); consider showing “backend waking up…” after slow response.
- In-memory rate limit and prediction cache **do not span** multiple workers — document single-instance assumption or move to Redis/DB.

---

## 6. Suggested priority order (for implementation)

1. Fix predictor `sell_price` / `y` bug and redeploy backend.
2. Confirm Vercel `NEXT_PUBLIC_API_URL` and backend DB + poller running.
3. Frontend: show errors + misconfiguration instead of infinite loading.
4. Tighten items query + diversification logic + calibration scope (global vs per-user).

---

## 7. Questions for Gemini to answer

1. After fixing `predictor.py`, does `/api/predict/{item}` return 200 for `ENCHANTED_DIAMOND` when DB has ≥10 rows in the lookback window?
2. Does the production browser network tab show successful calls to `${NEXT_PUBLIC_API_URL}/api/history/...` and `/api/predict/...`, or CORS/blocked/mixed-content failures?
3. Should calibration require authenticated users, and if not, how do you prevent malicious log spam?

---

*Generated from live page content and static repo review; not a security audit.*
