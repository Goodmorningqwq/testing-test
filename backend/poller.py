import httpx
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poller")

HYPIXEL_BAZAAR_API = "https://api.hypixel.net/v2/skyblock/bazaar"

async def fetch_and_store_bazaar_data():
    logger.info("Fetching Bazaar data...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(HYPIXEL_BAZAAR_API, timeout=30.0)
            response.raise_for_status()
            data = response.json()

        if not data.get("success"):
            logger.error("Bazaar API returned success=False")
            return

        products = data.get("products", {})
        now = datetime.now(timezone.utc)
        
        records = []
        for item_id, item_data in products.items():
            quick_status = item_data.get("quick_status", {})
            buy_price = quick_status.get("buyPrice", 0.0)
            buy_volume = quick_status.get("buyVolume", 0)
            sell_price = quick_status.get("sellPrice", 0.0)
            sell_volume = quick_status.get("sellVolume", 0)

            records.append((
                now,
                item_id,
                buy_price,
                buy_volume,
                sell_price,
                sell_volume
            ))

        if records and db.pool:
            async with db.pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO bazaar_prices 
                    (timestamp, item_id, buy_price, buy_volume, sell_price, sell_volume)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    records
                )
            logger.info(f"✅ Stored {len(records)} bazaar items into DB.")

    except Exception as e:
        logger.error(f"Error fetching/storing bazaar data: {e}")

# Global scheduler instance
scheduler = AsyncIOScheduler()

def start_poller():
    # Run every 5 minutes
    scheduler.add_job(fetch_and_store_bazaar_data, 'interval', minutes=5, id="bazaar_poller", replace_existing=True)
    scheduler.start()
    logger.info("✅ Background poller started (runs every 5 mins).")

def stop_poller():
    scheduler.shutdown()
    logger.info("❌ Background poller stopped.")
