import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            raise ValueError("SUPABASE_DB_URL is not set in environment.")
        
        # Create a connection pool targeting Supabase
        self.pool = await asyncpg.create_pool(db_url, min_size=1, max_size=10)
        print("✅ Connected to Supabase DB pool")
        
        # Initialize schema if it doesn't exist
        await self.init_schema()

    async def init_schema(self):
        schema_sql = """
        -- 1. Bazaar Prices Table
        CREATE TABLE IF NOT EXISTS bazaar_prices (
            timestamp TIMESTAMPTZ NOT NULL,
            item_id VARCHAR(100) NOT NULL,
            buy_price DOUBLE PRECISION NOT NULL,
            buy_volume INTEGER NOT NULL,
            sell_price DOUBLE PRECISION NOT NULL,
            sell_volume INTEGER NOT NULL
        );

        -- Crucial indices for time-series forecasting and querying history
        CREATE INDEX IF NOT EXISTS idx_bazaar_prices_item_time ON bazaar_prices (item_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_bazaar_prices_time ON bazaar_prices (timestamp DESC);

        -- 2. User Investment Logs Table (Feedback Loop)
        CREATE TABLE IF NOT EXISTS user_investment_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            plan_id VARCHAR(100),
            recommended_items TEXT,
            budget DOUBLE PRECISION,
            horizon_days INTEGER,
            predicted_roi DOUBLE PRECISION,
            actual_roi DOUBLE PRECISION,
            actual_profit DOUBLE PRECISION,
            notes TEXT
        );
        """
        async with self.pool.acquire() as connection:
            await connection.execute(schema_sql)
            print("✅ Database schema initialized")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            print("❌ Disconnected from DB")

    async def get_connection(self):
        """Yields a connection from the pool. Use with async with."""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        return self.pool.acquire()

# Global database instance
db = Database()
