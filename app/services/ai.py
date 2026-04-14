from typing import Dict
import re
import time
from openai import AzureOpenAI
from app.config import settings

class AIAnalyzer:
    """AI-powered search analysis using Azure OpenAI"""
    
    def __init__(self):
        """Initialize Azure OpenAI client"""
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_API_KEY,
            api_version=settings.AZURE_API_VERSION
        )
        self.model = settings.AZURE_MODEL_NAME

    
    @staticmethod
    def _build_multi_issue_prompt(search_data: Dict) -> str:
        """Ultra-compact comprehensive prompt for multiple issues"""
        
        spl = search_data['search_spl']
        rt = search_data['runtime']
        ev = search_data['events_scanned']
        res = search_data['results_returned']
        ratio = search_data['scan_ratio']
        issues = ', '.join([i.replace('_', ' ') for i in search_data.get('issues', [])])
        
        return f"""Fix: {issues}

SPL: {spl}
Stats: {rt}s runtime, {ev:,} events, {res:,} results, {ratio:.0f}:1 ratio

Output:
## Problems
[1-2 sentences]
## Optimized Query
```spl
[Complete fixed SPL]
```
## Changes
[Bullet list of fixes]
## Impact
[Performance estimate]"""
    
    @staticmethod
    def _build_general_analysis_prompt(search_data: Dict) -> str:
        """Ultra-compact general analysis prompt"""
        
        spl = search_data['search_spl']
        rt = search_data['runtime']
        ev = search_data['events_scanned']
        res = search_data['results_returned']
        issues = ', '.join(search_data.get('issues', [])) if search_data.get('issues') else 'None'
        
        return f"""Analyze performance.

SPL: {spl}
Stats: {rt}s, {ev:,} events, {res:,} results
Issues: {issues}

Output:
## Problem
[Root cause]
## Optimized Query
```spl
[Fixed SPL]
```
## Changes
[List]
## Impact
[Estimate]"""
    
    @staticmethod
    def _build_index_wildcard_prompt(search_data: Dict) -> str:
        """Ultra-compact index wildcard prompt"""
        
        spl = search_data['search_spl']
        ev = search_data['events_scanned']
        
        return f"""Fix index=* wildcard.

SPL: {spl}
Problem: Searches all indexes ({ev:,} events)

Output:
## Analysis
[Identify likely index from SPL]
## Recommended Index
[Specific index name]
## Optimized Query
```spl
[Fixed SPL with specific index]
```
## Impact
[Event reduction estimate]"""
    
    @staticmethod
    def _build_no_time_constraint_prompt(search_data: Dict) -> str:
        """Ultra-compact no time constraint prompt"""
        
        spl = search_data['search_spl']
        rt = search_data['runtime']
        ev = search_data['events_scanned']
        
        return f"""Add time bounds.

SPL: {spl}
Problem: No time constraint ({ev:,} events, {rt}s)

Output:
## Recommended Time
[Appropriate timespan based on use case]
## Optimized Query
```spl
[SPL with earliest/latest added]
```
## Impact
[Event and runtime reduction]"""
    
    @staticmethod
    def _build_transaction_optimization_prompt(search_data: Dict) -> str:
        """Ultra-compact transaction prompt"""
        
        spl = search_data['search_spl']
        
        return f"""Replace transaction with stats.

SPL: {spl}

Output:
## Why Slow
[1 sentence]
## Stats Alternative
```spl
[Rewritten using stats/streamstats]
```
## How It Works
[Brief explanation]
## Gain
[Performance improvement]"""
    
    @staticmethod
    def _build_poor_scan_ratio_prompt(search_data: Dict) -> str:
        """Ultra-compact scan ratio prompt"""
        
        spl = search_data['search_spl']
        ratio = search_data['scan_ratio']
        ev = search_data['events_scanned']
        res = search_data['results_returned']
        
        return f"""Improve scan efficiency.

SPL: {spl}
Issue: {ev:,} scanned, {res:,} returned, {ratio:.0f}:1 ratio

Output:
## Root Cause
[Why inefficient]
## Strategy
[Filters to add early]
## Optimized Query
```spl
[Fixed SPL]
```
## Efficiency
[New ratio estimate]"""
    
    @staticmethod
    def _build_join_optimization_prompt(search_data: Dict) -> str:
        """Ultra-compact join prompt"""
        
        spl = search_data['search_spl']
        
        return f"""Replace join with stats.

SPL: {spl}

Output:
## Why Avoid
[1 sentence]
## Stats Alternative
```spl
[Rewritten using stats correlation]
```
## How
[Brief explanation]
## Benefit
[Performance gain]"""
    
    
    @staticmethod
    def _select_prompt(search_data: Dict) -> str:
        
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
        """Analyze search using Azure OpenAI with retry logic for quota limits"""
        
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
        max_retries = 3
        retry_delay = 1  
        
        for attempt in range(max_retries):
            try:
                print(f"\n========== DEBUG: AI REQUEST (Attempt {attempt + 1}/{max_retries}) ==========")
                print(f"Prompt type: {selected_type}")
                print(f"Issues: {issues}")
                print(f"Prompt length: {len(prompt)} chars")
                
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
                
                finish_reason = response.choices[0].finish_reason
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                total_tokens = prompt_tokens + completion_tokens
                
                print(f"\n========== DEBUG: AI RESPONSE ==========")
                print(f"Finish reason: {finish_reason}")
                print(f"Prompt tokens: {prompt_tokens}")
                print(f"Completion tokens: {completion_tokens}")
                print(f"Total tokens: {total_tokens}")
                print(f"Response length: {len(response.choices[0].message.content)} chars")
                if finish_reason == "length" and attempt < max_retries - 1:
                    print(f"⚠️  Response truncated (likely quota limit)")
                    print(f"Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  
                    continue
                
                ai_analysis = response.choices[0].message.content
                optimized_spl = self._extract_optimized_spl(ai_analysis)
                
                if finish_reason == "length":
                    print(f"  Final response truncated - returning partial result")
                else:
                    print(f" Complete response received")
                
                
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
                    "finish_reason": finish_reason,
                    "truncated": finish_reason == "length",
                    "retry_count": attempt,
                    "skipped": False
                }
                
            except Exception as e:
                print(f"\n========== DEBUG: ERROR (Attempt {attempt + 1}) ==========")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    print(f"Max retries exceeded")
                    return {
                        "analysis": f"Error: {str(e)}",
                        "optimized_spl": "",
                        "prompt_type": selected_type,
                        "token_usage": None,
                        "model": self.model,
                        "error": str(e),
                        "retry_count": attempt,
                        "skipped": False
                    }
        
        return {
            "analysis": "Error: Max retries exceeded",
            "optimized_spl": "",
            "prompt_type": selected_type,
            "token_usage": None,
            "model": self.model,
            "error": "Max retries exceeded",
            "skipped": False
        }