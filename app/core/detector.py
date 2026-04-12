from typing import Dict, List

class SearchAnalyzer:    
    @staticmethod
    def parse_search_entry(entry: Dict) -> Dict:
        content = entry.get('content', {})
        scan_count = int(content.get('scanCount', 0))
        result_count = int(content.get('resultCount', 1))  # Avoid division by zero
        runtime = float(content.get('runDuration', 0))
        scan_ratio = scan_count / result_count if result_count > 0 else 0
        cpu_seconds = 0
        perf = content.get('performance', {})
        if perf and 'command.search' in perf:
            cpu_seconds = float(perf['command.search'].get('duration_secs', 0))
        
        return {
            'search_id': content.get('sid'),
            'user': content.get('author', 'unknown'),
            'search_spl': content.get('search', ''),
            'is_saved_search': content.get('isSavedSearch', False),
            'is_done': content.get('isDone', False),
            'is_failed': content.get('isFailed', False),  # ← ADDED
            'runtime': round(runtime, 2),
            'cpu_seconds': round(cpu_seconds, 2),
            'events_scanned': scan_count,
            'results_returned': result_count,
            'scan_ratio': round(scan_ratio, 2)
        }