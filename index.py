import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timezone
from typing import Optional

# Import from app modules
from app.config import settings
from app.core.splunk import SplunkAPI
from app.core.detector import SearchAnalyzer
from app.services.ai import AIAnalyzer
from app.db.memory_storage import memory_storage as storage

# Initialize FastAPI
app = FastAPI(
    title="Columbus",
    description="Discover Splunk Anomalies",
    version="0.1.0"
)

# Initialize Splunk API and AI Analyzer
splunk_api = SplunkAPI()
ai_analyzer = AIAnalyzer()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve UI at root
@app.get("/")
def serve_ui():
    return FileResponse('static/index.html')


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
        "internal_port": settings.INTERNAL_PORT,
        "azure_openai_configured": bool(settings.AZURE_API_KEY)
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
    """
    Get recent searches from Splunk
    
    Args:
        minutes: Look back this many minutes (default: 5)
        include_raw: Include raw entry from Splunk API (default: False)
        only_problematic: Only return searches with issues (default: False)
    """
    try:
        entries = splunk_api.get_recent_searches(minutes=minutes)
        
        searches = []
        ad_hoc_count = 0
        saved_count = 0
        problematic_count = 0
        
        for entry in entries:
            # Parse search with metrics
            search_data = SearchAnalyzer.parse_search_entry(entry)
            
            # Count by type
            if search_data['is_saved_search']:
                saved_count += 1
            else:
                ad_hoc_count += 1
            
            # Only include completed searches
            if search_data['is_done']:
                
                # Detect issues
                issues = SearchAnalyzer.detect_issues(search_data)
                search_data['issues'] = issues
                
                # Add severity
                if issues:
                    problematic_count += 1
                    search_data['severity'] = SearchAnalyzer.calculate_severity(issues, search_data)
                else:
                    search_data['severity'] = 'none'
                
                # Filter if only_problematic requested
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


# ==================== AI ENDPOINTS ====================

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
            'optimized_spl': ai_result['optimized_spl'],
            'prompt_type': ai_result['prompt_type'],
            'token_usage': ai_result['token_usage'],
            'finish_reason': ai_result.get('finish_reason'),
            'truncated': ai_result.get('truncated', False),
            'retry_count': ai_result.get('retry_count', 0)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/searches/{search_id}/analyze")
def analyze_search_by_id(search_id: str):
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
            'optimized_spl': ai_result['optimized_spl'],
            'prompt_type': ai_result['prompt_type'],
            'token_usage': ai_result['token_usage'],
            'finish_reason': ai_result.get('finish_reason'),
            'truncated': ai_result.get('truncated', False),
            'retry_count': ai_result.get('retry_count', 0)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== STORAGE ENDPOINTS (IN-MEMORY) ====================

@app.post("/api/searches/{search_id}/save")
def save_search_to_storage(search_id: str):
    """
    Save a flagged search to in-memory storage (without AI analysis)
    
    Example:
        POST /api/searches/1234567890.12345/save
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
        
        # Detect issues
        issues = SearchAnalyzer.detect_issues(search_data)
        search_data['issues'] = issues
        
        if issues:
            search_data['severity'] = SearchAnalyzer.calculate_severity(issues, search_data)
        else:
            search_data['severity'] = 'none'
        
        # Save to storage (without AI analysis)
        doc_id = storage.save_flagged_search(search_data)
        
        return {
            'status': 'success',
            'message': 'Search saved to storage',
            'search_id': search_id,
            'storage_count': storage.get_count()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/searches/{search_id}/analyze-and-save")
def analyze_and_save_search(search_id: str):
    """
    Analyze search with AI and save to storage
    
    Example:
        POST /api/searches/1234567890.12345/analyze-and-save
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
        
        # Save to storage with AI analysis
        doc_id = storage.save_flagged_search(search_data, ai_result)
        
        return {
            'status': 'success',
            'message': 'Search analyzed and saved to storage',
            'search_id': search_id,
            'storage_count': storage.get_count(),
            'ai_analysis': ai_result['analysis'],
            'optimized_spl': ai_result['optimized_spl'],
            'token_usage': ai_result['token_usage']
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/searches/history")
def get_search_history(
    limit: int = 100,
    severity: Optional[str] = None,
    has_ai_analysis: Optional[bool] = None
):
    """
    Get flagged search history from storage
    
    Args:
        limit: Max results (default 100)
        severity: Filter by severity (critical, high, medium, low)
        has_ai_analysis: Filter by AI analysis presence (true/false)
    
    Example:
        GET /api/searches/history?limit=50&severity=critical
    """
    try:
        searches = storage.get_recent_flagged_searches(
            limit=limit,
            severity=severity,
            has_ai_analysis=has_ai_analysis
        )
        
        return {
            'status': 'success',
            'count': len(searches),
            'total_stored': storage.get_count(),
            'searches': searches
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/searches/history/{search_id}")
def get_search_from_history(search_id: str):
    """
    Get a specific search from history
    
    Example:
        GET /api/searches/history/1234567890.12345
    """
    try:
        search = storage.get_search_by_id(s