#!/usr/bin/env python3
"""
Data extraction strategies for AutoBilling
Different approaches to extract billing data from web pages
"""

import re
import json
import base64
import requests
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

import ollama
from bs4 import BeautifulSoup

from .config import (
    OLLAMA_MODEL, VISION_MODEL, USER_AGENT, MAX_HTML_LENGTH,
    DATE_PATTERNS, AMOUNT_PATTERNS, MAX_TOTAL_TRANSACTIONS,
    MIN_UTILITY_AMOUNT, MAX_UTILITY_AMOUNT
)
from .utils import (
    BillInfo, extract_dates_and_amounts, parse_date_flexible,
    is_valid_utility_date, deduplicate_transactions, has_meaningful_billing_data,
    extract_account_number_from_url, truncate_html_content
)

# Check for Vision AI availability
try:
    from PIL import Image
    VISION_AI_AVAILABLE = True
except ImportError:
    VISION_AI_AVAILABLE = False

class ExtractionStrategy(ABC):
    """Abstract base class for extraction strategies"""
    
    @abstractmethod
    def extract(self, page_source: str, driver=None) -> BillInfo:
        """Extract billing data from page source"""
        pass

class APIExtractionStrategy(ExtractionStrategy):
    """Extract data by calling discovered API endpoints directly"""
    
    def __init__(self):
        self.session_cookies = {}
    
    def extract(self, page_source: str, driver=None) -> BillInfo:
        """Try to find and call billing APIs"""
        print("🔍 Trying API extraction...")
        
        if not driver:
            return BillInfo("No driver", 0.0, "API extraction needs driver", 0.0)
        
        # Get session cookies for authentication
        cookies = driver.get_cookies()
        self.session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
        
        # Extract API endpoints from page
        api_endpoints = self._extract_api_endpoints(page_source, driver.current_url)
        
        if not api_endpoints:
            return BillInfo("No APIs found", 0.0, "No API endpoints detected", 0.0)
        
        # Try each API endpoint
        for endpoint in api_endpoints:
            api_data = self._call_api(endpoint)
            if api_data:
                return self._parse_api_response(api_data)
        
        return BillInfo("API calls failed", 0.0, "No working API endpoints", 0.0)
    
    def _extract_api_endpoints(self, html_content: str, current_url: str) -> List[Dict]:
        """Extract potential API endpoints from JavaScript"""
        endpoints = []
        base_url = '/'.join(current_url.split('/')[:3])
        
        # Common API patterns
        api_patterns = [
            r'["\']([^"\']*\/api\/[^"\']*billing[^"\']*)["\']',
            r'["\']([^"\']*\/api\/[^"\']*transaction[^"\']*)["\']',
            r'["\']([^"\']*\/api\/[^"\']*history[^"\']*)["\']',
            r'fetch\s*\(\s*["\']([^"\']+)["\']',
            r'axios\.get\s*\(\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if any(keyword in match.lower() for keyword in ['billing', 'transaction', 'history']):
                    full_url = base_url + match if match.startswith('/') else match
                    endpoints.append({
                        'url': full_url,
                        'method': 'GET',
                        'type': 'api'
                    })
        
        return endpoints[:10]  # Limit to top 10
    
    def _call_api(self, endpoint: Dict) -> Optional[Dict]:
        """Call API endpoint with session authentication"""
        try:
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'application/json',
                'Referer': endpoint['url']
            }
            
            response = requests.get(
                endpoint['url'],
                headers=headers,
                cookies=self.session_cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            pass
        
        return None
    
    def _parse_api_response(self, json_data: Dict) -> BillInfo:
        """Parse JSON API response for billing data"""
        bills = []
        
        # Look for data arrays
        possible_keys = ['data', 'results', 'bills', 'transactions', 'history']
        billing_data = None
        
        for key in possible_keys:
            if key in json_data and isinstance(json_data[key], list):
                billing_data = json_data[key]
                break
        
        if not billing_data and isinstance(json_data, list):
            billing_data = json_data
        
        if billing_data:
            for item in billing_data:
                date_fields = ['date', 'billDate', 'transactionDate']
                amount_fields = ['amount', 'billAmount', 'totalAmount']
                
                bill_date = None
                bill_amount = None
                
                # Extract date
                for field in date_fields:
                    if field in item:
                        try:
                            date_str = str(item[field])
                            bill_date = datetime.strptime(date_str, '%Y-%m-%d')
                            break
                        except:
                            continue
                
                # Extract amount
                for field in amount_fields:
                    if field in item:
                        try:
                            bill_amount = float(str(item[field]).replace('$', '').replace(',', ''))
                            break
                        except:
                            continue
                
                if bill_date and bill_amount:
                    bills.append({
                        'date': bill_date,
                        'amount': bill_amount,
                        'type': 'bill',
                        'description': f"API Bill - {item.get('description', 'Utility Service')}"
                    })
        
        if bills:
            # Use HTMLExtractionStrategy's _create_bill_info method for consistent latest-per-month filtering
            html_strategy = HTMLExtractionStrategy()
            return html_strategy._create_bill_info(bills, None)
        
        return BillInfo("No API data", 0.0, "No parseable API data", 0.0)

class HTMLExtractionStrategy(ExtractionStrategy):
    """Extract data from HTML tables and structured content"""
    
    def extract(self, page_source: str, driver=None) -> BillInfo:
        """Extract billing data from HTML"""
        print("🔍 Trying HTML extraction...")
        
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find transaction containers
        transaction_containers = self._find_transaction_containers(soup)
        
        if not transaction_containers:
            # Try AI-powered extraction as fallback
            ai_result = self._try_ai_html_extraction(page_source)
            if ai_result and hasattr(ai_result, 'all_bills') and ai_result.all_bills:
                return ai_result
            return self._extract_dashboard_amounts(soup, driver)
        
        # Extract historical data
        historical_data = self._extract_historical_transactions(transaction_containers)
        
        if not historical_data:
            # Try AI-powered extraction as fallback
            ai_result = self._try_ai_html_extraction(page_source)
            if ai_result and hasattr(ai_result, 'all_bills') and ai_result.all_bills:
                return ai_result
            return self._extract_dashboard_amounts(soup, driver)
        
        # Process and return results
        return self._create_bill_info(historical_data, driver)
    
    def _find_transaction_containers(self, soup) -> List:
        """Find elements likely to contain transaction data"""
        containers = []
        
        # Look for tables first (most reliable)
        tables = soup.find_all('table')
        for table in tables:
            table_text = table.get_text().lower()
            if any(keyword in table_text for keyword in ['date', 'amount', 'transaction', 'bill']):
                if len(table.find_all('tr')) >= 3:  # At least header + 2 rows
                    containers.append(table)
        
        # Look for other structured containers if no good tables
        if len(containers) < 1:
            selectors = ['[class*="transaction"]', '[class*="billing"]', '[class*="history"]']
            for selector in selectors:
                elements = soup.select(selector)
                for element in elements:
                    if len(element.get_text()) > 100:  # Has substantial content
                        containers.append(element)
        
        return containers
    
    def _extract_historical_transactions(self, containers: List) -> List[Dict]:
        """Extract transaction data from containers"""
        historical_data = []
        
        for container in containers:
            # Find rows within container
            if container.name == 'table':
                rows = container.find_all('tr')
            else:
                rows = container.find_all(['div', 'tr', 'li'])
            
            for row in rows:
                row_text = row.get_text()
                transactions = extract_dates_and_amounts(row_text)
                
                for transaction in transactions:
                    # Determine transaction type
                    transaction_type = 'bill'
                    if any(word in row_text.lower() for word in ['payment', 'paid', 'credit']):
                        transaction_type = 'payment'
                    
                    historical_data.append({
                        'date': transaction['date'],
                        'amount': transaction['amount'],
                        'type': transaction_type,
                        'description': row_text.strip()[:100]
                    })
                
                # Limit per container to avoid duplicates
                if len(historical_data) >= MAX_TOTAL_TRANSACTIONS:
                    break
        
        return deduplicate_transactions(historical_data)
    
    def _extract_dashboard_amounts(self, soup, driver) -> BillInfo:
        """Extract billing amounts from dashboard/overview pages"""
        print("🏠 Extracting dashboard billing amounts...")
        
        amounts = []
        dates = []
        
        # Enhanced dashboard patterns for SPA applications
        dashboard_patterns = [
            # Current bill patterns
            (r'current.*bill.*amount.*\$?([\d,]+\.?\d*)', 'current_bill'),
            (r'amount.*due.*\$?([\d,]+\.?\d*)', 'amount_due'),
            (r'balance.*\$?([\d,]+\.?\d*)', 'balance'),
            (r'bill.*amount.*\$?([\d,]+\.?\d*)', 'bill_amount'),
            # Payment patterns  
            (r'last.*payment.*\$?([\d,]+\.?\d*)', 'last_payment'),
            (r'payment.*amount.*\$?([\d,]+\.?\d*)', 'payment_amount'),
            (r'paid.*\$?([\d,]+\.?\d*)', 'paid_amount'),
            # General amount patterns
            (r'\$\s*([\d,]+\.?\d*)', 'dollar_amount')
        ]
        
        # Date patterns for dashboard
        date_patterns = [
            r'(?:paid|due|on)\s+([a-zA-Z]+ \d{1,2},? \d{4})',  # "paid July 17, 2025"
            r'(\d{1,2}/\d{1,2}/\d{4})',  # "07/17/2025"
            r'(\d{4}-\d{1,2}-\d{1,2})',  # "2025-07-17"
            r'([a-zA-Z]+ \d{4})',  # "July 2025"
        ]
        
        page_text = soup.get_text()
        
        # Extract amounts with context
        for pattern, amount_type in dashboard_patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    if amount > 0 and amount < 10000:  # Reasonable utility bill range
                        # Try to find associated date near this amount
                        context_start = max(0, match.start() - 100)
                        context_end = min(len(page_text), match.end() + 100)
                        context = page_text[context_start:context_end]
                        
                        # Look for date in context
                        amount_date = None
                        for date_pattern in date_patterns:
                            date_match = re.search(date_pattern, context, re.IGNORECASE)
                            if date_match:
                                try:
                                    date_str = date_match.group(1)
                                    # Try different date formats
                                    for fmt in ['%B %d, %Y', '%m/%d/%Y', '%Y-%m-%d', '%B %Y']:
                                        try:
                                            amount_date = datetime.strptime(date_str, fmt)
                                            break
                                        except:
                                            continue
                                    if amount_date:
                                        break
                                except:
                                    continue
                        
                        # If no date found, use current date for current bills
                        if not amount_date and amount_type in ['current_bill', 'amount_due', 'balance']:
                            amount_date = datetime.now()
                        
                        if amount_date:
                            amounts.append({
                                'amount': amount,
                                'date': amount_date,
                                'type': amount_type,
                                'description': f"Dashboard {amount_type.replace('_', ' ').title()}"
                            })
                            print(f"   💰 Found {amount_type}: ${amount:.2f} on {amount_date.strftime('%m/%d/%Y')}")
                        
                except (ValueError, IndexError):
                    continue
        
        # If we found amounts, create BillInfo
        if amounts:
            # Sort by date (newest first)
            amounts.sort(key=lambda x: x['date'], reverse=True)
            
            # Apply latest-per-month filtering
            monthly_latest = {}
            for amount_data in amounts:
                date_obj = amount_data['date']
                month_key = f"{date_obj.year}-{date_obj.month:02d}"
                
                # Prioritize current bill amounts over payments for the same month
                if month_key not in monthly_latest:
                    monthly_latest[month_key] = {
                        'date': date_obj,
                        'amount': amount_data['amount'],
                        'type': 'bill',
                        'description': amount_data['description'],
                        'amount_type': amount_data['type']
                    }
                else:
                    # If we already have an entry for this month, prioritize current bill amounts
                    existing_type = monthly_latest[month_key].get('amount_type', '')
                    new_type = amount_data['type']
                    
                    # Priority order: current_bill > amount_due > balance > bill_amount > payment amounts
                    priority_order = {
                        'current_bill': 1, 'amount_due': 2, 'balance': 3, 'bill_amount': 4,
                        'last_payment': 5, 'payment_amount': 6, 'paid_amount': 7, 'dollar_amount': 8
                    }
                    
                    existing_priority = priority_order.get(existing_type, 9)
                    new_priority = priority_order.get(new_type, 9)
                    
                    # Replace if new type has higher priority (lower number) or higher amount with same priority
                    if (new_priority < existing_priority or 
                        (new_priority == existing_priority and amount_data['amount'] > monthly_latest[month_key]['amount'])):
                        monthly_latest[month_key] = {
                            'date': date_obj,
                            'amount': amount_data['amount'],
                            'type': 'bill',
                            'description': amount_data['description'],
                            'amount_type': amount_data['type']
                        }
                        print(f"   🔄 Replaced {existing_type} (${monthly_latest[month_key]['amount']:.2f}) with {new_type} (${amount_data['amount']:.2f}) for {month_key}")
            
            # Convert to list and sort
            filtered_bills = list(monthly_latest.values())
            # Remove the amount_type field before returning (not needed in BillInfo)
            for bill in filtered_bills:
                bill.pop('amount_type', None)
            filtered_bills.sort(key=lambda x: x['date'], reverse=True)
            
            if filtered_bills:
                current_bill = filtered_bills[0]
                previous_bill = filtered_bills[1] if len(filtered_bills) > 1 else None
                
                account_number = extract_account_number_from_url(driver.current_url) if driver else None
                
                result = BillInfo(
                    previous_month=f"Previous ({previous_bill['date'].strftime('%m/%d/%Y')})" if previous_bill else "No previous",
                    previous_amount=previous_bill['amount'] if previous_bill else 0.0,
                    current_month=f"Current ({current_bill['date'].strftime('%m/%d/%Y')})",
                    current_amount=current_bill['amount'],
                    account_number=account_number or "Dashboard Data"
                )
                
                result.all_bills = filtered_bills
                print(f"📊 Dashboard extraction: {len(filtered_bills)} bills from {len(amounts)} total amounts")
                return result
        
        # Original fallback logic
        current_amount = 0.0
        
        # Look for simple amount patterns
        amount_patterns = [
            r'\$\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*dollars?',
            r'amount:?\s*\$?([\d,]+\.?\d*)'
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                try:
                    amount = float(match.replace(',', ''))
                    if 10.0 <= amount <= 5000.0:  # Reasonable utility bill range
                        current_amount = max(current_amount, amount)
                except ValueError:
                    continue
        
        if current_amount > 0:
            account_number = extract_account_number_from_url(driver.current_url) if driver else None
            
            return BillInfo(
                previous_month="No previous data",
                previous_amount=0.0,
                current_month="Current Bill",
                current_amount=current_amount,
                account_number=account_number or "Unknown"
            )
        
        return BillInfo("No HTML data found", 0.0, "No extractable amounts", 0.0)
    
    def _create_bill_info(self, transactions: List[Dict], driver) -> BillInfo:
        """Create BillInfo from transaction list with latest date per month filtering"""
        if not transactions:
            return BillInfo("No transactions", 0.0, "No valid transactions", 0.0)
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        # Group by month and keep only the latest date from each month
        monthly_latest = {}
        for transaction in transactions:
            date_obj = transaction['date']
            month_key = f"{date_obj.year}-{date_obj.month:02d}"  # Format: "2025-07"
            
            # Keep only if this is the first (latest) entry for this month
            if month_key not in monthly_latest:
                monthly_latest[month_key] = transaction
        
        # Convert back to list and sort by date (newest first)
        filtered_bills = list(monthly_latest.values())
        filtered_bills.sort(key=lambda x: x['date'], reverse=True)
        
        # Filter to bills only for current/previous
        bills = [t for t in filtered_bills if t['type'] == 'bill']
        
        if not bills:
            bills = filtered_bills  # Use all if no specific bills found
        
        current_bill = bills[0] if bills else None
        previous_bill = bills[1] if len(bills) > 1 else None
        
        account_number = extract_account_number_from_url(driver.current_url) if driver else None
        
        result = BillInfo(
            previous_month=f"Previous ({previous_bill['date'].strftime('%m/%d/%Y')})" if previous_bill else "No previous",
            previous_amount=previous_bill['amount'] if previous_bill else 0.0,
            current_month=f"Current ({current_bill['date'].strftime('%m/%d/%Y')})" if current_bill else "No current",
            current_amount=current_bill['amount'] if current_bill else 0.0,
            account_number=account_number or "Historical Data"
        )
        
        # Store filtered bills (latest per month only)
        result.all_bills = filtered_bills
        
        print(f"📊 Filtered to latest per month: {len(filtered_bills)} bills from {len(transactions)} total")
        
        return result

    def _try_ai_html_extraction(self, page_source: str) -> BillInfo:
        """Try AI-powered HTML extraction using the HTML_EXTRACTION prompt"""
        try:
            print("🤖 Trying AI-powered HTML extraction...")
            
            # Prepare clean HTML content for AI
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Remove script, style, and other non-content elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
                
            # Get relevant HTML content
            html_text = str(soup)[:10000]  # Limit size for AI processing
            
            # Get AI extraction using the new prompt
            from .prompts import PromptLibrary
            
            prompt = PromptLibrary.get_prompt('html_extraction', html_content=html_text)
            
            import ollama
            from .config import OLLAMA_MODEL
            
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 1000
                }
            )
            
            response_content = response["message"]["content"]
            print(f"🤖 AI HTML extraction response preview: {response_content[:150]}...")
            
            # Parse AI response
            import json
            import re
            
            try:
                ai_result = json.loads(response_content)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    ai_result = json.loads(json_match.group())
                else:
                    print(f"❌ Could not parse AI HTML extraction response")
                    return None
            
            bills = ai_result.get('bills', [])
            
            if not bills:
                return None
            
            # Convert AI bills to transaction format
            from datetime import datetime
            transactions = []
            
            for bill in bills:
                try:
                    date_str = bill.get('date', '')
                    amount = float(bill.get('amount', 0))
                    description = bill.get('description', 'AI extracted bill')
                    
                    # Parse date
                    bill_date = datetime.strptime(date_str, '%m/%d/%Y')
                    
                    transactions.append({
                        'date': bill_date,
                        'amount': amount,
                        'type': 'bill',
                        'description': description
                    })
                    
                except Exception as e:
                    print(f"⚠️ Skipping invalid bill entry: {e}")
                    continue
            
            if transactions:
                print(f"✅ AI extracted {len(transactions)} bills from HTML")
                return self._create_bill_info(transactions, None)
            
            return None
            
        except Exception as e:
            print(f"❌ AI HTML extraction failed: {e}")
            return None

class VisionAIExtractionStrategy(ExtractionStrategy):
    """Extract data using computer vision on screenshots"""
    
    def extract(self, page_source: str, driver=None) -> BillInfo:
        """Use Vision AI to extract data from screenshot"""
        if not VISION_AI_AVAILABLE:
            return BillInfo("Vision AI unavailable", 0.0, "Install Pillow", 0.0)
        
        if not driver:
            return BillInfo("No driver", 0.0, "Vision AI needs driver", 0.0)
        
        print("📸 Taking screenshot for Vision AI...")
        
        try:
            # Take screenshot
            screenshot_path = "/tmp/autobilling_screenshot.png"
            driver.save_screenshot(screenshot_path)
            
            # Convert to base64
            with open(screenshot_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Analyze with Vision AI
            return self._analyze_screenshot(image_base64)
            
        except Exception as e:
            print(f"❌ Screenshot analysis failed: {e}")
            return BillInfo("Screenshot failed", 0.0, str(e), 0.0)
    
    def _analyze_screenshot(self, image_base64: str) -> BillInfo:
        """Analyze screenshot with Vision AI"""
        vision_prompt = """
        Extract billing data from this utility website screenshot.
        
        Look for:
        - Bill amounts and dates in tables
        - Transaction history 
        - Payment records
        - Account information
        
        Return JSON:
        {
            "bills": [
                {
                    "date": "MM/DD/YYYY", 
                    "amount": 199.00,
                    "description": "Bill description",
                    "type": "bill"
                }
            ],
            "account_info": {
                "account_number": "if visible"
            }
        }
        
        Extract ALL visible billing entries. Be precise with dates and amounts.
        """
        
        try:
            response = ollama.chat(
                model=VISION_MODEL,
                messages=[{
                    'role': 'user',
                    'content': vision_prompt,
                    'images': [image_base64]
                }],
                options={'temperature': 0.1}
            )
            
            # Parse response
            vision_response = response['message']['content']
            json_match = re.search(r'\{.*\}', vision_response, re.DOTALL)
            
            if json_match:
                billing_data = json.loads(json_match.group())
                return self._create_bill_info_from_vision(billing_data)
            
        except Exception as e:
            print(f"❌ Vision AI analysis failed: {e}")
        
        return BillInfo("Vision AI failed", 0.0, "Could not analyze screenshot", 0.0)
    
    def _create_bill_info_from_vision(self, billing_data: Dict) -> BillInfo:
        """Create BillInfo from Vision AI response"""
        bills = billing_data.get('bills', [])
        account_info = billing_data.get('account_info', {})
        
        if not bills:
            return BillInfo("No vision data", 0.0, "Vision AI found no bills", 0.0)
        
        # Process bills
        processed_bills = []
        for bill in bills:
            try:
                bill_date = datetime.strptime(bill['date'], '%m/%d/%Y')
                bill_amount = float(bill['amount'])
                
                processed_bills.append({
                    'date': bill_date,
                    'amount': bill_amount,
                    'type': bill.get('type', 'bill'),
                    'description': bill.get('description', 'Vision AI Bill')
                })
            except:
                continue
        
        if not processed_bills:
            return BillInfo("No valid vision data", 0.0, "Could not parse vision data", 0.0)
        
        # Sort by date
        processed_bills.sort(key=lambda x: x['date'], reverse=True)
        
        current_bill = processed_bills[0]
        previous_bill = processed_bills[1] if len(processed_bills) > 1 else None
        
        result = BillInfo(
            previous_month=f"Previous ({previous_bill['date'].strftime('%m/%d/%Y')})" if previous_bill else "No previous",
            previous_amount=previous_bill['amount'] if previous_bill else 0.0,
            current_month=f"Current ({current_bill['date'].strftime('%m/%d/%Y')})",
            current_amount=current_bill['amount'],
            account_number=account_info.get('account_number', 'Vision AI Data')
        )
        
        result.all_bills = processed_bills
        return result

class SmartExtractionOrchestrator:
    """Orchestrates multiple extraction strategies"""
    
    def __init__(self):
        self.strategies = [
            APIExtractionStrategy(),
            HTMLExtractionStrategy(),
            VisionAIExtractionStrategy()
        ]
    
    def extract_billing_data(self, page_source: str, driver=None, is_billing_page: bool = False) -> BillInfo:
        """Try extraction strategies in order until one succeeds"""
        print("🧠 Smart extraction starting...")
        
        # Try API first (fastest)
        api_result = self.strategies[0].extract(page_source, driver)
        if has_meaningful_billing_data(api_result):
            print("✅ API extraction succeeded!")
            return api_result
        
        # Try HTML extraction
        html_result = self.strategies[1].extract(page_source, driver)
        if has_meaningful_billing_data(html_result):
            print("✅ HTML extraction succeeded!")
            return html_result
        
        # Try Vision AI only on confirmed billing pages
        if is_billing_page and VISION_AI_AVAILABLE:
            print("🎯 Using Vision AI on billing page...")
            vision_result = self.strategies[2].extract(page_source, driver)
            if has_meaningful_billing_data(vision_result):
                print("✅ Vision AI extraction succeeded!")
                return vision_result
        
        # Return best available result
        if has_meaningful_billing_data(html_result):
            return html_result
        elif has_meaningful_billing_data(api_result):
            return api_result
        else:
            return BillInfo("All extractions failed", 0.0, "No viable extraction method", 0.0) 