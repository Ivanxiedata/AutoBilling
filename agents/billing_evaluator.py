#!/usr/bin/env python3
"""
Billing Data Evaluator Agent for AutoBilling
AI agent responsible for evaluating if a page contains sufficient billing data (4+ months)
"""

import json
import re
from typing import Dict, List
from bs4 import BeautifulSoup

import ollama

from utils.config import OLLAMA_MODEL
from utils.prompts import PromptLibrary
from utils.utils import BillInfo


class BillingDataEvaluator:
    """AI agent that evaluates if a page contains sufficient billing data"""
    
    def __init__(self):
        self.model = OLLAMA_MODEL
    
    def evaluate_page_sufficiency(self, page_source: str) -> Dict:
        """
        Evaluate if current page has sufficient billing data (4+ months)
        
        Args:
            page_source: Raw HTML content of the page
            
        Returns:
            Dict with evaluation results including sufficiency, months found, data quality
        """
        try:
            print(f"🧠 AI evaluating page content for billing data sufficiency...")
            
            # Prepare clean page content for AI analysis
            page_content = self._prepare_page_content(page_source)
            
            # Get AI billing data evaluation
            prompt = PromptLibrary.get_prompt('billing_data_evaluation', page_content=page_content)
            
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 800
                }
            )
            
            response_content = response["message"]["content"]
            print(f"🤖 AI evaluation response preview: {response_content[:150]}...")
            
            # Parse AI response
            ai_evaluation = self._parse_ai_response(response_content)
            
            # Log evaluation results
            self._log_evaluation_results(ai_evaluation)
            
            return ai_evaluation
            
        except Exception as e:
            print(f"❌ AI billing evaluation failed: {e}")
            return self._get_default_evaluation()
    
    def extract_with_ai_guidance(self, billing_entries: List[Dict], extraction_orchestrator, page_source: str) -> BillInfo:
        """
        Use AI-identified billing entries to enhance extraction
        
        Args:
            billing_entries: List of billing entries found by AI
            extraction_orchestrator: Extraction orchestrator instance
            page_source: Raw HTML content
            
        Returns:
            Enhanced BillInfo with AI-guided data
        """
        try:
            print(f"🎯 Extracting data with AI guidance...")
            
            if not billing_entries:
                return BillInfo("AI guided extraction failed", 0.0, "No entries provided", 0.0)
            
            # Convert AI-found entries to BillInfo format
            all_bills = []
            current_amount = 0.0
            previous_amount = 0.0
            
            for i, entry in enumerate(billing_entries):
                date_str = entry.get('date', '')
                amount_str = entry.get('amount', '0')
                description = entry.get('description', 'Utility Bill')
                
                # Parse amount
                amount = self._parse_amount(amount_str)
                
                if amount > 0:
                    all_bills.append({
                        'date': date_str,
                        'amount': amount,
                        'description': description,
                        'type': 'bill'
                    })
                    
                    # Set current and previous amounts
                    if i == 0:
                        current_amount = amount
                    elif i == 1:
                        previous_amount = amount
            
            # Create enhanced BillInfo
            if all_bills:
                current_month = f"AI extracted {len(all_bills)} bills"
                enhanced_bill = BillInfo(current_month, current_amount, f"Previous: ${previous_amount}", previous_amount)
                enhanced_bill.all_bills = all_bills
                
                print(f"✅ AI guidance extracted {len(all_bills)} billing entries")
                return enhanced_bill
            else:
                return BillInfo("AI guidance found no valid amounts", 0.0, "No valid bills", 0.0)
                
        except Exception as e:
            print(f"❌ AI-guided extraction failed: {e}")
            return BillInfo("AI guided extraction error", 0.0, str(e), 0.0)
    
    def _prepare_page_content(self, page_source: str) -> str:
        """Prepare clean page content for AI analysis"""
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()
        
        # Get text content with some structure preserved
        page_text = soup.get_text(separator='\n', strip=True)
        
        # Limit content size for AI processing (keep most relevant parts)
        lines = page_text.split('\n')
        relevant_lines = []
        
        for line in lines:
            line = line.strip()
            if len(line) < 3:
                continue
            # Keep lines that might contain billing data
            if any(keyword in line.lower() for keyword in ['$', 'bill', 'amount', 'date', 'payment', 'due', 'balance', 'transaction']):
                relevant_lines.append(line)
            elif len(relevant_lines) < 50:  # Keep some context
                relevant_lines.append(line)
        
        # Limit to reasonable size for AI
        return '\n'.join(relevant_lines[:100])
    
    def _parse_ai_response(self, response_content: str) -> Dict:
        """Parse AI response with error handling"""
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                print(f"❌ Could not parse AI evaluation response")
                return self._get_default_evaluation()
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        try:
            # Extract numeric value from amount string
            amount_clean = re.sub(r'[^0-9.]', '', str(amount_str))
            return float(amount_clean) if amount_clean else 0.0
        except:
            return 0.0
    
    def _log_evaluation_results(self, ai_evaluation: Dict) -> None:
        """Log detailed evaluation results"""
        has_sufficient = ai_evaluation.get('has_sufficient_billing_data', False)
        months_found = ai_evaluation.get('months_of_data_found', 0)
        data_quality = ai_evaluation.get('data_quality', 'none')
        billing_entries = ai_evaluation.get('billing_entries_found', [])
        reason = ai_evaluation.get('evaluation_reason', 'No reason provided')
        
        print(f"🔍 AI Billing Evaluation Results:")
        print(f"   • Sufficient data: {has_sufficient}")
        print(f"   • Months found: {months_found}")
        print(f"   • Data quality: {data_quality}")
        print(f"   • Billing entries: {len(billing_entries)}")
        print(f"   • Reason: {reason}")
    
    def _get_default_evaluation(self) -> Dict:
        """Return default evaluation when AI fails"""
        return {
            'has_sufficient_billing_data': False, 
            'months_of_data_found': 0,
            'data_quality': 'none',
            'billing_entries_found': [],
            'evaluation_reason': 'AI evaluation failed'
        } 