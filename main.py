import os
import time
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from tabulate import tabulate
import ollama

# Import configuration
import config

@dataclass
class BillInfo:
    """Data class to store billing information"""
    previous_month: str
    previous_amount: float
    current_month: str
    current_amount: float
    account_number: Optional[str] = None
    due_date: Optional[str] = None

class UtilityBillScraper:
    """AI-powered utility bill scraper that can handle various utility company websites"""
    
    def __init__(self):
        self.driver = None
        # Test Ollama connection
        try:
            # Test if Ollama is running and the model is available
            ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=[{"role": "user", "content": "test"}],
                options={"num_predict": 1}
            )
            print(f"✅ Connected to Ollama with model: {config.OLLAMA_MODEL}")
        except Exception as e:
            raise ValueError(f"Cannot connect to Ollama: {e}\nPlease ensure Ollama is running and {config.OLLAMA_MODEL} is available")
        
    def setup_driver(self, headless: bool = None) -> webdriver.Chrome:
        """Setup Chrome driver with appropriate options"""
        if headless is None:
            headless = config.HEADLESS_BROWSER
            
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-agent={config.USER_AGENT}")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        return self.driver
        
    def ai_login_form_detection(self, html_content: str) -> Dict:
        """Use AI specifically to detect login form elements"""
        try:
            truncated_html = html_content[:config.MAX_HTML_LENGTH] if len(html_content) > config.MAX_HTML_LENGTH else html_content
            
            prompt = f"""
            You are an expert at finding login forms on websites.
            
            HTML Content:
            {truncated_html}
            
            Find the login form elements. Look for:
            1. Username/email input fields
            2. Password input fields  
            3. Login/submit buttons
            
            Respond with JSON only:
            {{
                "login_form": {{
                    "found": true/false,
                    "username_field": "exact CSS selector for username field",
                    "password_field": "exact CSS selector for password field",
                    "submit_button": "exact CSS selector for submit button"
                }}
            }}
            """
            
            response = ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 500,
                    "top_p": 0.9
                }
            )
            
            response_content = response['message']['content']
            
            # Extract JSON from response
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_content = response_content[json_start:json_end]
                return json.loads(json_content)
            else:
                return {"error": "Could not parse AI response"}
                
        except Exception as e:
            print(f"🤖 AI login detection error: {e}")
            return {"error": str(e)}

    def find_login_elements(self, html_content: str) -> Dict:
        """Find login form elements using both AI and traditional methods"""
        
        # First try AI analysis for better accuracy
        try:
            ai_result = self.ai_login_form_detection(html_content)
            login_form = ai_result.get("login_form", {})
            
            if login_form.get("found"):
                print("🤖 Using AI-detected login elements")
                return {
                    "found": True,
                    "username_field": login_form.get("username_field"),
                    "password_field": login_form.get("password_field"),
                    "submit_button": login_form.get("submit_button")
                }
        except Exception as e:
            print(f"⚠️  AI login detection failed: {e}")
        
        # Fallback to traditional detection with improved patterns
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Enhanced login field patterns including the specific ones we found
        username_patterns = [
            'input[name="Email"]',           # Specific to this site
            'input[name="email"]',
            'input[name*="user"]', 
            'input[name*="email"]', 
            'input[name*="login"]',
            'input[id*="user"]', 
            'input[id*="email"]', 
            'input[id*="login"]',
            'input[type="email"]', 
            'input[placeholder*="user"]', 
            'input[placeholder*="email"]'
        ]
        
        password_patterns = [
            'input[name="Password"]',        # Specific to this site
            'input[name="password"]',
            'input[type="password"]', 
            'input[name*="pass"]', 
            'input[id*="pass"]'
        ]
        
        submit_patterns = [
            'button[name="button"][value="login"]',  # Specific to this site
            'button[value="login"]',
            'input[type="submit"]', 
            'button[type="submit"]',
            'input[value*="Login"]', 
            'input[value*="Sign"]'
        ]
        
        login_data = {
            "found": False,
            "username_field": None,
            "password_field": None,
            "submit_button": None
        }
        
        # Try to find username field
        for pattern in username_patterns:
            element = soup.select_one(pattern)
            if element:
                login_data["username_field"] = pattern
                print(f"📧 Found username field: {pattern}")
                break
        
        # Try to find password field
        for pattern in password_patterns:
            element = soup.select_one(pattern)
            if element:
                login_data["password_field"] = pattern
                login_data["found"] = True
                print(f"🔒 Found password field: {pattern}")
                break
        
        # Find submit button
        for pattern in submit_patterns:
            element = soup.select_one(pattern)
            if element:
                login_data["submit_button"] = pattern
                print(f"🔘 Found submit button: {pattern}")
                break
        
        return login_data

    def extract_billing_fallback(self, html_content: str) -> BillInfo:
        """Fallback method to extract billing data using regex patterns"""
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        
        # Common patterns for amounts
        amount_patterns = [
            r'\$[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*USD',
            r'Amount:\s*\$?[\d,]+\.?\d*'
        ]
        
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            amounts.extend(matches)
        
        # Extract numeric values
        numeric_amounts = []
        for amount in amounts:
            cleaned = re.sub(r'[^\d.]', '', amount)
            try:
                numeric_amounts.append(float(cleaned))
            except:
                continue
        
        # Sort amounts to get current and previous
        numeric_amounts.sort(reverse=True)
        
        current_month = datetime.now().strftime("%B %Y")
        previous_month = (datetime.now() - timedelta(days=30)).strftime("%B %Y")
        
        return BillInfo(
            previous_month=previous_month,
            previous_amount=numeric_amounts[1] if len(numeric_amounts) > 1 else 0.0,
            current_month=current_month,
            current_amount=numeric_amounts[0] if numeric_amounts else 0.0
        )
    
    def perform_login(self, username: str, password: str, login_data: Dict) -> bool:
        """Perform login using detected form elements"""
        try:
            print(f"🔧 Attempting to fill username: {username}")
            print(f"🔧 Using username selector: {login_data.get('username_field')}")
            print(f"🔧 Using password selector: {login_data.get('password_field')}")
            
            # Find and fill username field
            username_element = None
            if login_data.get("username_field"):
                # Try multiple ways to find the username field
                selectors_to_try = [
                    login_data["username_field"],
                    'input[name="Email"]',
                    'input[type="email"]',
                    '#Email'
                ]
                
                for selector in selectors_to_try:
                    try:
                        if selector.startswith('#'):
                            username_element = self.driver.find_element(By.ID, selector[1:])
                        elif '[' in selector:
                            username_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        else:
                            username_element = self.driver.find_element(By.NAME, selector)
                        
                        if username_element:
                            print(f"✅ Found username field with: {selector}")
                            break
                    except:
                        continue
            
            # Find and fill password field  
            password_element = None
            if login_data.get("password_field"):
                # Try multiple ways to find the password field
                selectors_to_try = [
                    login_data["password_field"],
                    'input[name="Password"]',
                    'input[type="password"]',
                    '#Password'
                ]
                
                for selector in selectors_to_try:
                    try:
                        if selector.startswith('#'):
                            password_element = self.driver.find_element(By.ID, selector[1:])
                        elif '[' in selector:
                            password_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        else:
                            password_element = self.driver.find_element(By.NAME, selector)
                        
                        if password_element:
                            print(f"✅ Found password field with: {selector}")
                            break
                    except:
                        continue
            
            if not username_element:
                print("❌ Could not find username field")
                return False
                
            if not password_element:
                print("❌ Could not find password field")
                return False
            
            # Fill the fields
            print("📝 Filling username field...")
            username_element.clear()
            username_element.send_keys(username)
            
            print("📝 Filling password field...")
            password_element.clear()
            password_element.send_keys(password)
            
            # Verify fields are filled
            username_value = username_element.get_attribute('value')
            password_value = password_element.get_attribute('value')
            
            print(f"🔍 Username field value: {username_value}")
            print(f"🔍 Password field filled: {'Yes' if password_value else 'No'}")
            
            if not username_value or not password_value:
                print("❌ Failed to fill login fields properly")
                return False
            
            # Find and click submit button
            submit_element = None
            if login_data.get("submit_button"):
                selectors_to_try = [
                    login_data["submit_button"],
                    'button[name="button"][value="login"]',
                    'button:contains("Login")',
                    'input[type="submit"]',
                    'button[type="submit"]'
                ]
                
                for selector in selectors_to_try:
                    try:
                        if ':contains(' in selector:
                            # Use XPath for text-based search
                            submit_element = self.driver.find_element(By.XPATH, f"//button[contains(text(), 'Login')]")
                        else:
                            submit_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if submit_element:
                            print(f"✅ Found submit button with: {selector}")
                            break
                    except:
                        continue
            
            if not submit_element:
                print("❌ Could not find submit button")
                return False
            
            # Get current URL before clicking
            url_before = self.driver.current_url
            
            print("🔘 Clicking login button...")
            submit_element.click()
            time.sleep(config.LOGIN_WAIT_TIME)
            
            # Check if login was successful
            url_after = self.driver.current_url
            page_source = self.driver.page_source
            
            # Check for specific login error messages (not general page content)
            login_error_indicators = [
                "invalid username or password",
                "invalid email or password", 
                "login failed",
                "authentication failed",
                "incorrect username",
                "incorrect password",
                "login error",
                "sign in failed"
            ]
            
            page_text = page_source.lower()
            has_login_error = any(error in page_text for error in login_error_indicators)
            
            # Check if URL changed (indicating redirect after successful login)
            url_changed = url_before != url_after
            
            # Check if still on login page
            still_on_login = "login" in url_after.lower() and "account.municipal" in url_after.lower()
            
            print(f"🔍 URL before: {url_before}")
            print(f"🔍 URL after:  {url_after}")
            print(f"🔍 URL changed: {url_changed}")
            print(f"🔍 Still on login page: {still_on_login}")
            print(f"🔍 Login error messages found: {has_login_error}")
            
            # Determine login success based on multiple indicators
            if has_login_error and still_on_login:
                print("❌ Login failed - error message on login page")
                return False
            elif url_changed and not still_on_login:
                print("✅ Login successful - redirected to main site")
                return True
            elif still_on_login and not url_changed:
                print("❌ Login failed - still on same login page")
                return False
            else:
                print("✅ Login appears successful - page changed")
                return True
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def intelligent_page_analysis(self, html_content: str, current_url: str) -> Dict:
        """Use AI to intelligently analyze any utility website page"""
        try:
            truncated_html = html_content[:config.MAX_HTML_LENGTH] if len(html_content) > config.MAX_HTML_LENGTH else html_content
            
            prompt = f"""
            You are an AI assistant helping to navigate utility company websites to find TRANSACTION HISTORY and BILLING STATEMENTS.
            
            Current URL: {current_url}
            
            HTML Content:
            {truncated_html}
            
            PRIORITY: Find transaction history, billing statements, payment history, or billing details with actual amounts.
            
            Analyze this page and determine:
            1. What type of page this is (login, dashboard, billing, account, transaction_history, etc.)
            2. Whether TRANSACTION HISTORY or BILLING STATEMENTS are visible
            3. Whether previous billing amounts or payment history is shown
            4. How to navigate to find transaction/billing history
            5. What links lead to account details, billing statements, transaction history, payment history
            
            Respond with JSON only:
            {{
                "page_analysis": {{
                    "page_type": "login|dashboard|billing|account|transaction_history|billing_statements|other",
                    "page_purpose": "brief description of what this page is for",
                    "has_billing_data": true/false,
                    "has_transaction_history": true/false,
                    "billing_elements_found": ["list", "of", "billing", "elements", "found"]
                }},
                "billing_data": {{
                    "found": true/false,
                    "current_month": "month name if found",
                    "current_amount": "amount if found",
                    "previous_month": "month name if found", 
                    "previous_amount": "amount if found",
                    "account_number": "account number if found",
                    "due_date": "due date if found",
                    "service_period": "service period if found"
                }},
                "navigation_options": [
                    {{
                        "type": "link|button|menu",
                        "text": "visible text of the element",
                        "url_or_action": "href or onclick action",
                        "relevance_score": "1-10 how likely this leads to TRANSACTION HISTORY or BILLING STATEMENTS",
                        "element_selector": "CSS selector or xpath",
                        "priority": "high|medium|low - high for transaction history, billing statements, account details"
                    }}
                ],
                "recommended_action": "stay|navigate|explore",
                "confidence": "1-10 confidence in analysis"
            }}
            
            Focus especially on finding:
            - Transaction history, payment history, billing history
            - Account details with billing amounts
            - Billing statements or bill summaries  
            - Previous bills or past due amounts
            - Account activity or payment records
            
            Look for navigation elements like "Transaction History", "Billing History", "Account Details", "Statements", 
            "Payment History", "My Bills", "Bill Summary", "Account Activity", "View Bills", etc.
            
            IMPORTANT: Only recommend navigation options that ACTUALLY EXIST on this page. 
            Do not invent or suggest links that are not present in the HTML.
            Extract the exact href values and link text from the HTML.
            
            PRIORITIZE links that specifically mention "details", "history", "statements", "activity", "summary".
            """
            
            response = ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 2000,
                    "top_p": 0.9
                }
            )
            
            response_content = response['message']['content']
            
            # Extract JSON from response
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_content = response_content[json_start:json_end]
                return json.loads(json_content)
            else:
                return {"error": "Could not parse AI response"}
                
        except Exception as e:
            print(f"🤖 AI analysis error: {e}")
            return {"error": str(e)}

    def intelligent_navigation(self, analysis_result: Dict, visited_urls: set = None) -> bool:
        """Intelligently navigate based on AI analysis, prioritizing transaction history"""
        try:
            if visited_urls is None:
                visited_urls = set()
                
            nav_options = analysis_result.get("navigation_options", [])
            
            # Sort navigation options by priority first, then relevance score
            def sort_key(option):
                priority_weight = {"high": 100, "medium": 50, "low": 0}
                priority = option.get("priority", "medium")
                relevance = int(option.get("relevance_score", 0))
                return priority_weight.get(priority, 50) + relevance
            
            nav_options.sort(key=sort_key, reverse=True)
            
            for option in nav_options:
                relevance = int(option.get("relevance_score", 0))
                priority = option.get("priority", "medium")
                
                # Prioritize high-priority links or high relevance
                if priority == "high" or relevance >= 6:
                    element_text = option.get("text", "")
                    url_or_action = option.get("url_or_action", "")
                    element_selector = option.get("element_selector", "")
                    
                    # Skip if we've already visited this URL
                    if url_or_action and url_or_action in visited_urls:
                        print(f"⏭️  Skipping already visited: '{element_text}'")
                        continue
                    
                    print(f"🎯 Trying HIGH PRIORITY navigation: '{element_text}' (priority: {priority}, relevance: {relevance}/10)")
                    
                    try:
                        # Try different navigation methods
                        if url_or_action and url_or_action.startswith('http'):
                            # Direct URL navigation
                            if url_or_action not in visited_urls:
                                self.driver.get(url_or_action)
                                visited_urls.add(url_or_action)
                                time.sleep(3)
                                return True
                        elif url_or_action and url_or_action.startswith('/'):
                            # Relative URL
                            from urllib.parse import urljoin
                            full_url = urljoin(self.driver.current_url, url_or_action)
                            if full_url not in visited_urls:
                                self.driver.get(full_url)
                                visited_urls.add(full_url)
                                time.sleep(3)
                                return True
                        elif element_selector:
                            # Try to find and click element
                            element = None
                            selectors_to_try = [
                                element_selector,
                                f"a:contains('{element_text}')",
                                f"button:contains('{element_text}')",
                                f"//*[contains(text(), '{element_text}')]",
                                f"//a[contains(text(), '{element_text}')]",
                                f"//button[contains(text(), '{element_text}')]"
                            ]
                            
                            for selector in selectors_to_try:
                                try:
                                    if selector.startswith('//'):
                                        element = self.driver.find_element(By.XPATH, selector)
                                    else:
                                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    
                                    if element and element.is_displayed():
                                        element.click()
                                        time.sleep(3)
                                        current_url = self.driver.current_url
                                        visited_urls.add(current_url)
                                        return True
                                except:
                                    continue
                        
                        # Enhanced fallback: search for text in links with specific keywords
                        try:
                            # Prioritize links with transaction/billing keywords
                            priority_keywords = ['detail', 'history', 'statement', 'activity', 'summary', 'account', 'transaction', 'payment']
                            
                            links = self.driver.find_elements(By.TAG_NAME, "a")
                            for link in links:
                                link_text = link.text.lower().strip()
                                link_href = link.get_attribute('href') or ''
                                
                                # Check if this link contains our target text and priority keywords
                                if element_text.lower() in link_text:
                                    # Extra priority for links with billing keywords
                                    has_priority_keyword = any(keyword in link_text for keyword in priority_keywords)
                                    
                                    if has_priority_keyword or relevance >= 7:
                                        if link_href not in visited_urls:
                                            print(f"🔗 Clicking priority link: '{link_text}'")
                                            link.click()
                                            time.sleep(3)
                                            current_url = self.driver.current_url
                                            visited_urls.add(current_url)
                                            return True
                        except:
                            pass
                            
                    except Exception as nav_error:
                        print(f"⚠️  Navigation attempt failed: {nav_error}")
                        continue
            
            return False
            
        except Exception as e:
            print(f"❌ Navigation error: {e}")
            return False

    def intelligent_billing_extraction(self, html_content: str) -> BillInfo:
        """Use AI to intelligently extract billing data from any utility website"""
        try:
            truncated_html = html_content[:config.MAX_HTML_LENGTH] if len(html_content) > config.MAX_HTML_LENGTH else html_content
            
            prompt = f"""
            You are an expert at extracting billing information from utility company websites. 
            Analyze this HTML content and find ALL financial amounts and billing-related information.
            
            HTML Content:
            {truncated_html}
            
            Look for ANY of these patterns and variations:
            - Dollar amounts: $123.45, $123, 123.45, USD 123.45, ($123.45)
            - HTML table data with classes like "forge-table", "forge-table-cell", table rows and cells
            - Span elements containing dollar amounts: <span>$150.46</span>
            - Bill entries, payment entries, transaction entries
            - Current bill, current amount, amount due, balance due
            - Previous bill, last bill, prior month, last month  
            - Due dates, payment dates, service periods
            - Account numbers, customer numbers
            - Usage amounts, kWh, therms, gallons
            - Any financial totals, subtotals, charges
            - Transaction history tables with billing amounts
            
            SPECIFICALLY look for:
            - HTML tables with transaction data
            - Table cells containing dollar amounts
            - Alternating patterns of bills and payments
            - Bills (positive amounts) and Bank Draft Payments (negative amounts)
            
            Search in ALL parts of the page including:
            - Tables and table cells (<td>, <tr>, <table>, forge-table)
            - Divs and spans with financial data
            - Form fields and input values
            - JSON data or JavaScript variables
            - Hidden elements with amounts
            - Bills statements and summaries
            
            If you find a table with multiple financial amounts, extract the TWO MOST RECENT bill amounts 
            (not payment amounts) for current and previous billing periods.
            
            Respond with JSON only:
            {{
                "billing_found": true/false,
                "current_bill": {{
                    "amount": "extract exact number without currency symbols from most recent bill",
                    "period": "billing period description",
                    "due_date": "due date if found",
                    "service_period": "service period if different"
                }},
                "previous_bill": {{
                    "amount": "previous bill exact number from second most recent bill",
                    "period": "previous billing period"
                }},
                "account_info": {{
                    "account_number": "account number if found",
                    "customer_name": "customer name if visible",
                    "service_address": "service address if shown"
                }},
                "all_amounts_found": [
                    {{
                        "amount": "any number found",
                        "context": "what this amount appears to be for (Bill, Payment, etc.)",
                        "location": "where in the page this was found"
                    }}
                ],
                "page_analysis": {{
                    "seems_like_billing_page": true/false,
                    "has_financial_data": true/false,
                    "main_content_type": "description of main page content"
                }},
                "confidence": "1-10 confidence in extracted data",
                "debug_info": "any relevant text snippets or patterns found"
            }}
            
            BE VERY THOROUGH. Extract ANY numbers that could be financial amounts.
            Look for patterns like: Total: $X, Amount: $X, Balance: $X, Due: $X, etc.
            Pay special attention to HTML table structures with billing data.
            """
            
            response = ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 2000,
                    "top_p": 0.9
                }
            )
            
            response_content = response['message']['content']
            print(f"🤖 AI Extraction Response: {response_content[:300]}...")
            
            # Extract JSON from response
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_content = response_content[json_start:json_end]
                extracted_data = json.loads(json_content)
                
                # Show what the AI found for debugging
                if extracted_data.get("all_amounts_found"):
                    print("🔍 AI found these amounts:")
                    for amount_info in extracted_data["all_amounts_found"][:5]:
                        print(f"   • ${amount_info.get('amount', 'N/A')} - {amount_info.get('context', 'Unknown context')}")
                
                # Convert to BillInfo format
                def clean_amount(amount_str) -> float:
                    if not amount_str:
                        return 0.0
                    cleaned = re.sub(r'[^\d.,]', '', str(amount_str))
                    try:
                        return float(cleaned.replace(',', ''))
                    except:
                        return 0.0
                
                current_bill = extracted_data.get("current_bill", {})
                previous_bill = extracted_data.get("previous_bill", {})
                account_info = extracted_data.get("account_info", {})
                
                return BillInfo(
                    previous_month=previous_bill.get("period", "Unknown"),
                    previous_amount=clean_amount(previous_bill.get("amount")),
                    current_month=current_bill.get("period", "Unknown"),
                    current_amount=clean_amount(current_bill.get("amount")),
                    account_number=account_info.get("account_number"),
                    due_date=current_bill.get("due_date")
                )
            else:
                return self.extract_billing_fallback(html_content)
                
        except Exception as e:
            print(f"🤖 AI extraction error: {e}")
            return self.extract_billing_fallback(html_content)
    
    def universal_billing_extraction(self, html_content: str) -> BillInfo:
        """Universal billing extraction that works with different website structures"""
        try:
            print("🌐 Attempting universal billing extraction...")
            
            # Strategy 1: Try AI extraction first
            ai_result = self.intelligent_billing_extraction(html_content)
            if ai_result.current_amount > 0 or ai_result.previous_amount > 0:
                print("✅ AI extraction successful")
                return ai_result
            
            # Strategy 2: Look for current billing dashboard info first (before transaction history)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Strategy 2a: Look for current bill indicators on dashboard
            current_bill_patterns = [
                r'current\s*bill.*?\$?([\d,]+\.?\d*)',
                r'amount\s*due.*?\$?([\d,]+\.?\d*)', 
                r'balance.*?\$?([\d,]+\.?\d*)',
                r'due.*?\$?([\d,]+\.?\d*)',
                r'\$?([\d,]+\.?\d*)\s*billed',
                r'\$?([\d,]+\.?\d*)\s*due'
            ]
            
            last_payment_patterns = [
                r'last\s*payment.*?\$?([\d,]+\.?\d*)',
                r'previous\s*payment.*?\$?([\d,]+\.?\d*)',
                r'\$?([\d,]+\.?\d*)\s*paid',
                r'thank\s*you.*?\$?([\d,]+\.?\d*)'
            ]
            
            page_text = soup.get_text()
            current_amount = 0.0
            previous_amount = 0.0
            
            # Look for current bill amount
            for pattern in current_bill_patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    try:
                        amount = float(match.group(1).replace(',', ''))
                        if 10.0 <= amount <= 2000.0:  # Reasonable utility bill range
                            current_amount = amount
                            print(f"🎯 Found current bill pattern: ${amount:.2f}")
                            break
                    except:
                        continue
                if current_amount > 0:
                    break
            
            # Look for previous payment amount  
            for pattern in last_payment_patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    try:
                        amount = float(match.group(1).replace(',', ''))
                        if 10.0 <= amount <= 2000.0:  # Reasonable utility bill range
                            previous_amount = amount
                            print(f"🎯 Found previous payment pattern: ${amount:.2f}")
                            break
                    except:
                        continue
                if previous_amount > 0:
                    break
            
            # If we found both current and previous from dashboard, use those
            if current_amount > 0 and previous_amount > 0:
                print(f"✅ Found current billing info on dashboard: Current=${current_amount:.2f}, Previous=${previous_amount:.2f}")
                
                # Try to extract account number
                account_number = None
                current_url = self.driver.current_url if self.driver else ""
                account_patterns = [
                    r'/(\d{2,}-\d{4,}-\d{2,})',  # XX-XXXX-XX format
                    r'/(\d{8,})',  # 8+ digit account numbers
                ]
                
                for pattern in account_patterns:
                    match = re.search(pattern, current_url, re.IGNORECASE)
                    if match:
                        account_number = match.group(1)
                        break
                
                return BillInfo(
                    previous_month="Previous Payment",
                    previous_amount=previous_amount,
                    current_month="Current Bill",
                    current_amount=current_amount,
                    account_number=account_number or "Unknown"
                )
            
            # Strategy 3: Parse with BeautifulSoup for manual extraction (fallback to old method)
            amounts = []
            
            # Look for table rows with dates and amounts to sort chronologically
            date_amount_pairs = []
            
            # Strategy 3a: Check tables for date/amount patterns
            table_selectors = [
                'table',  # Standard HTML tables
                '[class*="table"]',  # Any element with "table" in class
                '[class*="forge-table"]',  # Forge tables (like our current site)
                '[class*="billing"]',  # Billing-specific tables
                '[class*="transaction"]',  # Transaction tables
                '[class*="statement"]'  # Statement tables
            ]
            
            for selector in table_selectors:
                tables = soup.select(selector)
                for table in tables:
                    # Look for table rows with both dates and amounts
                    rows = table.find_all('tr')
                    for row in rows:
                        row_text = row.get_text()
                        
                        # Look for date patterns (various formats)
                        date_patterns = [
                            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY or M/D/YYYY
                            r'(\d{4}-\d{2}-\d{2})',      # YYYY-MM-DD
                            r'(\d{1,2}-\d{1,2}-\d{4})',  # MM-DD-YYYY
                        ]
                        
                        # Look for amount patterns
                        amount_patterns = [
                            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $123.45 or $1,234.56
                        ]
                        
                        date_match = None
                        for date_pattern in date_patterns:
                            date_match = re.search(date_pattern, row_text)
                            if date_match:
                                break
                        
                        amount_matches = []
                        for amount_pattern in amount_patterns:
                            amount_matches.extend(re.findall(amount_pattern, row_text))
                        
                        # If we found both date and amounts in this row
                        if date_match and amount_matches:
                            date_str = date_match.group(1)
                            
                            # Parse the date
                            try:
                                if '/' in date_str:
                                    # Handle MM/DD/YYYY format
                                    if len(date_str.split('/')) == 3:
                                        parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
                                    else:
                                        continue
                                elif '-' in date_str and len(date_str.split('-')) == 3:
                                    if date_str.count('-') == 2:
                                        if len(date_str.split('-')[0]) == 4:
                                            parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                                        else:
                                            parsed_date = datetime.strptime(date_str, '%m-%d-%Y')
                                    else:
                                        continue
                                else:
                                    continue
                                
                                # Process amounts found in this row
                                for amount_str in amount_matches:
                                    try:
                                        amount = float(amount_str.replace(',', ''))
                                        if 10.0 <= amount <= 2000.0:  # Reasonable utility bill range
                                            # Check if this looks like a bill (not a payment)
                                            if 'bill' in row_text.lower() and 'payment' not in row_text.lower():
                                                date_amount_pairs.append((parsed_date, amount, 'bill'))
                                                print(f"📅 Found BILL: {date_str} → ${amount:.2f}")
                                            elif 'payment' not in row_text.lower():
                                                # If no clear indication, assume it's a bill
                                                date_amount_pairs.append((parsed_date, amount, 'bill'))
                                                print(f"📅 Found transaction: {date_str} → ${amount:.2f}")
                                    except:
                                        continue
                                        
                            except Exception as date_error:
                                continue
            
            # Sort by date (most recent first) and filter for bills only
            date_amount_pairs.sort(key=lambda x: x[0], reverse=True)
            recent_bills = [(date, amount) for date, amount, transaction_type in date_amount_pairs 
                           if transaction_type == 'bill']
            
            print(f"📊 Found {len(recent_bills)} bills sorted by date:")
            for i, (date, amount) in enumerate(recent_bills[:5]):
                print(f"   {i+1}. {date.strftime('%m/%d/%Y')}: ${amount:.2f}")
            
            # If we found bills with dates, use the most recent ones
            if len(recent_bills) >= 2:
                current_amount = recent_bills[0][1]  # Most recent bill
                previous_amount = recent_bills[1][1]  # Second most recent bill
                
                print(f"✅ Using date-sorted bills: Current=${current_amount:.2f}, Previous=${previous_amount:.2f}")
                
                # Try to extract account number from URL
                account_number = None
                current_url = self.driver.current_url if self.driver else ""
                account_patterns = [
                    r'/(\d{2,}-\d{4,}-\d{2,})',  # XX-XXXX-XX format
                    r'/(\d{8,})',  # 8+ digit account numbers
                ]
                
                for pattern in account_patterns:
                    match = re.search(pattern, current_url, re.IGNORECASE)
                    if match:
                        account_number = match.group(1)
                        break
                
                return BillInfo(
                    previous_month=f"Previous Bill ({recent_bills[1][0].strftime('%m/%d/%Y')})",
                    previous_amount=previous_amount,
                    current_month=f"Current Bill ({recent_bills[0][0].strftime('%m/%d/%Y')})",
                    current_amount=current_amount,
                    account_number=account_number or "Unknown"
                )
            
            elif len(recent_bills) == 1:
                current_amount = recent_bills[0][1]
                return BillInfo(
                    previous_month="No previous data",
                    previous_amount=0.0,
                    current_month=f"Current Bill ({recent_bills[0][0].strftime('%m/%d/%Y')})",
                    current_amount=current_amount,
                    account_number="Unknown"
                )
            
            # Fallback to original amount-based method if no dates found
            print("⚠️  No dates found, falling back to amount-based extraction...")
            amounts = []
            
            # Look for various table structures and dollar amounts
            patterns_to_try = [
                r'\$[\d,]+\.?\d*',  # $123.45
                r'[\d,]+\.?\d*\s*USD',  # 123.45 USD
                r'Amount:\s*\$?[\d,]+\.?\d*',  # Amount: $123.45
                r'Total:\s*\$?[\d,]+\.?\d*',   # Total: $123.45
                r'Balance:\s*\$?[\d,]+\.?\d*'  # Balance: $123.45
            ]
            
            # Strategy 3a: Check multiple table types
            table_selectors = [
                'table',  # Standard HTML tables
                '[class*="table"]',  # Any element with "table" in class
                '[class*="forge-table"]',  # Forge tables (like our current site)
                '[class*="billing"]',  # Billing-specific tables
                '[class*="transaction"]',  # Transaction tables
                '[class*="statement"]'  # Statement tables
            ]
            
            for selector in table_selectors:
                tables = soup.select(selector)
                for table in tables:
                    table_text = table.get_text()
                    
                    # Extract amounts from table text
                    for pattern in patterns_to_try:
                        matches = re.findall(pattern, table_text, re.IGNORECASE)
                        for match in matches:
                            try:
                                # Clean and convert to float
                                cleaned = re.sub(r'[^\d.]', '', match)
                                if cleaned:
                                    amount = float(cleaned)
                                    if amount > 0:  # Only positive amounts (bills)
                                        amounts.append(amount)
                                        print(f"   💰 Found in {selector}: ${amount:.2f}")
                            except:
                                continue
            
            # Strategy 3b: Look for amounts in divs, spans, etc.
            amount_selectors = [
                '[class*="amount"]',
                '[class*="total"]', 
                '[class*="balance"]',
                '[class*="bill"]',
                '[class*="payment"]',
                'td', 'th', 'div', 'span'
            ]
            
            for selector in amount_selectors:
                elements = soup.select(selector)
                for element in elements:
                    element_text = element.get_text(strip=True)
                    
                    for pattern in patterns_to_try:
                        matches = re.findall(pattern, element_text, re.IGNORECASE)
                        for match in matches:
                            try:
                                cleaned = re.sub(r'[^\d.]', '', match)
                                if cleaned:
                                    amount = float(cleaned)
                                    if amount > 0 and amount < 10000:  # Reasonable range
                                        amounts.append(amount)
                                        print(f"   💰 Found in {selector}: ${amount:.2f}")
                            except:
                                continue
            
            # Remove duplicates and filter reasonable amounts
            unique_amounts = list(set(amounts))
            # Filter to reasonable utility bill range
            reasonable_amounts = [amt for amt in unique_amounts if 10.0 <= amt <= 2000.0]
            reasonable_amounts.sort(reverse=True)
            
            print(f"📊 Found {len(reasonable_amounts)} reasonable billing amounts: {reasonable_amounts[:10]}")
            
            # Extract current and previous amounts
            if len(reasonable_amounts) >= 2:
                current_amount = reasonable_amounts[0]
                previous_amount = reasonable_amounts[1]
                
                # Try to extract account number from URL or page
                account_number = None
                current_url = self.driver.current_url if self.driver else ""
                
                # Look for account numbers in URL
                account_patterns = [
                    r'/(\d{2,}-\d{4,}-\d{2,})',  # XX-XXXX-XX format
                    r'/(\d{8,})',  # 8+ digit account numbers
                    r'account[=/](\d+)',  # account=123456
                    r'acct[=/](\d+)'  # acct=123456
                ]
                
                for pattern in account_patterns:
                    match = re.search(pattern, current_url, re.IGNORECASE)
                    if match:
                        account_number = match.group(1)
                        break
                
                # Look for account number in page content
                if not account_number:
                    page_text = soup.get_text()
                    account_patterns_text = [
                        r'Account\s*#?:?\s*(\d{2,}-\d{4,}-\d{2,})',
                        r'Account\s*Number:?\s*(\d{8,})',
                        r'Acct\s*#?:?\s*(\d+)'
                    ]
                    
                    for pattern in account_patterns_text:
                        match = re.search(pattern, page_text, re.IGNORECASE)
                        if match:
                            account_number = match.group(1)
                            break
                
                return BillInfo(
                    previous_month="Previous Bill",
                    previous_amount=previous_amount,
                    current_month="Current Bill",
                    current_amount=current_amount,
                    account_number=account_number or "Unknown"
                )
            
            elif len(reasonable_amounts) == 1:
                return BillInfo(
                    previous_month="No previous data",
                    previous_amount=0.0,
                    current_month="Current Bill",
                    current_amount=reasonable_amounts[0],
                    account_number="Unknown"
                )
            
            else:
                # Strategy 4: Fallback to original method
                print("⚠️  No amounts found with universal extraction, trying fallback...")
                return self.extract_billing_fallback(html_content)
                
        except Exception as e:
            print(f"❌ Universal extraction error: {e}")
            return self.extract_billing_fallback(html_content)
    
    def scrape_utility_bill(self, url: str, username: str, password: str) -> BillInfo:
        """Main function to scrape utility bill information using intelligent AI analysis"""
        try:
            # Setup driver
            self.setup_driver()
            
            print(f"🌐 Navigating to {url}")
            self.driver.get(url)
            time.sleep(3)
            
            # Get initial page content
            html_content = self.driver.page_source
            
            # Find login elements
            print("🔍 Analyzing page for login elements...")
            login_data = self.find_login_elements(html_content)
            
            if login_data.get("found"):
                print("🔐 Login form found, attempting to login...")
                if self.perform_login(username, password, login_data):
                    print("✅ Login successful!")
                    
                    # Wait longer for complex OAuth/OpenID redirects
                    print("⏳ Waiting for authentication redirects to complete...")
                    time.sleep(10)  # Longer wait for OAuth flows
                    
                    # Check if we've been redirected away from login
                    current_url = self.driver.current_url
                    print(f"📍 Current URL after login: {current_url}")
                    
                    # If still on login page, try refreshing or waiting more
                    if "login" in current_url.lower() or "account.municipal" in current_url:
                        print("🔄 Still on authentication page, waiting for redirect...")
                        time.sleep(5)
                        
                        # Try refreshing the page to trigger redirect
                        self.driver.refresh()
                        time.sleep(5)
                        
                        current_url = self.driver.current_url
                        print(f"📍 URL after refresh: {current_url}")
                    
                    # Start intelligent exploration from current page
                    max_pages_to_explore = 8  # Increased to be more thorough
                    pages_explored = 0
                    best_billing_info = BillInfo("Unknown", 0.0, "Unknown", 0.0)
                    visited_urls = set()  # Track visited URLs to avoid loops
                    
                    while pages_explored < max_pages_to_explore:
                        pages_explored += 1
                        current_url = self.driver.current_url
                        
                        # Skip if we've already analyzed this URL  
                        if current_url in visited_urls:
                            print(f"⏭️  Skipping already analyzed URL: {current_url}")
                            continue
                            
                        visited_urls.add(current_url)
                        html_content = self.driver.page_source
                        
                        print(f"🧠 Intelligently analyzing page {pages_explored}: {current_url}")
                        
                        # Get page title and headers for debugging
                        try:
                            page_title = self.driver.title
                            print(f"📋 Page Title: {page_title}")
                            
                            # Look for main headers and content indicators
                            soup = BeautifulSoup(html_content, 'html.parser')
                            
                            # Find all headers (h1, h2, h3)
                            headers = []
                            for i in range(1, 4):
                                h_tags = soup.find_all(f'h{i}')
                                for h in h_tags:
                                    if h.get_text(strip=True):
                                        headers.append(f"H{i}: {h.get_text(strip=True)}")
                            
                            if headers:
                                print("📑 Page Headers Found:")
                                for header in headers[:5]:  # Show first 5 headers
                                    print(f"   • {header}")
                            
                            # Look for key billing-related text content
                            text_content = soup.get_text()
                            billing_keywords = ['bill', 'amount', 'due', 'balance', 'payment', 'account', 'current', 'previous', '$']
                            
                            # Find text snippets that contain billing keywords
                            billing_snippets = []
                            lines = text_content.split('\n')
                            for line in lines:
                                line = line.strip()
                                if line and any(keyword.lower() in line.lower() for keyword in billing_keywords):
                                    if len(line) < 100:  # Only short relevant lines
                                        billing_snippets.append(line)
                            
                            if billing_snippets:
                                print("💰 Billing-related content found:")
                                for snippet in billing_snippets[:8]:  # Show first 8 relevant snippets
                                    print(f"   • {snippet}")
                            else:
                                print("❌ No billing-related keywords found on this page")
                                
                            # Check for forms and interactive elements
                            forms = soup.find_all('form')
                            buttons = soup.find_all('button')
                            links = soup.find_all('a')
                            
                            print(f"🔗 Page Elements: {len(forms)} forms, {len(buttons)} buttons, {len(links)} links")
                            
                            # Show navigation links that might be relevant
                            nav_links = []
                            for link in links:
                                link_text = link.get_text(strip=True)
                                href = link.get('href', '')
                                if link_text and any(word in link_text.lower() for word in ['bill', 'account', 'payment', 'statement', 'usage', 'history']):
                                    nav_links.append(f"{link_text} → {href}")
                            
                            if nav_links:
                                print("🧭 Relevant navigation links found:")
                                for nav_link in nav_links[:5]:
                                    print(f"   • {nav_link}")
                                    
                        except Exception as debug_error:
                            print(f"⚠️  Debug analysis failed: {debug_error}")
                        
                        # AI-powered page analysis
                        analysis = self.intelligent_page_analysis(html_content, current_url)
                        
                        # Extract REAL navigation links from the page (no AI hallucination)
                        real_navigation_links = self.extract_real_navigation_links(html_content)
                        
                        if analysis.get("error"):
                            print(f"⚠️  Analysis error: {analysis['error']}")
                            # Still try navigation with real links even if AI analysis fails
                            analysis = {"page_analysis": {"page_type": "unknown", "has_billing_data": False, "has_transaction_history": False}, "confidence": 5}
                        
                        page_info = analysis.get("page_analysis", {})
                        page_type = page_info.get("page_type", "unknown")
                        has_billing = page_info.get("has_billing_data", False)
                        has_transaction_history = page_info.get("has_transaction_history", False)
                        confidence = analysis.get("confidence", 0)
                        
                        print(f"📊 Page type: {page_type}, Has billing: {has_billing}, Has transaction history: {has_transaction_history}, Confidence: {confidence}/10")
                        
                        # Check if we found comprehensive billing data with high confidence
                        if ((best_billing_info.current_amount > 0 and best_billing_info.previous_amount > 0) and confidence >= 8) or \
                           (has_transaction_history and confidence >= 7):
                            print("🎯 Found comprehensive billing data or transaction history, stopping exploration")
                            break
                        
                        # Skip if we're still stuck in authentication/login flows
                        if page_type == "login" and pages_explored > 1:
                            print("🔄 Still in authentication flow, trying to navigate away...")
                            
                            # Try to find any links that might take us to the main site
                            try:
                                # Look for "Continue" or "Proceed" buttons
                                continue_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Proceed') or contains(text(), 'Dashboard')]")
                                if continue_buttons:
                                    continue_buttons[0].click()
                                    time.sleep(5)
                                    continue
                                
                                # Try navigating to the base domain
                                base_url = "https://flowermoundtx.municipalonlinepayments.com/"
                                print(f"🏠 Trying to navigate to base URL: {base_url}")
                                self.driver.get(base_url)
                                time.sleep(5)
                                current_url = self.driver.current_url
                                html_content = self.driver.page_source
                                print(f"📍 New URL: {current_url}")
                                
                            except Exception as nav_error:
                                print(f"⚠️  Navigation attempt failed: {nav_error}")
                                
                        # Try to extract billing information from current page
                        print("💰 Attempting to extract billing information...")
                        billing_info = self.universal_billing_extraction(html_content)
                        
                        # Save HTML for debugging if we find potential billing content
                        if billing_snippets:
                            filename = f"billing_page_{pages_explored}.html"
                            with open(filename, 'w', encoding='utf-8') as f:
                                f.write(html_content)
                            print(f"📁 Saved page content to: {filename}")
                        
                        # Check if we found better billing data
                        if (billing_info.current_amount > 0 or billing_info.previous_amount > 0) and \
                           (billing_info.current_amount > best_billing_info.current_amount or 
                            billing_info.previous_amount > best_billing_info.previous_amount):
                            best_billing_info = billing_info
                            print(f"✅ Found billing data! Current: ${billing_info.current_amount:.2f}, Previous: ${billing_info.previous_amount:.2f}")
                            
                            # If we found good data, save this page for reference
                            success_filename = f"successful_billing_page.html"
                            with open(success_filename, 'w', encoding='utf-8') as f:
                                f.write(html_content)
                            print(f"🎯 Saved successful billing page to: {success_filename}")
                        else:
                            print(f"💸 No billing amounts found. Current: ${billing_info.current_amount:.2f}, Previous: ${billing_info.previous_amount:.2f}")
                        
                        # If no comprehensive billing data found, try to navigate to a better page
                        if not has_transaction_history or best_billing_info.current_amount == 0 or best_billing_info.previous_amount == 0:
                            
                            # Always try to navigate if we haven't found transaction history and have real links
                            if real_navigation_links:
                                print("🧭 Attempting navigation using REAL links found on the page...")
                                
                                # Use real links instead of AI-generated ones
                                fake_analysis_with_real_links = {
                                    "navigation_options": real_navigation_links,
                                    "recommended_action": "navigate"
                                }
                                
                                navigation_success = self.intelligent_navigation(fake_analysis_with_real_links, visited_urls)
                                
                                if navigation_success:
                                    print("✅ Navigation successful, analyzing new page...")
                                    time.sleep(3)  # Wait for page to load
                                    continue
                                else:
                                    print("❌ Navigation failed, trying next option...")
                            else:
                                print("🚫 No relevant navigation links found on this page")
                            
                            # If we can't navigate, try a few more pages
                            if pages_explored < max_pages_to_explore - 1:
                                print("🔄 Will continue exploring other options")
                        else:
                            print("✅ Found transaction history or comprehensive billing data")
                            if best_billing_info.current_amount > 0 and best_billing_info.previous_amount > 0:
                                break
                    
                    print(f"🔍 Exploration complete. Visited {pages_explored} pages.")
                    
                    # Return the best billing information found
                    if best_billing_info.current_amount > 0 or best_billing_info.previous_amount > 0:
                        print("🎉 Successfully extracted billing information!")
                        return best_billing_info
                    else:
                        print("😞 No billing information found after intelligent exploration")
                        return BillInfo("No data found", 0.0, "No data found", 0.0)
                    
                else:
                    print("❌ Login failed")
                    return BillInfo("Login failed", 0.0, "Login failed", 0.0)
            else:
                print("❌ Login form not found")
                return BillInfo("No login form", 0.0, "No login form", 0.0)
                
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
            return BillInfo("Error occurred", 0.0, "Error occurred", 0.0)
            
        finally:
            if self.driver:
                self.driver.quit()

    def extract_real_navigation_links(self, html_content: str) -> List[Dict]:
        """Extract actual navigation links from HTML to avoid AI hallucination"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            real_links = []
            
            # Find all actual links in the page
            links = soup.find_all('a', href=True)
            
            # Keywords that suggest billing/account related links
            priority_keywords = ['bill', 'account', 'transaction', 'history', 'statement', 'payment', 'detail', 'manage', 'consumption', 'summary']
            
            for link in links:
                href = link.get('href', '').strip()
                text = link.get_text(strip=True)
                
                if href and text and len(text) > 1:  # Skip empty or very short text
                    # Calculate relevance based on keywords
                    relevance = 1
                    priority = "low"
                    
                    text_lower = text.lower()
                    href_lower = href.lower()
                    
                    # Check for billing-related keywords
                    for keyword in priority_keywords:
                        if keyword in text_lower or keyword in href_lower:
                            relevance += 2
                            if keyword in ['transaction', 'history', 'detail', 'account', 'bill']:
                                priority = "high"
                                relevance += 3
                            elif keyword in ['payment', 'statement', 'manage']:
                                priority = "medium"
                                relevance += 1
                    
                    # Boost relevance for specific utility patterns
                    if any(word in href_lower for word in ['utilities', 'billing', 'account']):
                        relevance += 3
                        priority = "high"
                    
                    real_links.append({
                        "type": "link",
                        "text": text,
                        "url_or_action": href,
                        "relevance_score": min(10, relevance),  # Cap at 10
                        "element_selector": f"a[href='{href}']",
                        "priority": priority
                    })
            
            # Also check for buttons with onclick handlers
            buttons = soup.find_all(['button', 'forge-button'], onclick=True)
            for button in buttons:
                onclick = button.get('onclick', '')
                text = button.get_text(strip=True)
                
                if 'location.href' in onclick and text:
                    # Extract URL from onclick
                    url_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                    if url_match:
                        href = url_match.group(1)
                        
                        relevance = 3  # Buttons are generally more important
                        priority = "medium"
                        
                        text_lower = text.lower()
                        href_lower = href.lower()
                        
                        for keyword in priority_keywords:
                            if keyword in text_lower or keyword in href_lower:
                                relevance += 2
                                if keyword in ['transaction', 'history', 'detail', 'account']:
                                    priority = "high"
                                    relevance += 3
                        
                        real_links.append({
                            "type": "button",
                            "text": text,
                            "url_or_action": href,
                            "relevance_score": min(10, relevance),
                            "element_selector": f"button[onclick*='{href}']",
                            "priority": priority
                        })
            
            # Sort by relevance and priority
            def sort_key(link):
                priority_weight = {"high": 100, "medium": 50, "low": 0}
                priority = link.get("priority", "medium")
                relevance = int(link.get("relevance_score", 0))
                return priority_weight.get(priority, 50) + relevance
            
            real_links.sort(key=sort_key, reverse=True)
            
            print(f"🔗 Found {len(real_links)} real navigation links")
            for link in real_links[:5]:  # Show top 5
                print(f"   • {link['text']} → {link['url_or_action']} (priority: {link['priority']}, relevance: {link['relevance_score']})")
            
            return real_links
            
        except Exception as e:
            print(f"❌ Error extracting real links: {e}")
            return []

def display_billing_table(bill_info: BillInfo):
    """Display billing information in a nice table format"""
    data = [
        ["Previous Month", bill_info.previous_month, f"${bill_info.previous_amount:.2f}"],
        ["Current Month", bill_info.current_month, f"${bill_info.current_amount:.2f}"],
        ["Difference", "", f"${bill_info.current_amount - bill_info.previous_amount:.2f}"]
    ]
    
    if bill_info.account_number:
        data.append(["Account Number", bill_info.account_number, ""])
    
    if bill_info.due_date:
        data.append(["Due Date", bill_info.due_date, ""])
    
    print("\n" + "="*50)
    print("💡 UTILITY BILL SUMMARY")
    print("="*50)
    print(tabulate(data, headers=["Period", "Month", "Amount"], tablefmt="grid"))
    print("="*50)

def main():
    """Main function to run the intelligent universal utility bill scraper"""
    print("🏠 AutoBilling - Universal AI-Powered Utility Bill Scraper (Ollama)")
    print("🤖 Intelligent system that can analyze ANY utility website")
    print("=" * 60)
    
    try:
        # Example usage
        url = input("🌐 Enter utility bill website URL: ").strip()
        username = input("👤 Enter username/email: ").strip()
        password = input("🔒 Enter password: ").strip()
        
        if not all([url, username, password]):
            print("❌ All fields are required!")
            return
        
        print("\n🧠 Starting intelligent analysis...")
        print("✨ The AI will automatically:")
        print("   • Detect and navigate the website structure")
        print("   • Find login forms automatically")  
        print("   • Intelligently explore to find billing information")
        print("   • Extract data from any utility company layout")
        print("   • Work universally across different websites")
        
        # Create scraper and run
        scraper = UtilityBillScraper()
        bill_info = scraper.scrape_utility_bill(url, username, password)
        
        # Display results
        display_billing_table(bill_info)
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please ensure Ollama is running and qwen2.5:latest model is available")
        print("Run: ollama pull qwen2.5:latest")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    main()
