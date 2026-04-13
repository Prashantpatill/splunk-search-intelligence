import uvicorn
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone

# Import from app modules
from app.config import settings
from app.core.splunk import SplunkAPI
from app.core.detector import SearchAnalyzer
from app.services.ai import AIAnalyzer


# Initialize FastAPI
app = FastAPI(
    title="Columbus",
    description="Discover Splunk Anomalies",
    version="0.1.0"
)

# Initialize Splunk API
splunk_api = SplunkAPI()
ai_analyzer = AIAnalyzer()

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

@app.get("/api/test/ai-analyze")
def test_ai_analyze(
    search_spl: str,
    runtime: float = 300.0,
    events_scanned: int = 1000000,
    results_returned: int = 100
):
    """
    Test AI analysis on a single search SPL
    
    Example:
        /api/test/ai-analyze?search_spl=index=* | transaction user&runtime=523
    """
    try:
        # Create mock search data
        search_data = {
            'search_id': 'test_12345',
            'user': 'test_user',
            'search_spl': search_spl,
            'runtime': round(runtime, 2),
            'events_scanned': events_scanned,
            'results_returned': results_returned if results_returned > 0 else 1,
            'scan_ratio': round(events_scanned / (results_returned if results_returned > 0 else 1), 2)
        }
        
        # Detect issues
        issues = SearchAnalyzer.detect_issues(search_data)
        search_data['issues'] = issues
        
        if issues:
            search_data['severity'] = SearchAnalyzer.calculate_severity(issues, search_data)
        else:
            search_data['severity'] = 'none'
        
        # Get AI analysis
        ai_result = ai_analyzer.analyze_search(search_data)
        
        return {
            'status': 'success',
            'search_data': search_data,
            'ai_analysis': ai_result['analysis'],
            'prompt_type': ai_result['prompt_type'],
            'token_usage': ai_result['token_usage']
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/searches/{search_id}/analyze")
async def analyze_search_by_id(search_id: str):
    """
    Analyze a specific search from recent searches
    
    Example:
        POST /api/searches/1234567890.12345/analyze
    """
    try:
        # Get recent searches
        entries = splunk_api.get_recent_searches(minutes=30)
        
        # Find the search
        search_entry = None
        for entry in entries:
            if entry.get('content', {}).get('sid') == search_id:
                search_entry = entry
                break
        
        if not search_entry:
            raise HTTPException(status_code=404, detail=f"Search {search_id} not found")
        
        # Parse search data
        search_data = SearchAnalyzer.parse_search_entry(search_entry)
        
        # Only analyze completed searches
        if not search_data['is_done']:
            raise HTTPException(status_code=400, detail="Search is not complete yet")
        
        # Detect issues
        issues = SearchAnalyzer.detect_issues(search_data)
        search_data['issues'] = issues
        
        if issues:
            search_data['severity'] = SearchAnalyzer.calculate_severity(issues, search_data)
        else:
            search_data['severity'] = 'none'
        
        # Get AI analysis
        ai_result = ai_analyzer.analyze_search(search_data)
        
        return {
            'status': 'success',
            'search_id': search_id,
            'search_data': search_data,
            'ai_analysis': ai_result['analysis'],
            'prompt_type': ai_result['prompt_type'],
            'token_usage': ai_result['token_usage']
        }
    
    except HTTPException:
        raise
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