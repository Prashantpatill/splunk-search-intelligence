import requests
import urllib3
from typing import Dict, List, Optional
from fastapi import HTTPException
import json
from app.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SplunkAPI:
    """Splunk REST API client with token authentication"""
    
    def __init__(self):
        self.host = settings.SPLUNK_HOST
        self.token = settings.SPLUNK_TOKEN
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request to Splunk REST API"""
        
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        url = f"{self.host}{endpoint}"
        
        if params is None:
            params = {}
        params['output_mode'] = 'json'
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="Auth failed: Check bearer token"
                )
            
            if response.status_code == 403:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: Token lacks permissions"
                )
            
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail=f"Splunk returned non-JSON: {response.text[:200]}"
                )
        
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Splunk request failed: {str(e)}"
            )
    
    def test_connection(self) -> Dict:
        """Test connection and get server info"""
        data = self.get('/services/server/info')
        entry = data.get('entry', [{}])[0]
        content = entry.get('content', {})
        
        return {
            'status': 'connected',
            'version': content.get('version'),
            'build': content.get('build'),
            'server_name': content.get('serverName')
        }
    
    def get_recent_searches(self, minutes: int = 5) -> List[Dict]:
    """Get recent search jobs"""
    params = {
        'count': 5000,
        'status_buckets': minutes * 60
    }
    
    data = self.get('/services/search/jobs', params=params)  ß
    return data.get('entry', [])

    
    