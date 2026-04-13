from typing import Dict, List
import re

class SearchAnalyzer:
    
    @staticmethod
    def parse_search_entry(entry: Dict) -> Dict:

        content = entry.get('content', {})
        
        scan_count = int(content.get('scanCount', 0))
        result_count = int(content.get('resultCount', 1))
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
            'is_failed': content.get('isFailed', False),
            
            'runtime': round(runtime, 2),
            'cpu_seconds': round(cpu_seconds, 2),
            'events_scanned': scan_count,
            'results_returned': result_count,
            'scan_ratio': round(scan_ratio, 2)
        }
    
    @staticmethod
    def _is_generating_command(spl: str) -> bool:

        spl_lower = spl.lower().strip()
        
        if spl_lower.startswith('|'):
            generating_commands = [
                '| rest',
                '| makeresults',
                '| inputlookup',
                '| metadata',
                '| dbinspect',
                '| datamodel',
                '| pivot'
            ]
            
            for cmd in generating_commands:
                if spl_lower.startswith(cmd):
                    return True
        
        return False
    
    @staticmethod
    def detect_issues(search_data: Dict) -> List[str]:

        issues = []
        spl = search_data['search_spl']
        runtime = search_data['runtime']
        scan_ratio = search_data['scan_ratio']
        events = search_data['events_scanned']
        
        if SearchAnalyzer._is_generating_command(spl):
            return []  
        
        if 'index=*' in spl:
            issues.append('index_wildcard')
        

        elif 'index=' not in spl and events > 0:
            issues.append('no_index')
        

        if 'earliest=' not in spl and 'latest=' not in spl and events > 100000:
            issues.append('no_time_constraint')
        
        if runtime > 300:
            issues.append('long_runtime')
        
        if scan_ratio > 1000 and events > 10000:
            issues.append('poor_scan_ratio')
        
        if scan_ratio > 10000 and events > 10000:
            issues.append('very_poor_scan_ratio')
        
        if events > 10000000:
            issues.append('high_event_volume')
        
        if '| transaction' in spl:
            issues.append('uses_transaction')
        
        if '| join' in spl:
            issues.append('uses_join')
        
        if spl.count('[search') > 1:
            issues.append('multiple_subsearches')
        
        return issues
    
    @staticmethod
    def calculate_severity(issues: List[str], search_data: Dict) -> str:

        if 'no_time_constraint' in issues:
            return 'critical'
        
        if search_data['scan_ratio'] > 100000:
            return 'critical'
        
        if any([
            'index_wildcard' in issues,
            'very_poor_scan_ratio' in issues,
            'high_event_volume' in issues,
            search_data['runtime'] > 600  
        ]):
            return 'high'
        
        if any([
            len(issues) >= 3,
            'long_runtime' in issues,
            'poor_scan_ratio' in issues,
            'uses_transaction' in issues
        ]):
            return 'medium'
        
        
        return 'low'