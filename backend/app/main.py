from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Backend starting up...")
    yield
    # Shutdown logic
    print("Backend shutting down...")

app = FastAPI(
    title="Momentum A-Share System",
    description="Quantitative Trading System Backend",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "Welcome to Momentum API", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "db_connected": "todo"}
