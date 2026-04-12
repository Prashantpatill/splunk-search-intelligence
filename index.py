import uvicorn
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone

# Import from app modules
from app.config import settings
from app.core.splunk import SplunkAPI
from app.core.detector import SearchAnalyzer


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
def get_recent_searches_endpoint(
    minutes: int = 5, 
    include_raw: bool = False,
    only_problematic: bool = False 
):
    try:
        entries = splunk_api.get_recent_searches(minutes=minutes)
        
        searches = []
        ad_hoc_count = 0
        saved_count = 0
        problematic_count = 0
        
        for entry in entries:
          
            search_data = SearchAnalyzer.parse_search_entry(entry)
            
            
            if search_data['is_saved_search']:
                saved_count += 1
            else:
                ad_hoc_count += 1
            
            
            if search_data['is_done']:
                
                
                issues = SearchAnalyzer.detect_issues(search_data)
                
                
                search_data['issues'] = issues
                
                if issues:
                    problematic_count += 1
                    search_data['severity'] = SearchAnalyzer.calculate_severity(issues, search_data)
                else:
                    search_data['severity'] = 'none'
                
                
                if only_problematic and not issues:
                    continue
                
                if include_raw:
                    search_data['raw_entry'] = entry
                
                searches.append(search_data)
        
        return {
            'total': len(searches),
            'ad_hoc': ad_hoc_count,
            'saved': saved_count,
            'problematic': problematic_count,
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