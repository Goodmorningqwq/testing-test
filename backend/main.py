from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
from collections import defaultdict

from db import db
from poller import start_poller, stop_poller
from api import router as api_router

logger = logging.getLogger("api")

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple IP-based memory rate limiter for MVP (100 requests / min).
    """
    def __init__(self, app):
        super().__init__(app)
        self.rate_limit_records = defaultdict(list)
        self.limit = 100
        self.window = 60

    async def dispatch(self, request: Request, call_next):
        # Exclude health checks from rate limits so uptime monitors don't get blocked
        if request.url.path == "/health":
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean up old records
        self.rate_limit_records[client_ip] = [t for t in self.rate_limit_records[client_ip] if now - t < self.window]
        
        if len(self.rate_limit_records[client_ip]) >= self.limit:
            logger.warning(f"Rate limit exceeded for IP {client_ip}")
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests. Rate limit exceeded."})
            
        self.rate_limit_records[client_ip].append(now)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Phase
    logger.info("Starting up Backend API...")
    
    # 1. Connect to Database and run schema check
    await db.connect()
    
    # 2. Start Background Poller
    start_poller()
    
    yield
    
    # Shutdown Phase
    logger.info("Shutting down Backend API...")
    stop_poller()
    await db.disconnect()

app = FastAPI(
    title="SkyBlock Bazaar Oracle",
    description="Backend API powering the SkyBlock Bazaar Oracle MVP. Features historical price tracking, Prophet ML Engine, and PuLP Portfolio Optimization.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add API Routes
app.include_router(api_router)

# Add Middlewares
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://bazzar-two.vercel.app", 
        "http://localhost:3000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "SkyBlock Bazaar Oracle API is running. Check /docs for Swagger UI."}

@app.get("/health", tags=["Infrastructure"])
async def health_check():
    """Idempotent health check endpoint for Render keep-alive (cron-job.org)."""
    return {"status": "ok"}
