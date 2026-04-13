from typing import Dict
from openai import AzureOpenAI
from app.config import settings

class AIAnalyzer:
    
    
    def __init__(self):
        """Initialize Azure OpenAI client"""
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_API_KEY,
            api_version=settings.AZURE_API_VERSION
        )
        self.model = settings.AZURE_MODEL_NAME
    
    
    @staticmethod
    def _build_general_analysis_prompt(search_data: Dict) -> str:
       
        
        spl = search_data['search_spl']
        runtime = search_data['runtime']
        events = search_data['events_scanned']
        results = search_data['results_returned']
        scan_ratio = search_data['scan_ratio']
        issues = search_data.get('issues', [])
        severity = search_data.get('severity', 'unknown')
        
        issues_formatted = ', '.join(issues) if issues else 'None'
        
        return f"""Analyze this Splunk search performance issue.

CURRENT SEARCH:
```spl
{spl}
```

METRICS:
- Runtime: {runtime}s
- Events Scanned: {events:,}
- Results Returned: {results:,}
- Scan Ratio: {scan_ratio:.0f}:1
- Severity: {severity}
- Issues: {issues_formatted}

OUTPUT FORMAT:
## Problem
[Root cause in 1-2 sentences]

## Optimized Query
```spl
[Rewritten SPL with improvements]
```

## Key Changes
- [Change 1]
- [Change 2]
- [Change 3]

## Expected Impact
[Estimated performance improvement]"""
    
    @staticmethod
    def _build_index_wildcard_prompt(search_data: Dict) -> str:
        """Index wildcard optimization prompt"""
        
        spl = search_data['search_spl']
        events = search_data['events_scanned']
        
        return f"""Fix index=* wildcard issue.

CURRENT:
```spl
{spl}
```

PROBLEM: Searches all indexes ({events:,} events scanned)

OUTPUT FORMAT:
## Analysis
[Identify data sources from search logic]

## Recommended Index
[Specific index name: index=X]

## Optimized Query
```spl
[Rewritten with specific index]
```

## Impact
Events scanned: {events:,} → [estimated new count]
Performance gain: [X]x faster"""
    
    @staticmethod
    def _build_no_time_constraint_prompt(search_data: Dict) -> str:
        """No time constraint optimization prompt"""
        
        spl = search_data['search_spl']
        runtime = search_data['runtime']
        events = search_data['events_scanned']
        
        return f"""Add time constraints to all-time search.

CURRENT:
```spl
{spl}
```

PROBLEM: No time bounds (searched {events:,} events, {runtime}s runtime)

OUTPUT FORMAT:
## Recommended Time Range
[Appropriate earliest/latest based on search purpose]

## Optimized Query
```spl
[Add earliest/latest to the query]
```

## Impact
- Scanned: {events:,} → [estimated]
- Runtime: {runtime}s → [estimated]s
- Speedup: [X]x faster"""
    
    @staticmethod
    def _build_transaction_optimization_prompt(search_data: Dict) -> str:
        """Transaction command optimization"""
        
        spl = search_data['search_spl']
        
        return f"""Replace transaction with stats-based alternative.

CURRENT:
```spl
{spl}
```

PROBLEM: transaction is memory-intensive and slow

OUTPUT FORMAT:
## Why Transaction is Slow
[1 sentence explanation]

## Stats Alternative
```spl
[Rewritten using stats/streamstats/eventstats]
```

## How It Works
[Brief explanation of the stats approach]

## Performance Gain
[Memory usage and speed improvement]"""
    
    @staticmethod
    def _build_poor_scan_ratio_prompt(search_data: Dict) -> str:
        """Poor scan ratio optimization"""
        
        spl = search_data['search_spl']
        scan_ratio = search_data['scan_ratio']
        events = search_data['events_scanned']
        results = search_data['results_returned']
        
        return f"""Improve scan efficiency.

CURRENT:
```spl
{spl}
```

EFFICIENCY ISSUE:
- Scanned: {events:,} events
- Returned: {results:,} results
- Ratio: {scan_ratio:.0f}:1 (inefficient)

OUTPUT FORMAT:
## Root Cause
[Why so many events scanned for few results]

## Optimization Strategy
[Filters to add early in pipeline]

## Optimized Query
```spl
[Rewritten with better filtering]
```

## New Efficiency
- New ratio: [estimated ratio]
- Events saved: {events:,} → [estimated]"""
    
    @staticmethod
    def _build_join_optimization_prompt(search_data: Dict) -> str:
        """Join command optimization"""
        
        spl = search_data['search_spl']
        
        return f"""Replace join with stats correlation.

CURRENT:
```spl
{spl}
```

PROBLEM: join creates Cartesian products, memory-intensive

OUTPUT FORMAT:
## Why Avoid Join
[1 sentence]

## Stats Alternative
```spl
[Rewritten using stats correlation]
```

## How It Works
[Explanation of correlation approach]

## Benefit
[Performance and memory improvement]"""
    
    # ==================== PROMPT SELECTOR ====================
    
    @staticmethod
    def _select_prompt(search_data: Dict) -> str:
        """
        Select the most appropriate prompt based on issues
        
        Priority order (most specific to general):
        1. No time constraint (critical)
        2. Index wildcard (high impact)
        3. Transaction command (specific fix)
        4. Join command (specific fix)
        5. Poor scan ratio (optimization)
        6. General analysis (fallback)
        """
        
        issues = search_data.get('issues', [])
        
        # Priority order - most critical first
        if 'no_time_constraint' in issues:
            return AIAnalyzer._build_no_time_constraint_prompt(search_data)
        
        if 'index_wildcard' in issues:
            return AIAnalyzer._build_index_wildcard_prompt(search_data)
        
        if 'uses_transaction' in issues:
            return AIAnalyzer._build_transaction_optimization_prompt(search_data)
        
        if 'uses_join' in issues:
            return AIAnalyzer._build_join_optimization_prompt(search_data)
        
        if 'very_poor_scan_ratio' in issues or 'poor_scan_ratio' in issues:
            return AIAnalyzer._build_poor_scan_ratio_prompt(search_data)
        
        return AIAnalyzer._build_general_analysis_prompt(search_data)
    
    # ==================== MAIN ANALYSIS METHOD ====================
    
    def analyze_search(self, search_data: Dict, prompt_type: str = "auto") -> Dict:
        
        if prompt_type == "auto":
            prompt = self._select_prompt(search_data)
            selected_type = "auto_selected"
        elif prompt_type == "general":
            prompt = self._build_general_analysis_prompt(search_data)
            selected_type = "general"
        elif prompt_type == "index_wildcard":
            prompt = self._build_index_wildcard_prompt(search_data)
            selected_type = "index_wildcard"
        elif prompt_type == "no_time":
            prompt = self._build_no_time_constraint_prompt(search_data)
            selected_type = "no_time"
        elif prompt_type == "transaction":
            prompt = self._build_transaction_optimization_prompt(search_data)
            selected_type = "transaction"
        elif prompt_type == "join":
            prompt = self._build_join_optimization_prompt(search_data)
            selected_type = "join"
        elif prompt_type == "scan_ratio":
            prompt = self._build_poor_scan_ratio_prompt(search_data)
            selected_type = "scan_ratio"
        else:
            prompt = self._build_general_analysis_prompt(search_data)
            selected_type = "general"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Splunk performance expert. "
                            "Follow the OUTPUT FORMAT exactly. "
                            "Use markdown headers (##) and code blocks (```spl```). "
                            "Be concise but professional. "
                            "Provide specific, actionable improvements."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4,      
                max_tokens=600,       
                top_p=0.95,          
                presence_penalty=0.1, 
                frequency_penalty=0.1 
            )
            
            return {
                "analysis": response.choices[0].message.content,
                "prompt_type": selected_type,
                "token_usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "model": self.model
            }
            
        except Exception as e:
            return {
                "analysis": f"**Error:** {str(e)}",
                "prompt_type": selected_type,
                "token_usage": None,
                "model": self.model,
                "error": str(e)
            }