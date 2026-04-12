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


@app.get("/api/searches/recent")
def get_recent_searches_endpoint(minutes: int = 5, include_raw: bool = False):
    """
    Get recent searches from Splunk
    
    Args:
        minutes: Look back this many minutes (default: 5)
        include_raw: Include raw entry from Splunk API (default: False)
    """
    try:
        entries = splunk_api.get_recent_searches(minutes=minutes)
        searches = []
        ad_hoc_count = 0
        saved_count = 0
        
        for entry in entries:
            content = entry.get('content', {})
            
            is_saved = content.get('isSavedSearch', False)
            is_done = content.get('isDone', False)
            if is_saved:
                saved_count += 1
            else:
                ad_hoc_count += 1
            if is_done:
                search_data = {
                    'search_id': content.get('sid'),
                    'user': content.get('author', 'unknown'),
                    'search_spl': content.get('search', ''),
                    'is_saved_search': is_saved,
                    'is_done': is_done,
                    'runtime': float(content.get('runDuration', 0)),
                    'events_scanned': int(content.get('scanCount', 0)),
                    'results_returned': int(content.get('resultCount', 0))
                }
                if include_raw:
                    search_data['raw_entry'] = entry
                
                searches.append(search_data)
        
        return {
            'total': len(searches),
            'ad_hoc': ad_hoc_count,
            'saved': saved_count,
            'minutes': minutes,
            'searches': searches
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== RUN ====================

if __name__ == "__main__":
    uvicorn.run(
        "index:app",
        host="0.0.0.0",ß
        port=settings.API_PORT,
        reload=True
    )