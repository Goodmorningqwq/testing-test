import gc
import logging
import pandas as pd
from prophet import Prophet
from datetime import datetime, timezone, timedelta
from db import db
from pydantic import BaseModel
from typing import Dict, Any

logger = logging.getLogger("predictor")

class CacheEntry:
    def __init__(self, timestamp: datetime, data: Any):
        self.timestamp = timestamp
        self.data = data

# Simple local in-memory cache
_prediction_cache: Dict[str, CacheEntry] = {}
CACHE_TTL_MINUTES = 60

async def get_calibration_factor() -> float:
    """
    Computes a global scalar adjustment based on user's past accuracy.
    If actual ROI was consistently 10% lower than predicted ROI, this returns 0.9.
    """
    if getattr(db, 'pool', None) is None:
        return 1.0
        
    query = """
        SELECT AVG(actual_roi / NULLIF(predicted_roi, 0)) as avg_ratio
        FROM user_investment_logs
        WHERE actual_roi IS NOT NULL AND predicted_roi IS NOT NULL
    """
    
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(query)
            if row and row["avg_ratio"]:
                # Bound the factor to avoid crazy values (e.g. between 0.5 and 1.5)
                return max(0.5, min(1.5, float(row["avg_ratio"])))
    except Exception as e:
        logger.error(f"Error fetching calibration: {e}")
        
    return 1.0

async def generate_prediction(item_id: str, days_history: int = 30, horizon_days: int = 7) -> dict:
    """Generate and cache a time-series prediction for an item."""
    cache_key = f"{item_id}_{horizon_days}"
    now = datetime.now(timezone.utc)
    
    # Check cache
    if cache_key in _prediction_cache:
        entry = _prediction_cache[cache_key]
        if (now - entry.timestamp).total_seconds() < CACHE_TTL_MINUTES * 60:
            return entry.data

    if getattr(db, 'pool', None) is None:
        return {}

    cutoff = now - timedelta(days=days_history)
    query = """
        SELECT timestamp, sell_price, buy_price 
        FROM bazaar_prices 
        WHERE item_id = $1 AND timestamp >= $2
        ORDER BY timestamp ASC
    """
    
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query, item_id, cutoff)
        
    if not rows:
        return {}
        
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty or len(df) < 10:
        return {}

    # Standardize for Prophet: 'ds' (datestamp) and 'y' (target value)
    df.rename(columns={'timestamp': 'ds', 'sell_price': 'y'}, inplace=True)
    df['ds'] = pd.to_datetime(df['ds']).dt.tz_localize(None) # Prophet prefers tz-naive

    # Downsample to save RAM (1-hour intervals)
    df = df.set_index('ds').resample('1h').mean().dropna().reset_index()

    # Fit Model
    model = Prophet(daily_seasonality=True, yearly_seasonality=False, weekly_seasonality=False)
    
    try:
        model.fit(df)
        
        future = model.make_future_dataframe(periods=horizon_days * 24, freq='h')
        forecast = model.predict(future)
        
        # Free memory aggressively (Render Free Tier constraints)
        model.history = None
        del model
        gc.collect()

        # Extract just the future horizon mapping
        future_forecast = forecast[forecast['ds'] > df['ds'].max()]
        
        if future_forecast.empty:
            return {}
            
        predicted_end_price = float(future_forecast['yhat'].iloc[-1])
        current_price = float(df['y'].iloc[-1])
        current_buy_price = float(df['buy_price'].iloc[-1]) if 'buy_price' in df.columns else current_price
        
        # Raw predicted ROI computation (Lazy Investor)
        raw_predicted_roi = 0.0
        if current_price > 0:
            raw_predicted_roi = (predicted_end_price - current_price) / current_price
            
        # Raw predicted ROI computation (Flipper)
        flipper_raw_roi = 0.0
        if current_buy_price > 0:
            flipper_raw_roi = (predicted_end_price - current_buy_price) / current_buy_price
            
        # Apply strict User Calibration Factor
        calibration_factor = await get_calibration_factor()
        calibrated_roi = raw_predicted_roi * calibration_factor
        flipper_calibrated_roi = flipper_raw_roi * calibration_factor

        result = {
            "item_id": item_id,
            "current_price": current_price,
            "current_buy_order_price": current_buy_price,
            "predicted_end_price": current_price * (1 + calibrated_roi),
            "raw_predicted_roi": raw_predicted_roi,
            "calibrated_roi": calibrated_roi,
            "flipper_raw_roi": flipper_raw_roi,
            "flipper_calibrated_roi": flipper_calibrated_roi,
            "calibration_factor_applied": calibration_factor,
            "horizon_days": horizon_days
        }

        # Save to cache
        _prediction_cache[cache_key] = CacheEntry(timestamp=now, data=result)

        return result

    except Exception as e:
        logger.error(f"Prophet fitting error for {item_id}: {e}")
        return {}
