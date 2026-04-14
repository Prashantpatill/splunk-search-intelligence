from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Optional
from datetime import datetime, timezone
from app.config import settings

class MongoDB:
    """MongoDB operations for storing flagged searches"""
    
    def __init__(self):
        """Initialize MongoDB connection"""
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.searches_collection = self.db['flagged_searches']
    
    async def save_flagged_search(self, search_data: Dict, ai_result: Optional[Dict] = None) -> str:
        """
        Save a flagged search to MongoDB
        
        Args:
            search_data: Parsed search data with issues
            ai_result: Optional AI analysis result
            
        Returns:
            MongoDB document ID
        """
        
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
            
            # Metadata
            'flagged_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        # Upsert: update if exists, insert if new
        result = await self.searches_collection.update_one(
            {'search_id': search_data['search_id']},
            {'$set': document},
            upsert=True
        )
        
        return str(result.upserted_id) if result.upserted_id else search_data['search_id']
    
    async def get_recent_flagged_searches(
        self, 
        limit: int = 100,
        severity: Optional[str] = None,
        has_ai_analysis: Optional[bool] = None
    ) -> List[Dict]:
        """
        Get recent flagged searches from MongoDB
        
        Args:
            limit: Maximum number of results
            severity: Filter by severity (critical, high, medium, low)
            has_ai_analysis: Filter by AI analysis presence
            
        Returns:
            List of flagged search documents
        """
        
        query = {}
        
        if severity:
            query['severity'] = severity
        
        if has_ai_analysis is not None:
            query['ai_analyzed'] = has_ai_analysis
        
        cursor = self.searches_collection.find(query).sort('flagged_at', -1).limit(limit)
        
        searches = []
        async for document in cursor:
            # Convert ObjectId to string
            document['_id'] = str(document['_id'])
            searches.append(document)
        
        return searches
    
    async def get_search_by_id(self, search_id: str) -> Optional[Dict]:
        """
        Get a specific flagged search by search_id
        
        Args:
            search_id: Splunk search ID
            
        Returns:
            Search document or None
        """
        
        document = await self.searches_collection.find_one({'search_id': search_id})
        
        if document:
            document['_id'] = str(document['_id'])
        
        return document
    
    async def get_stats(self) -> Dict:
        """
        Get statistics about flagged searches
        
        Returns:
            Dict with counts by severity, issues, etc.
        """
        
        pipeline = [
            {
                '$group': {
                    '_id': '$severity',
                    'count': {'$sum': 1}
                }
            }
        ]
        
        severity_counts = {}
        async for doc in self.searches_collection.aggregate(pipeline):
            severity_counts[doc['_id']] = doc['count']
        
        total = await self.searches_collection.count_documents({})
        ai_analyzed = await self.searches_collection.count_documents({'ai_analyzed': True})
        
        return {
            'total_flagged': total,
            'ai_analyzed_count': ai_analyzed,
            'severity_breakdown': severity_counts
        }
    
    async def delete_old_searches(self, days: int = 90) -> int:
        """
        Delete searches older than specified days
        
        Args:
            days: Delete searches older than this many days
            
        Returns:
            Number of deleted documents
        """
        
        cutoff_date = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)
        
        result = await self.searches_collection.delete_many({
            'flagged_at': {'$lt': datetime.fromtimestamp(cutoff_date, tz=timezone.utc)}
        })
        
        return result.deleted_count

# Singleton instance
mongodb = MongoDB()