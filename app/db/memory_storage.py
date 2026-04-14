from typing import List, Dict, Optional
from datetime import datetime, timezone
import threading

class InMemoryStorage:
    """In-memory storage for flagged searches (testing/demo purposes)"""
    
    def __init__(self):
        """Initialize in-memory storage"""
        self.searches = {}  # key: search_id, value: search document
        self.lock = threading.Lock()  # Thread-safe operations
    
    def save_flagged_search(self, search_data: Dict, ai_result: Optional[Dict] = None) -> str:
        """
        Save a flagged search to memory
        
        Args:
            search_data: Parsed search data with issues
            ai_result: Optional AI analysis result
            
        Returns:
            search_id
        """
        
        with self.lock:
            document = {
                # Search identity
                'search_id': search_data['search_id'],
                'user': search_data['user'],
                'search_spl': search_data['search_spl'],
                'is_saved_search': search_data['is_saved_search'],
                
                # Performance metrics
                'runtime': search_data['runtime'],
                'events_scanned': search_data['events_scanned'],
                'results_returned': search_data['results_returned'],
                'scan_ratio': search_data['scan_ratio'],
                
                # Issues
                'issues': search_data['issues'],
                'severity': search_data['severity'],
                
                # AI Analysis (if provided)
                'ai_analyzed': ai_result is not None,
                'ai_analysis': ai_result.get('analysis') if ai_result else None,
                'optimized_spl': ai_result.get('optimized_spl') if ai_result else None,
                'prompt_type': ai_result.get('prompt_type') if ai_result else None,
                'token_usage': ai_result.get('token_usage') if ai_result else None,
                'finish_reason': ai_result.get('finish_reason') if ai_result else None,
                'truncated': ai_result.get('truncated', False) if ai_result else False,
                'retry_count': ai_result.get('retry_count', 0) if ai_result else 0,
                
                # Metadata
                'flagged_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Store in memory
            self.searches[search_data['search_id']] = document
            
            return search_data['search_id']
    
    def get_recent_flagged_searches(
        self, 
        limit: int = 100,
        severity: Optional[str] = None,
        has_ai_analysis: Optional[bool] = None
    ) -> List[Dict]:
        """
        Get recent flagged searches from memory
        
        Args:
            limit: Maximum number of results
            severity: Filter by severity (critical, high, medium, low)
            has_ai_analysis: Filter by AI analysis presence
            
        Returns:
            List of flagged search documents
        """
        
        with self.lock:
            searches = list(self.searches.values())
            
            # Apply filters
            if severity:
                searches = [s for s in searches if s['severity'] == severity]
            
            if has_ai_analysis is not None:
                searches = [s for s in searches if s['ai_analyzed'] == has_ai_analysis]
            
            # Sort by flagged_at (most recent first)
            searches.sort(key=lambda x: x['flagged_at'], reverse=True)
            
            # Limit results
            return searches[:limit]
    
    def get_search_by_id(self, search_id: str) -> Optional[Dict]:
        """
        Get a specific flagged search by search_id
        
        Args:
            search_id: Splunk search ID
            
        Returns:
            Search document or None
        """
        
        with self.lock:
            return self.searches.get(search_id)
    
    def get_stats(self) -> Dict:
        """
        Get statistics about flagged searches
        
        Returns:
            Dict with counts by severity, issues, etc.
        """
        
        with self.lock:
            searches = list(self.searches.values())
            
            # Count by severity
            severity_counts = {}
            for search in searches:
                sev = search['severity']
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            # Count AI analyzed
            ai_analyzed = sum(1 for s in searches if s['ai_analyzed'])
            
            # Count by issue type
            issue_counts = {}
            for search in searches:
                for issue in search['issues']:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1
            
            return {
                'total_flagged': len(searches),
                'ai_analyzed_count': ai_analyzed,
                'severity_breakdown': severity_counts,
                'issue_breakdown': issue_counts
            }
    
    def clear_all(self) -> int:
        """
        Clear all stored searches (useful for testing)
        
        Returns:
            Number of cleared searches
        """
        
        with self.lock:
            count = len(self.searches)
            self.searches.clear()
            return count
    
    def get_count(self) -> int:
        """Get total count of stored searches"""
        with self.lock:
            return len(self.searches)

# Singleton instance
memory_storage = InMemoryStorage()