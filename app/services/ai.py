from typing import Dict
import re
from openai import AzureOpenAI
from app.config import settings

class AIAnalyzer:
   
    
    def __init__(self):
       
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_API_KEY,
            api_version=settings.AZURE_API_VERSION
        )
        self.model = settings.AZURE_MODEL_NAME
    
   
    
    @staticmethod
    def _build_multi_issue_prompt(search_data: Dict) -> str:
        """Comprehensive prompt for multiple issues"""
        
        spl = search_data['search_spl']
        runtime = search_data['runtime']
        events = search_data['events_scanned']
        results = search_data['results_returned']
        scan_ratio = search_data['scan_ratio']
        issues = search_data.get('issues', [])
        severity = search_data.get('severity', 'unknown')
        
        issues_list = ', '.join([issue.replace('_', ' ') for issue in issues])
        
        return f"""Fix ALL performance issues.

CURRENT: {spl}

METRICS: Runtime {runtime}s, Events {events:,}, Results {results:,}, Ratio {scan_ratio:.0f}:1, Severity {severity}

ISSUES: {issues_list}

FORMAT:
## Problems
[Brief explanation]

## Optimized Query
```spl
[Complete rewritten SPL]
```

## Changes
[List fixes]

## Impact
[Performance improvement]"""
    
    @staticmethod
    def _build_general_analysis_prompt(search_data: Dict) -> str:
        """General analysis prompt"""
        
        spl = search_data['search_spl']
        runtime = search_data['runtime']
        events = search_data['events_scanned']
        results = search_data['results_returned']
        scan_ratio = search_data['scan_ratio']
        issues = search_data.get('issues', [])
        
        issues_formatted = ', '.join(issues) if issues else 'None'
        
        return f"""Analyze Splunk search performance.

CURRENT: {spl}

METRICS: Runtime {runtime}s, Events {events:,}, Results {results:,}, Ratio {scan_ratio:.0f}:1, Issues {issues_formatted}

FORMAT:
## Problem
[Root cause]

## Optimized Query
```spl
[Rewritten SPL]
```

## Changes
[List changes]

## Impact
[Performance gain]"""
    
    @staticmethod
    def _build_index_wildcard_prompt(search_data: Dict) -> str:
        """Index wildcard optimization"""
        
        spl = search_data['search_spl']
        events = search_data['events_scanned']
        
        return f"""Fix index=* wildcard.

CURRENT: {spl}

PROBLEM: Searches all indexes ({events:,} events)

FORMAT:
## Analysis
[Identify data source]

## Recommended Index
[Specific index]

## Optimized Query
```spl
[Rewritten with specific index]
```

## Impact
Events {events:,} to [estimated], [X]x faster"""
    
    @staticmethod
    def _build_no_time_constraint_prompt(search_data: Dict) -> str:
        """No time constraint optimization"""
        
        spl = search_data['search_spl']
        runtime = search_data['runtime']
        events = search_data['events_scanned']
        
        return f"""Add time constraints.

CURRENT: {spl}

PROBLEM: No time bounds ({events:,} events, {runtime}s)

FORMAT:
## Recommended Time
[Appropriate timespan]

## Optimized Query
```spl
[Query with time bounds]
```

## Impact
Events {events:,} to [est], Runtime {runtime}s to [est]s, [X]x faster"""
    
    @staticmethod
    def _build_transaction_optimization_prompt(search_data: Dict) -> str:
        """Transaction command optimization"""
        
        spl = search_data['search_spl']
        
        return f"""Replace transaction with stats.

CURRENT: {spl}

PROBLEM: transaction is memory-intensive

FORMAT:
## Why Slow
[1 sentence]

## Stats Alternative
```spl
[Rewritten using stats]
```

## How It Works
[Brief explanation]

## Gain
[Improvement]"""
    
    @staticmethod
    def _build_poor_scan_ratio_prompt(search_data: Dict) -> str:
        """Poor scan ratio optimization"""
        
        spl = search_data['search_spl']
        scan_ratio = search_data['scan_ratio']
        events = search_data['events_scanned']
        results = search_data['results_returned']
        
        return f"""Improve scan efficiency.

CURRENT: {spl}

ISSUE: Scanned {events:,}, Returned {results:,}, Ratio {scan_ratio:.0f}:1

FORMAT:
## Root Cause
[Why inefficient]

## Strategy
[Filters to add]

## Optimized Query
```spl
[Rewritten]
```

## Efficiency
New ratio [est], Events saved [est]"""
    
    @staticmethod
    def _build_join_optimization_prompt(search_data: Dict) -> str:
        """Join command optimization"""
        
        spl = search_data['search_spl']
        
        return f"""Replace join with stats.

CURRENT: {spl}

PROBLEM: join creates Cartesian products

FORMAT:
## Why Avoid
[1 sentence]

## Stats Alternative
```spl
[Rewritten]
```

## Works
[Explanation]

## Benefit
[Improvement]"""
    

    
    @staticmethod
    def _select_prompt(search_data: Dict) -> str:
        """Select prompt based on number of issues"""
        
        issues = search_data.get('issues', [])
        
        if not issues:
            return AIAnalyzer._build_general_analysis_prompt(search_data)
        
       
        if len(issues) > 1:
            return AIAnalyzer._build_multi_issue_prompt(search_data)
        
    
        single_issue = issues[0]
        
        if single_issue == 'index_wildcard':
            return AIAnalyzer._build_index_wildcard_prompt(search_data)
        
        if single_issue == 'no_time_constraint':
            return AIAnalyzer._build_no_time_constraint_prompt(search_data)
        
        if single_issue == 'uses_transaction':
            return AIAnalyzer._build_transaction_optimization_prompt(search_data)
        
        if single_issue == 'uses_join':
            return AIAnalyzer._build_join_optimization_prompt(search_data)
        
        if single_issue in ['poor_scan_ratio', 'very_poor_scan_ratio']:
            return AIAnalyzer._build_poor_scan_ratio_prompt(search_data)
        
        return AIAnalyzer._build_general_analysis_prompt(search_data)
    

    
    @staticmethod
    def _extract_optimized_spl(ai_response: str) -> str:
        """Extract optimized SPL from AI response"""
        
        # Look for ```spl ... ```
        spl_pattern = r'```spl\s+(.*?)\s+```'
        match = re.search(spl_pattern, ai_response, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        # Look for any ``` ... ``` with SPL
        generic_pattern = r'```\s+(.*?)\s+```'
        matches = re.findall(generic_pattern, ai_response, re.DOTALL)
        
        for code_block in matches:
            if any(kw in code_block.lower() for kw in ['index=', '|', 'search', 'stats', 'where']):
                return code_block.strip()
        
        return ""
    
  
    
    def analyze_search(self, search_data: Dict, prompt_type: str = "auto") -> Dict:
        """Analyze search using Azure OpenAI with debug logging"""
        
        issues = search_data.get('issues', [])
        
    
        if not issues:
            return {
                "analysis": "No performance issues detected.",
                "optimized_spl": "",
                "prompt_type": "none",
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "model": self.model,
                "skipped": True
            }
        
  
        if prompt_type == "auto":
            prompt = self._select_prompt(search_data)
            
            if len(issues) > 1:
                selected_type = f"multi_issue_{len(issues)}_issues"
            elif len(issues) == 1:
                selected_type = f"single_issue_{issues[0]}"
            else:
                selected_type = "general"
        else:
            if prompt_type == "multi_issue":
                prompt = self._build_multi_issue_prompt(search_data)
            elif prompt_type == "general":
                prompt = self._build_general_analysis_prompt(search_data)
            elif prompt_type == "index_wildcard":
                prompt = self._build_index_wildcard_prompt(search_data)
            elif prompt_type == "no_time":
                prompt = self._build_no_time_constraint_prompt(search_data)
            elif prompt_type == "transaction":
                prompt = self._build_transaction_optimization_prompt(search_data)
            elif prompt_type == "join":
                prompt = self._build_join_optimization_prompt(search_data)
            elif prompt_type == "scan_ratio":
                prompt = self._build_poor_scan_ratio_prompt(search_data)
            else:
                prompt = self._build_general_analysis_prompt(search_data)
            
            selected_type = prompt_type
        

        try:
            print(f"\n========== DEBUG: AI ANALYSIS REQUEST ==========")
            print(f"Prompt type: {selected_type}")
            print(f"Issues: {issues}")
            print(f"Prompt length: {len(prompt)} chars")
            print(f"Prompt preview: {prompt[:300]}...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Splunk expert. Follow FORMAT exactly. Use markdown (##, ```spl```). Be concise, specific, actionable."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=1500,
                top_p=1.0,
                presence_penalty=0.0,
                frequency_penalty=0.0
            )
            print(f"\n========== DEBUG: AI RESPONSE ==========")
            print(f"Finish reason: {response.choices[0].finish_reason}")
            print(f"Prompt tokens: {response.usage.prompt_tokens}")
            print(f"Completion tokens: {response.usage.completion_tokens}")
            print(f"Total tokens (reported): {response.usage.total_tokens}")
            print(f"Total tokens (calculated): {response.usage.prompt_tokens + response.usage.completion_tokens}")
            print(f"Response length: {len(response.choices[0].message.content)} chars")
            print(f"Response preview: {response.choices[0].message.content[:500]}...")
            print(f"Response end: ...{response.choices[0].message.content[-200:]}")
            print(f"==========================================\n")
            
            ai_analysis = response.choices[0].message.content
            optimized_spl = self._extract_optimized_spl(ai_analysis)
            
            # Calculate tokens ourselves
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            
            return {
                "analysis": ai_analysis,
                "optimized_spl": optimized_spl,
                "prompt_type": selected_type,
                "token_usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                "model": self.model,
                "finish_reason": response.choices[0].finish_reason,
                "skipped": False
            }
            
        except Exception as e:
            print(f"\n========== DEBUG: ERROR ==========")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"===================================\n")
            
            return {
                "analysis": f"Error: {str(e)}",
                "optimized_spl": "",
                "prompt_type": selected_type,
                "token_usage": None,
                "model": self.model,
                "error": str(e),
                "skipped": False
            }