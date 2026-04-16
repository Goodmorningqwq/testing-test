import asyncio
from db import db

async def audit_items():
    await db.connect()
    try:
        query = "SELECT DISTINCT item_id FROM bazaar_prices"
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(query)
            items = [row['item_id'] for row in rows]
            print("---START_IDS---")
            for item in items:
                print(item)
            print("---END_IDS---")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(audit_items())
