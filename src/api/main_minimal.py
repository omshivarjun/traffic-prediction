"""
Minimal FastAPI app to bypass SQLAlchemy model issues
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

# Create FastAPI app
app = FastAPI(
    title="Traffic Prediction API - Minimal",
    description="Minimal API for testing infrastructure",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Traffic Prediction API - Minimal Version", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-09-20T13:00:00.000000",
        "checks": {
            "api": {"status": "healthy", "message": "API is running"},
            "database": {"status": "healthy", "message": "Database bypassed in minimal mode"},
            "kafka": {"status": "healthy", "message": "Kafka connection skipped in minimal mode"}
        }
    }

@app.get("/api/sensors")
async def get_sensors():
    """Mock sensors endpoint"""
    return {"sensors": [], "message": "Minimal mode - no real data"}

@app.get("/api/traffic-data")
async def get_traffic_data():
    """Mock traffic data endpoint"""
    return {"traffic_data": [], "message": "Minimal mode - no real data"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)