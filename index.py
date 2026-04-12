import uvicorn
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone

# Import from app modules
from app.config import settings
from app.core.splunk import SplunkAPI

# Initialize FastAPI
app = FastAPI(
    title="Columbus",
    description="Discover Splunk Anomalies",
    version="0.1.0"
)

# Initialize Splunk API
splunk_api = SplunkAPI()


# ==================== API ENDPOINTS ====================

@app.get("/health")
def health():
    """Health check"""
    return {
        "status": "ok",
        "service": "columbus",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/checkConfig")
def check_config():
    """Check configuration"""
    token = settings.SPLUNK_TOKEN
    masked = f"{token[:6]}...{token[-4:]}" if len(token) > 10 else "not set"
    
    return {
        "splunk_host": settings.SPLUNK_HOST,
        "token_set": bool(token),
        "token_preview": masked,
        "api_port": settings.API_PORT
    }


@app.get("/testConnection")
def test_connection():
    """Test Splunk connection"""
    info = splunk_api.test_connection()
    return {
        **info,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ==================== RUN ====================

if __name__ == "__main__":
    uvicorn.run(
        "index:app",
        host="0.0.0.0",
        port=settings.API_PORT,
        reload=True
    )