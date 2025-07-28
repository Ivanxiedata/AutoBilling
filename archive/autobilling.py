#!/usr/bin/env python3
"""
AutoBilling - Universal AI-Powered Utility Bill Scraper
Simple version that just asks for URL, username, and password
"""

import os
import time
import json
import re
import random
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
import base64
from io import BytesIO

# Try to import PIL, provide helpful error if not available
try:
    from PIL import Image
    VISION_AI_AVAILABLE = True
except ImportError:
    VISION_AI_AVAILABLE = False
    print("⚠️  Vision AI unavailable - install Pillow: pip install Pillow")

# Configuration  
OLLAMA_MODEL = "qwen2.5:latest"
VISION_MODEL = "qwen2.5vl:7b"  # Much faster 7B model instead of 72B
HEADLESS_BROWSER = False  # Set to True to hide browser
DEBUG_MODE = True  # Set to False to reduce output
MAX_HTML_LENGTH = 15000  # Increased for better AI analysis
LOGIN_WAIT_TIME = 5
# Updated to latest Chrome user agent (December 2024)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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
            ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": "test"}],
                options={"num_predict": 1}
            )
            print(f"✅ Connected to Ollama with model: {OLLAMA_MODEL}")
        except Exception as e:
            raise ValueError(f"Cannot connect to Ollama: {e}\nPlease ensure Ollama is running and {OLLAMA_MODEL} is available")
        
    def setup_driver(self, headless: bool = None) -> webdriver.Chrome:
        """Setup Chrome driver with anti-detection measures"""
        if headless is None:
            headless = HEADLESS_BROWSER
            
        chrome_options = Options()
        
        # Basic options
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-agent={USER_AGENT}")
        
        # Anti-detection measures
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins-discovery")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Realistic browser behavior
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Remove webdriver property to avoid detection
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Add realistic navigator properties
        self.driver.execute_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
        """)
        
        return self.driver
    
    def human_like_delay(self, min_seconds=0.5, max_seconds=2.0):
        """Add random delay to simulate human behavior"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def human_like_typing(self, element, text, delay_range=(0.05, 0.15)):
        """Type text character by character with human-like delays"""
        element.clear()
        time.sleep(0.2)
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(*delay_range))
        
    def ai_submit_button_detection(self) -> tuple:
        """Use AI to intelligently detect the submit button by analyzing page context"""
        try:
            print("🧠 Using AI to analyze all interactive elements...")
            
            # Gather all potentially clickable elements with their context
            interactive_elements = []
            
            # Find all clickable elements more comprehensively
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='submit'], input[type='button']")
            links = self.driver.find_elements(By.TAG_NAME, "a")
            clickable_divs = self.driver.find_elements(By.CSS_SELECTOR, "[role='button'], [onclick], .btn, .button, [ng-click], [click]")
            clickable_spans = self.driver.find_elements(By.CSS_SELECTOR, "span[onclick], span[ng-click], span.clickable")
            
            all_elements = buttons + inputs + links + clickable_divs + clickable_spans
            
            print(f"🔍 Found {len(buttons)} buttons, {len(inputs)} inputs, {len(links)} links, {len(clickable_divs)} clickable divs, {len(clickable_spans)} clickable spans")
            
            for idx, element in enumerate(all_elements):
                try:
                    if not element.is_displayed():
                        continue
                        
                    # Gather comprehensive context about each element
                    context = {
                        "index": idx,
                        "tag": element.tag_name.lower(),
                        "type": element.get_attribute("type") or "",
                        "text": element.text.strip(),
                        "value": element.get_attribute("value") or "",
                        "id": element.get_attribute("id") or "",
                        "class": element.get_attribute("class") or "",
                        "name": element.get_attribute("name") or "",
                        "role": element.get_attribute("role") or "",
                        "onclick": element.get_attribute("onclick") or "",
                        "disabled": element.get_attribute("disabled") is not None,
                        "form_association": "unknown",
                        "position": element.location,
                        "size": element.size,
                        "aria_label": element.get_attribute("aria-label") or "",
                    }
                    
                    # Check form association
                    try:
                        form = element.find_element(By.XPATH, "./ancestor::form[1]")
                        context["form_association"] = "inside_form"
                    except:
                        context["form_association"] = "outside_form"
                    
                    interactive_elements.append(context)
                    
                except Exception as e:
                    continue
            
            if not interactive_elements:
                print("❌ No interactive elements found")
                return None, None
            
            # Use AI to analyze and choose the best submit button
            analysis_prompt = f"""
            You are an expert at analyzing web pages to identify login submit buttons. 
            
            Below is a list of ALL interactive elements found on the current page with their complete context:
            
            {json.dumps(interactive_elements, indent=2)}
            
            TASK: Identify which element is most likely the LOGIN SUBMIT button.
            
            ANALYSIS CRITERIA:
            1. **Purpose Indicators**: Text like "Sign In", "Login", "Submit", "Continue", "Enter"
            2. **Form Context**: Elements inside forms are more likely to be submit buttons
            3. **Element Type**: button[type="submit"], input[type="submit"] are primary candidates
            4. **Position**: Usually positioned after input fields, often bottom-right of forms
            5. **Styling**: Classes often indicate primary/submit buttons (.primary, .submit, .btn-primary)
            6. **State**: Should be enabled (not disabled) when ready for interaction
            7. **Size/Prominence**: Submit buttons are usually prominent in size
            
            REASONING PROCESS:
            1. Filter out clearly non-submit elements (navigation, decorative buttons)
            2. Look for form-associated elements first
            3. Analyze text content for login-related terms
            4. Consider element positioning and styling
            5. Prefer standard HTML submit patterns
            
            Respond with JSON only:
            {{
                "selected_element_index": <index_number>,
                "confidence": <0-100>,
                "reasoning": "<why this element was chosen>",
                "css_selector": "<most_reliable_css_selector_for_this_element>",
                "xpath": "<xpath_for_this_element>"
            }}
            
            If no suitable submit button is found, set selected_element_index to -1.
            """
            
            # Get AI analysis
            try:
                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=[{"role": "user", "content": analysis_prompt}],
                    options={"temperature": 0.1}
                )
                
                ai_analysis = json.loads(response["message"]["content"])
                selected_index = ai_analysis.get("selected_element_index", -1)
                
                if selected_index >= 0 and selected_index < len(all_elements):
                    element = all_elements[selected_index]
                    confidence = ai_analysis.get("confidence", 0)
                    reasoning = ai_analysis.get("reasoning", "No reasoning provided")
                    
                    print(f"🤖 AI selected element {selected_index} (confidence: {confidence}%)")
                    print(f"🧠 AI reasoning: {reasoning}")
                    
                    # Generate reliable selector for this element
                    selector = self.generate_reliable_selector(element)
                    
                    return element, selector
                else:
                    print("🤖 AI couldn't identify a suitable submit button")
                    return None, None
                    
            except Exception as e:
                print(f"❌ AI analysis failed: {e}")
                return None, None
                
        except Exception as e:
            print(f"❌ Button detection failed: {e}")
            return None, None
    
    def generate_reliable_selector(self, element) -> str:
        """Generate a reliable CSS selector for an element"""
        try:
            # Try ID first (most reliable)
            element_id = element.get_attribute("id")
            if element_id:
                return f"#{element_id}"
            
            # Try unique class combination
            classes = element.get_attribute("class")
            if classes:
                class_list = classes.split()
                if len(class_list) >= 2:
                    return f".{'.'.join(class_list[:2])}"
                elif len(class_list) == 1:
                    return f".{class_list[0]}"
            
            # Try name attribute
            name = element.get_attribute("name")
            if name:
                return f"[name='{name}']"
            
            # Try type and tag combination
            element_type = element.get_attribute("type")
            tag = element.tag_name.lower()
            if element_type:
                return f"{tag}[type='{element_type}']"
            
            # Fallback to tag
            return tag
            
        except:
            return "button"

    def ai_login_form_detection(self, html_content: str) -> Dict:
        """Use AI to universally detect login form elements on ANY website"""
        try:
            # Use more HTML content for better context
            truncated_html = html_content[:MAX_HTML_LENGTH] if len(html_content) > MAX_HTML_LENGTH else html_content
            
            prompt = f"""
            You are an expert web scraping AI that must analyze ONLY the actual HTML provided and find login form elements.
            
            CRITICAL: You must ONLY reference elements that actually exist in the provided HTML. Do NOT make up or guess selectors.
            
            HTML Content:
            {truncated_html}
            
            ANALYSIS REQUIREMENTS:
            1. Look through the EXACT HTML provided above
            2. Find ALL input elements and their actual attributes (name, id, type, class, placeholder)
            3. Find ALL button/submit elements and their actual attributes
            4. Only suggest selectors for elements that ACTUALLY EXIST in the HTML
            
            USERNAME FIELD DETECTION:
            - Look for input elements with type="text", type="email", or no type
            - Check if name/id/class/placeholder contains: user, login, email, account
            - MUST exist in the provided HTML
            
            PASSWORD FIELD DETECTION:
            - Look for input elements with type="password"
            - MUST exist in the provided HTML
            
            SUBMIT BUTTON DETECTION:
            - Look for button elements or input type="submit"
            - Check text content, value, name, id for: login, sign, submit
            - MUST exist in the provided HTML
            
            IMPORTANT: Before suggesting any selector, verify it exists in the HTML above.
            If you cannot find clear login elements, set found: false.
            
            Respond with JSON only - NO explanations:
            {{
                "login_form": {{
                    "found": true/false,
                    "confidence": 0-100,
                    "username_selectors": [
                        {{
                            "selector": "EXACT CSS selector that exists in HTML",
                            "confidence": 0-100,
                            "reason": "why this element is username field",
                            "verified_exists": true
                        }}
                    ],
                    "password_selectors": [
                        {{
                            "selector": "EXACT CSS selector that exists in HTML",
                            "confidence": 0-100,
                            "reason": "why this element is password field", 
                            "verified_exists": true
                        }}
                    ],
                    "submit_selectors": [
                        {{
                            "selector": "EXACT CSS selector that exists in HTML",
                            "confidence": 0-100,
                            "reason": "why this element submits form",
                            "verified_exists": true
                        }}
                    ],
                    "debug_info": {{
                        "total_inputs_found": 0,
                        "input_types_found": [],
                        "button_count": 0,
                        "form_count": 0
                    }}
                }}
            }}
            
            VERIFICATION STEP: Double-check that every selector you provide actually appears in the HTML above.
            """
            
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.05,  # Lower temperature for more accuracy
                    "num_predict": 1500,
                    "top_p": 0.8
                }
            )
            
            response_content = response['message']['content']
            
            # Extract JSON from response
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_content = response_content[json_start:json_end]
                result = json.loads(json_content)
                
                # Enhanced debugging output
                if result.get("login_form", {}).get("found"):
                    login_form = result["login_form"]
                    print(f"🤖 AI Detection Confidence: {login_form.get('confidence', 0)}%")
                    
                    debug_info = login_form.get("debug_info", {})
                    print(f"🤖 Total inputs found: {debug_info.get('total_inputs_found', 'unknown')}")
                    print(f"🤖 Input types: {debug_info.get('input_types_found', [])}")
                    print(f"🤖 Buttons found: {debug_info.get('button_count', 'unknown')}")
                    
                    # Show what selectors the AI is providing
                    username_selectors = login_form.get("username_selectors", [])
                    password_selectors = login_form.get("password_selectors", [])
                    submit_selectors = login_form.get("submit_selectors", [])
                    
                    print(f"🤖 AI suggested username selectors: {[s.get('selector') for s in username_selectors]}")
                    print(f"🤖 AI suggested password selectors: {[s.get('selector') for s in password_selectors]}")
                    print(f"🤖 AI suggested submit selectors: {[s.get('selector') for s in submit_selectors]}")
                else:
                    print("🤖 AI could not detect login form")
                
                return result
            else:
                return {"error": "Could not parse AI response"}
                
        except Exception as e:
            print(f"🤖 AI login detection error: {e}")
            return {"error": str(e)}

    def debug_actual_page_elements(self):
        """Debug function to see what elements are actually present on the page"""
        try:
            print("\n🔍 DEBUG: Analyzing actual page elements...")
            
            # Get all input elements
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            print(f"📋 Found {len(inputs)} input elements:")
            
            for i, input_elem in enumerate(inputs[:10]):  # Show first 10
                try:
                    name = input_elem.get_attribute('name') or 'No name'
                    id_attr = input_elem.get_attribute('id') or 'No id'
                    type_attr = input_elem.get_attribute('type') or 'No type'
                    placeholder = input_elem.get_attribute('placeholder') or 'No placeholder'
                    class_attr = input_elem.get_attribute('class') or 'No class'
                    visible = input_elem.is_displayed()
                    
                    print(f"  {i+1}. name='{name}', id='{id_attr}', type='{type_attr}', placeholder='{placeholder}', visible={visible}")
                except:
                    print(f"  {i+1}. Could not read attributes")
            
            # Get all buttons
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            print(f"\n🔘 Found {len(buttons)} button elements:")
            
            for i, button in enumerate(buttons[:5]):  # Show first 5
                try:
                    text = button.text or 'No text'
                    id_attr = button.get_attribute('id') or 'No id'
                    type_attr = button.get_attribute('type') or 'No type'
                    class_attr = button.get_attribute('class') or 'No class'
                    visible = button.is_displayed()
                    
                    print(f"  {i+1}. text='{text}', id='{id_attr}', type='{type_attr}', visible={visible}")
                except:
                    print(f"  {i+1}. Could not read button attributes")
            
            # Check for any form elements
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            print(f"\n📝 Found {len(forms)} form elements")
            
            print("🔍 DEBUG: Page element analysis complete\n")
            
        except Exception as e:
            print(f"❌ Debug analysis failed: {e}")

    def find_login_elements(self, html_content: str) -> Dict:
        """Universal login form detection using primarily AI with intelligent fallbacks"""
        
        print("🧠 Using Universal AI Login Detection...")
        
        # Add debug analysis of actual page elements
        if self.driver:
            self.debug_actual_page_elements()
        
        # Primary: AI-powered universal detection
        try:
            ai_result = self.ai_login_form_detection(html_content)
            login_form = ai_result.get("login_form", {})
            
            if login_form.get("found") and login_form.get("confidence", 0) >= 70:
                print(f"🤖 AI successfully detected login form (confidence: {login_form.get('confidence')}%)")
                
                # Extract best selectors from AI response
                username_selectors = login_form.get("username_selectors", [])
                password_selectors = login_form.get("password_selectors", [])
                submit_selectors = login_form.get("submit_selectors", [])
                
                # Get the highest confidence selector for each field
                best_username = max(username_selectors, key=lambda x: x.get("confidence", 0)) if username_selectors else None
                best_password = max(password_selectors, key=lambda x: x.get("confidence", 0)) if password_selectors else None
                best_submit = max(submit_selectors, key=lambda x: x.get("confidence", 0)) if submit_selectors else None
                
                if best_username and best_password:
                    print(f"📧 Username: {best_username['selector']} ({best_username.get('reason', 'AI detected')})")
                    print(f"🔒 Password: {best_password['selector']} ({best_password.get('reason', 'AI detected')})")
                    if best_submit:
                        print(f"🔘 Submit: {best_submit['selector']} ({best_submit.get('reason', 'AI detected')})")
                    
                    # Verify the AI's selectors actually work
                    print("🔍 Verifying AI-suggested selectors...")
                    verification_result = self.verify_selectors_work({
                        "username_field": best_username["selector"],
                        "password_field": best_password["selector"],
                        "submit_button": best_submit["selector"] if best_submit else None
                    })
                    
                    if verification_result["verified"]:
                        print("✅ AI selectors verified successfully!")
                        return {
                            "found": True,
                            "username_field": best_username["selector"],
                            "password_field": best_password["selector"],
                            "submit_button": best_submit["selector"] if best_submit else None,
                            "selectors": {
                                "username": username_selectors,
                                "password": password_selectors,
                                "submit": submit_selectors
                            }
                        }
                    else:
                        print("❌ AI selectors could not be verified, falling back...")
                        
        except Exception as e:
            print(f"⚠️  AI login detection failed: {e}")
        
        # Fallback: Intelligent generic detection (no hardcoded patterns)
        print("🔄 Falling back to intelligent generic detection...")
        return self.intelligent_generic_login_detection(html_content)
    
    def verify_selectors_work(self, selectors: Dict) -> Dict:
        """Verify that the provided selectors actually find elements on the page"""
        try:
            verification = {"verified": False, "details": {}}
            
            # Test username selector
            username_selector = selectors.get("username_field")
            if username_selector:
                try:
                    if username_selector.startswith('#'):
                        element = self.driver.find_element(By.ID, username_selector[1:])
                    elif username_selector.startswith('.'):
                        element = self.driver.find_element(By.CLASS_NAME, username_selector[1:])
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, username_selector)
                    
                    verification["details"]["username"] = element.is_displayed()
                    print(f"  ✅ Username selector '{username_selector}' found element (visible: {element.is_displayed()})")
                except Exception as e:
                    verification["details"]["username"] = False
                    print(f"  ❌ Username selector '{username_selector}' failed: {e}")
            
            # Test password selector
            password_selector = selectors.get("password_field")
            if password_selector:
                try:
                    if password_selector.startswith('#'):
                        element = self.driver.find_element(By.ID, password_selector[1:])
                    elif password_selector.startswith('.'):
                        element = self.driver.find_element(By.CLASS_NAME, password_selector[1:])
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, password_selector)
                    
                    verification["details"]["password"] = element.is_displayed()
                    print(f"  ✅ Password selector '{password_selector}' found element (visible: {element.is_displayed()})")
                except Exception as e:
                    verification["details"]["password"] = False
                    print(f"  ❌ Password selector '{password_selector}' failed: {e}")
            
            # Test submit selector (optional)
            submit_selector = selectors.get("submit_button")
            if submit_selector:
                try:
                    if submit_selector.startswith('#'):
                        element = self.driver.find_element(By.ID, submit_selector[1:])
                    elif submit_selector.startswith('.'):
                        element = self.driver.find_element(By.CLASS_NAME, submit_selector[1:])
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, submit_selector)
                    
                    verification["details"]["submit"] = element.is_displayed()
                    print(f"  ✅ Submit selector '{submit_selector}' found element (visible: {element.is_displayed()})")
                except Exception as e:
                    verification["details"]["submit"] = False
                    print(f"  ❌ Submit selector '{submit_selector}' failed: {e}")
            
            # Overall verification
            username_ok = verification["details"].get("username", False)
            password_ok = verification["details"].get("password", False)
            
            verification["verified"] = username_ok and password_ok
            
            return verification
            
        except Exception as e:
            print(f"❌ Selector verification failed: {e}")
            return {"verified": False, "error": str(e)}

    def intelligent_generic_login_detection(self, html_content: str) -> Dict:
        """Intelligent fallback that analyzes input field characteristics instead of hardcoded patterns"""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all input fields (including Angular Material)
        all_inputs = soup.find_all('input')
        
        # Also look for Angular Material inputs (mat-input-*)
        mat_inputs = soup.find_all(attrs={'id': lambda x: x and 'mat-input' in x})
        
        # Combine all input sources
        all_inputs.extend(mat_inputs)
        

        
        # Analyze each input field to determine its likely purpose
        username_candidates = []
        password_candidates = []
        submit_candidates = []
        
        for input_field in all_inputs:
            field_info = {
                "element": input_field,
                "selector": None,
                "confidence": 0,
                "reasons": []
            }
            
            # Get field attributes
            name = (input_field.get('name') or '').lower()
            id_attr = (input_field.get('id') or '').lower()
            type_attr = (input_field.get('type') or '').lower()
            placeholder = (input_field.get('placeholder') or '').lower()
            class_attr = ' '.join(input_field.get('class') or []).lower()
            
            # Create a selector for this field
            if id_attr:
                field_info["selector"] = f"#{input_field.get('id')}"
            elif name:
                field_info["selector"] = f"input[name='{input_field.get('name')}']"
            else:
                field_info["selector"] = f"input[type='{type_attr}']"
            
            # Password field detection (most reliable)
            if type_attr == 'password':
                field_info["confidence"] = 95
                field_info["reasons"].append("type=password")
                password_candidates.append(field_info)
                continue
            
            # Username field detection based on semantic analysis
            username_indicators = [
                'user', 'login', 'email', 'account', 'customer', 'member',
                'signin', 'username', 'userid', 'loginid', 'accountnumber',
                'customernumber', 'memberid', 'employeeid'
            ]
            
            # Check if any username indicators appear in field attributes
            all_text = f"{name} {id_attr} {placeholder} {class_attr}"
            
            username_score = 0
            matched_indicators = []
            
            for indicator in username_indicators:
                if indicator in all_text:
                    username_score += 10
                    matched_indicators.append(indicator)
            
            # Boost confidence for email type
            if type_attr == 'email':
                username_score += 15
                matched_indicators.append("type=email")
            
            # Boost confidence for text type (common for usernames)
            if type_attr in ['text', '']:
                username_score += 5
                matched_indicators.append("text input")
            
            if username_score > 0:
                field_info["confidence"] = min(username_score, 90)
                field_info["reasons"] = matched_indicators
                username_candidates.append(field_info)
            
            # Submit button detection
            if type_attr in ['submit', 'button']:
                submit_score = 50
                if any(word in (input_field.get('value') or '').lower() for word in ['login', 'sign', 'submit', 'enter']):
                    submit_score += 30
                field_info["confidence"] = submit_score
                field_info["reasons"].append(f"type={type_attr}")
                submit_candidates.append(field_info)
        
        # Also check for button elements
        all_buttons = soup.find_all('button')
        for button in all_buttons:
            field_info = {
                "element": button,
                "selector": None,
                "confidence": 0,
                "reasons": []
            }
            
            button_text = button.get_text().lower()
            type_attr = (button.get('type') or '').lower()
            id_attr = button.get('id') or ''
            class_attr = ' '.join(button.get('class') or []).lower()
            
            # Create selector
            if id_attr:
                field_info["selector"] = f"#{id_attr}"
            else:
                field_info["selector"] = "button"
                if class_attr:
                    field_info["selector"] = f"button.{class_attr.split()[0]}"
            
            submit_score = 30
            if any(word in button_text for word in ['login', 'sign in', 'submit', 'enter', 'continue']):
                submit_score += 40
            if type_attr in ['submit', 'button', '']:
                submit_score += 20
            
            # Boost for Angular Material buttons
            if 'mat-' in class_attr:
                submit_score += 30
                field_info["reasons"].append("Angular Material button")
            
            # Better selector for Angular Material
            if 'mat-focus-indicator' in class_attr and 'mat-button' in class_attr:
                field_info["selector"] = "button.mat-focus-indicator.mat-button"
                submit_score += 20
            
            if submit_score >= 40:
                field_info["confidence"] = submit_score
                field_info["reasons"].append(f"button text: {button_text}")
                submit_candidates.append(field_info)
        
        # Select the best candidates
        best_username = max(username_candidates, key=lambda x: x["confidence"]) if username_candidates else None
        best_password = max(password_candidates, key=lambda x: x["confidence"]) if password_candidates else None
        best_submit = max(submit_candidates, key=lambda x: x["confidence"]) if submit_candidates else None
        
        # Validate we found the essential fields
        if best_password and best_username:
            print(f"📧 Found username field: {best_username['selector']} (confidence: {best_username['confidence']}%, reasons: {', '.join(best_username['reasons'])})")
            print(f"🔒 Found password field: {best_password['selector']} (confidence: {best_password['confidence']}%)")
            if best_submit:
                print(f"🔘 Found submit button: {best_submit['selector']} (confidence: {best_submit['confidence']}%)")
            
            return {
                "found": True,
                "username_field": best_username["selector"],
                "password_field": best_password["selector"],
                "submit_button": best_submit["selector"] if best_submit else None
            }
        else:
            print("❌ Could not reliably detect login form fields")
            print(f"   Username candidates: {len(username_candidates)}")
            print(f"   Password candidates: {len(password_candidates)}")
            print(f"   Submit candidates: {len(submit_candidates)}")
            return {"found": False}

    def perform_login(self, username: str, password: str, login_data: Dict) -> bool:
        """Universal login performance that works with any detected login form"""
        try:
            print(f"🔧 Attempting to fill username: {username}")
            
            # Universal element finding function
            def find_element_universal(selectors_list, field_name):
                """Try multiple ways to find an element using various selectors"""
                if isinstance(selectors_list, str):
                    selectors_list = [{"selector": selectors_list, "type": "css_selector"}]
                elif isinstance(selectors_list, list) and selectors_list and isinstance(selectors_list[0], str):
                    selectors_list = [{"selector": s, "type": "css_selector"} for s in selectors_list]
                
                element = None
                successful_selector = None
                
                for selector_info in selectors_list:
                    selector = selector_info.get("selector") if isinstance(selector_info, dict) else selector_info
                    if not selector:
                        continue
                        
                    try:
                        # Try different selection methods
                        if selector.startswith('#'):
                            element = self.driver.find_element(By.ID, selector[1:])
                        elif selector.startswith('.'):
                            element = self.driver.find_element(By.CLASS_NAME, selector[1:])
                        elif selector.startswith('//'):
                            element = self.driver.find_element(By.XPATH, selector)
                        elif ':contains(' in selector:
                            # Convert CSS :contains() to XPath
                            text = selector.split(':contains(')[1].rstrip(')')
                            text = text.strip("'\"")
                            tag = selector.split(':contains(')[0] or '*'
                            xpath = f"//{tag}[contains(text(), '{text}')]"
                            element = self.driver.find_element(By.XPATH, xpath)
                        elif '[' in selector or '*' in selector:
                            element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        else:
                            # Try multiple fallback methods
                            try:
                                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                            except:
                                try:
                                    element = self.driver.find_element(By.NAME, selector)
                                except:
                                    try:
                                        element = self.driver.find_element(By.ID, selector)
                                    except:
                                        continue
                        
                        if element and element.is_displayed():
                            successful_selector = selector
                            print(f"✅ Found {field_name} with selector: {selector}")
                            break
                        else:
                            element = None
                            
                    except Exception as e:
                        continue
                
                return element, successful_selector
            
            # Get username element using universal finding
            username_selectors = []
            if login_data.get("selectors", {}).get("username"):
                username_selectors = login_data["selectors"]["username"]
            elif login_data.get("username_field"):
                username_selectors = [login_data["username_field"]]
            
            username_element, username_selector_used = find_element_universal(username_selectors, "username field")
            
            # Get password element using universal finding  
            password_selectors = []
            if login_data.get("selectors", {}).get("password"):
                password_selectors = login_data["selectors"]["password"]
            elif login_data.get("password_field"):
                password_selectors = [login_data["password_field"]]
            
            password_element, password_selector_used = find_element_universal(password_selectors, "password field")
            
            if not username_element:
                print("❌ Could not find username field with any provided selectors")
                return False
                
            if not password_element:
                print("❌ Could not find password field with any provided selectors")
                return False
            
            # Fill the fields with enhanced error handling
            print("📝 Filling username field...")
            try:
                # Simulate human-like interaction
                username_element.click()  # Focus the field first
                self.human_like_delay(0.3, 0.8)  # Random pause like a human
                
                # Human-like typing
                self.human_like_typing(username_element, username)
                self.human_like_delay(0.5, 1.2)  # Wait for validation/events
                
                # Trigger events that might be needed
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", username_element)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", username_element)
                time.sleep(0.5)
                
                # Verify username was filled
                username_value = username_element.get_attribute('value')
                if not username_value:
                    print("⚠️ Username field appears empty, trying alternative method...")
                    from selenium.webdriver.common.keys import Keys
                    username_element.send_keys(Keys.CONTROL + "a")
                    username_element.send_keys(username)
                    time.sleep(0.5)
                    username_value = username_element.get_attribute('value')
                
            except Exception as e:
                print(f"❌ Error filling username: {e}")
                return False
            
            print("📝 Filling password field...")
            try:
                # Simulate human-like interaction  
                password_element.click()  # Focus the field first
                self.human_like_delay(0.2, 0.6)  # Random pause like a human
                
                # Human-like typing for password
                self.human_like_typing(password_element, password, delay_range=(0.08, 0.20))
                self.human_like_delay(0.8, 1.5)  # Wait for validation/events
                
                # Trigger events that might be needed
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", password_element)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", password_element)
                time.sleep(0.5)
                
                # Verify password was filled
                password_value = password_element.get_attribute('value')
                if not password_value:
                    print("⚠️ Password field appears empty, trying alternative method...")
                    from selenium.webdriver.common.keys import Keys
                    password_element.send_keys(Keys.CONTROL + "a")
                    password_element.send_keys(password)
                    time.sleep(0.5)
                    password_value = password_element.get_attribute('value')
                
            except Exception as e:
                print(f"❌ Error filling password: {e}")
                return False
            
            # Verify fields are filled
            final_username = username_element.get_attribute('value')
            final_password = password_element.get_attribute('value')
            
            print(f"🔍 Username filled: {'Yes' if final_username else 'No'}")
            print(f"🔍 Password filled: {'Yes' if final_password else 'No'}")
            
            if not final_username or not final_password:
                print("❌ Failed to fill login fields properly")
                return False
            
            # Use AI to intelligently find the submit button
            submit_element, submit_selector_used = self.ai_submit_button_detection()
            
            # Debug: Print button detection results
            if submit_element:
                print(f"✅ AI found submit button using: {submit_selector_used}")
                print(f"🔍 Button text: '{submit_element.text}'")
                print(f"🔍 Button enabled: {submit_element.is_enabled()}")
                print(f"🔍 Button classes: {submit_element.get_attribute('class')}")
            else:
                print("❌ AI could not identify a submit button")
                
            # Get current URL before any login attempt
            url_before = self.driver.current_url
            
            # If no submit button found, try keyboard fallback
            if not submit_element:
                print("🔄 No submit button detected, trying common alternatives...")
                
                # Try pressing Enter on password field
                try:
                    from selenium.webdriver.common.keys import Keys
                    password_element.send_keys(Keys.RETURN)
                    print("✅ Pressed Enter on password field")
                    time.sleep(LOGIN_WAIT_TIME)
                except:
                    pass
            else:
                # Wait for button to become enabled (important for Material-UI forms)
                print("⏳ Waiting for submit button to become enabled...")
                button_enabled = False
                max_wait = 10  # seconds
                wait_interval = 0.5
                
                for i in range(int(max_wait / wait_interval)):
                    try:
                        if submit_element.is_enabled() and "disabled" not in submit_element.get_attribute("class"):
                            button_enabled = True
                            print("✅ Submit button is now enabled!")
                            break
                        else:
                            print(f"⏳ Button still disabled... waiting ({i * wait_interval:.1f}s)")
                            # Human-like waiting with slight variation
                            time.sleep(wait_interval + random.uniform(-0.1, 0.1))
                            # Re-find element in case it changed
                            submit_element, _ = find_element_universal(submit_selectors, "submit button")
                            if not submit_element:
                                break
                    except:
                        time.sleep(wait_interval)
                
                if not button_enabled:
                    print("⚠️ Button never became enabled, trying to click anyway...")
                
                print(f"🔘 Clicking submit button using: {submit_selector_used}")
                
                # Try multiple click methods in order of preference
                click_successful = False
                
                # Method 1: Regular click if enabled
                if button_enabled:
                    try:
                        print("🔧 Method 1: Regular click...")
                        submit_element.click()
                        print("✅ Regular click successful!")
                        click_successful = True
                    except Exception as e:
                        print(f"⚠️ Regular click failed: {e}")
                
                # Method 2: JavaScript click
                if not click_successful:
                    try:
                        print("🔧 Method 2: JavaScript click...")
                        self.driver.execute_script("arguments[0].click();", submit_element)
                        print("✅ JavaScript click successful!")
                        click_successful = True
                    except Exception as e:
                        print(f"⚠️ JavaScript click failed: {e}")
                
                # Method 3: Scroll to element and click
                if not click_successful:
                    try:
                        print("🔧 Method 3: Scroll to element and click...")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_element)
                        time.sleep(0.5)
                        submit_element.click()
                        print("✅ Scroll and click successful!")
                        click_successful = True
                    except Exception as e:
                        print(f"⚠️ Scroll and click failed: {e}")
                
                # Method 4: Form submission
                if not click_successful:
                    try:
                        print("🔧 Method 4: Form submission...")
                        form_element = submit_element.find_element(By.XPATH, "./ancestor::form[1]")
                        self.driver.execute_script("arguments[0].submit();", form_element)
                        print("✅ Form submission successful!")
                        click_successful = True
                    except Exception as e:
                        print(f"⚠️ Form submission failed: {e}")
                
                # Method 5: Enter key on password field
                if not click_successful:
                    try:
                        print("🔧 Method 5: Enter key on password field...")
                        from selenium.webdriver.common.keys import Keys
                        password_element.send_keys(Keys.RETURN)
                        print("✅ Enter key successful!")
                        click_successful = True
                    except Exception as e:
                        print(f"⚠️ Enter key failed: {e}")
                
                if not click_successful:
                    print("❌ All click methods failed!")
                    return False
                    
                print("⏳ Waiting for login response...")
                time.sleep(LOGIN_WAIT_TIME)
            
            # Enhanced login success verification
            url_after = self.driver.current_url
            page_source = self.driver.page_source.lower()
            
            # More comprehensive error detection
            login_error_indicators = [
                "invalid username or password",
                "invalid email or password",
                "login failed",
                "authentication failed",
                "incorrect username",
                "incorrect password",
                "login error",
                "sign in failed",
                "unable to log in",
                "authentication error",
                "login unsuccessful"
            ]
            
            has_login_error = any(error in page_source for error in login_error_indicators)
            
            # Success indicators
            success_indicators = [
                "dashboard", "account", "welcome", "billing", "utilities",
                "logout", "sign out", "profile", "settings"
            ]
            
            has_success_indicator = any(indicator in page_source for indicator in success_indicators)
            
            # URL change analysis
            url_changed = url_before != url_after
            still_on_login = any(term in url_after.lower() for term in ["login", "signin", "auth"])
            
            print(f"🔍 URL changed: {url_changed}")
            print(f"🔍 Still on login URL: {still_on_login}")
            print(f"🔍 Login error messages: {has_login_error}")
            print(f"🔍 Success indicators found: {has_success_indicator}")
            
            # Determine login success with enhanced logic
            if has_login_error:
                print("❌ Login failed - error message detected")
                return False
            elif url_changed and not still_on_login:
                print("✅ Login successful - redirected away from login page")
                return True
            elif has_success_indicator and not has_login_error:
                print("✅ Login successful - success indicators found (modern SPA)")
                return True
            elif url_changed and has_success_indicator:
                print("✅ Login successful - URL changed with success indicators")
                return True
            elif not still_on_login and not has_login_error:
                print("✅ Login appears successful - not on login page and no errors")
                return True
            else:
                print("⚠️ Login status unclear - proceeding with caution")
                return True  # Give benefit of doubt for modern apps
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    def detect_and_call_billing_apis(self, html_content: str) -> BillInfo:
        """Detect API endpoints from page source and call them directly for faster data retrieval"""
        try:
            print("🔍 Analyzing page for API endpoints...")
            
            # Extract potential API endpoints from JavaScript
            api_endpoints = self.extract_api_endpoints_from_js(html_content)
            
            if api_endpoints:
                print(f"🎯 Found {len(api_endpoints)} potential API endpoints")
                
                # Try to call each API endpoint
                for endpoint in api_endpoints:
                    print(f"🌐 Trying API: {endpoint['url']}")
                    api_data = self.call_billing_api(endpoint)
                    
                    if api_data:
                        print("✅ Successfully retrieved data from API!")
                        return self.parse_api_response(api_data)
            
            print("⚠️ No working APIs found, falling back to HTML parsing...")
            return self.enhanced_historical_transaction_search(html_content)
            
        except Exception as e:
            print(f"❌ API detection failed: {e}")
            return self.enhanced_historical_transaction_search(html_content)
    
    def extract_api_endpoints_from_js(self, html_content: str) -> List[Dict]:
        """Extract API endpoints from JavaScript code in the page"""
        try:
            endpoints = []
            
            # Common API patterns to look for
            api_patterns = [
                # REST API patterns
                r'["\']([^"\']*\/api\/[^"\']*billing[^"\']*)["\']',
                r'["\']([^"\']*\/api\/[^"\']*transaction[^"\']*)["\']', 
                r'["\']([^"\']*\/api\/[^"\']*history[^"\']*)["\']',
                r'["\']([^"\']*\/api\/[^"\']*statement[^"\']*)["\']',
                r'["\']([^"\']*\/api\/[^"\']*usage[^"\']*)["\']',
                
                # Specific utility company patterns
                r'["\']([^"\']*\/services\/[^"\']*billing[^"\']*)["\']',
                r'["\']([^"\']*\/data\/[^"\']*billing[^"\']*)["\']',
                r'["\']([^"\']*\/rest\/[^"\']*billing[^"\']*)["\']',
                
                # GraphQL patterns
                r'["\']([^"\']*\/graphql[^"\']*)["\']',
                
                # Common endpoint patterns
                r'["\']([^"\']*\/getBilling[^"\']*)["\']',
                r'["\']([^"\']*\/getTransactions[^"\']*)["\']',
                r'["\']([^"\']*\/getHistory[^"\']*)["\']',
            ]
            
            current_url = self.driver.current_url
            base_url = '/'.join(current_url.split('/')[:3])
            
            print(f"🔍 Scanning JavaScript for API patterns...")
            
            for pattern in api_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    # Clean and validate the URL
                    if match.startswith('/'):
                        full_url = base_url + match
                    elif match.startswith('http'):
                        full_url = match
                    else:
                        full_url = base_url + '/' + match
                    
                    endpoint_info = {
                        'url': full_url,
                        'method': 'GET',
                        'type': 'rest',
                        'pattern': pattern
                    }
                    
                    if endpoint_info not in endpoints:
                        endpoints.append(endpoint_info)
                        print(f"   📍 Found: {full_url}")
            
            # Also look for fetch/XMLHttpRequest calls
            fetch_patterns = [
                r'fetch\s*\(\s*["\']([^"\']+)["\']',
                r'XMLHttpRequest.*open\s*\(\s*["\']GET["\'],\s*["\']([^"\']+)["\']',
                r'axios\.get\s*\(\s*["\']([^"\']+)["\']',
                r'\$\.get\s*\(\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in fetch_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    if any(keyword in match.lower() for keyword in ['billing', 'transaction', 'history', 'statement']):
                        if match.startswith('/'):
                            full_url = base_url + match
                        elif match.startswith('http'):
                            full_url = match
                        else:
                            continue
                            
                        endpoint_info = {
                            'url': full_url,
                            'method': 'GET', 
                            'type': 'ajax',
                            'pattern': pattern
                        }
                        
                        if endpoint_info not in endpoints:
                            endpoints.append(endpoint_info)
                            print(f"   🌐 Found AJAX: {full_url}")
            
            return endpoints[:10]  # Limit to top 10 candidates
            
        except Exception as e:
            print(f"❌ Error extracting API endpoints: {e}")
            return []
    
    def call_billing_api(self, endpoint: Dict) -> Dict:
        """Call a discovered API endpoint with proper authentication"""
        try:
            # Get cookies from current session for authentication
            cookies = self.driver.get_cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # Get common headers
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': self.driver.current_url,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            # Try the API call
            response = requests.get(
                endpoint['url'],
                headers=headers,
                cookies=session_cookies,
                timeout=10,
                verify=True
            )
            
            if response.status_code == 200:
                try:
                    json_data = response.json()
                    print(f"✅ API call successful: {len(str(json_data))} characters of JSON data")
                    return json_data
                except:
                    # Sometimes APIs return HTML or other formats
                    print(f"⚠️ API returned non-JSON data: {response.headers.get('content-type')}")
                    return None
            else:
                print(f"❌ API call failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error calling API {endpoint['url']}: {e}")
            return None
    
    def parse_api_response(self, json_data: Dict) -> BillInfo:
        """Parse JSON API response to extract billing information"""
        try:
            print("🔍 Parsing API response for billing data...")
            
            # This would need to be customized based on the specific API response format
            # For now, let's try to find common patterns
            
            bills = []
            
            # Look for common JSON structures
            possible_data_keys = ['data', 'results', 'bills', 'transactions', 'history', 'statements', 'records']
            billing_data = None
            
            for key in possible_data_keys:
                if key in json_data and isinstance(json_data[key], list):
                    billing_data = json_data[key]
                    break
            
            if not billing_data and isinstance(json_data, list):
                billing_data = json_data
            
            if billing_data:
                for item in billing_data:
                    # Try to extract date and amount from various possible field names
                    date_fields = ['date', 'billDate', 'transactionDate', 'statementDate', 'dueDate', 'serviceDate']
                    amount_fields = ['amount', 'billAmount', 'totalAmount', 'balance', 'totalDue', 'charges']
                    
                    bill_date = None
                    bill_amount = None
                    
                    for date_field in date_fields:
                        if date_field in item:
                            try:
                                # Try to parse the date
                                date_str = str(item[date_field])
                                bill_date = datetime.strptime(date_str, '%Y-%m-%d')
                                break
                            except:
                                try:
                                    bill_date = datetime.strptime(date_str, '%m/%d/%Y')
                                    break
                                except:
                                    continue
                    
                    for amount_field in amount_fields:
                        if amount_field in item:
                            try:
                                bill_amount = float(str(item[amount_field]).replace('$', '').replace(',', ''))
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
                    # Sort by date (newest first)
                    bills.sort(key=lambda x: x['date'], reverse=True)
                    
                    # Create BillInfo with all bills
                    current_bill = bills[0] if bills else None
                    previous_bill = bills[1] if len(bills) > 1 else None
                    
                    bill_result = BillInfo(
                        previous_month=f"Previous Bill ({previous_bill['date'].strftime('%m/%d/%Y')})" if previous_bill else "No previous data",
                        previous_amount=previous_bill['amount'] if previous_bill else 0.0,
                        current_month=f"Current Bill ({current_bill['date'].strftime('%m/%d/%Y')})" if current_bill else "No current data",
                        current_amount=current_bill['amount'] if current_bill else 0.0,
                        account_number="API Data"
                    )
                    
                    bill_result.all_bills = bills
                    return bill_result
            
            print("⚠️ Could not extract billing data from API response structure")
            return BillInfo("No API data found", 0.0, "No API data found", 0.0)
            
        except Exception as e:
            print(f"❌ Error parsing API response: {e}")
            return BillInfo("API parse error", 0.0, "API parse error", 0.0)
    
    def vision_ai_screenshot_analysis(self) -> BillInfo:
        """Take screenshot and use vision AI to extract billing data - universal fallback"""
        try:
            # Check if vision AI is available
            if not VISION_AI_AVAILABLE:
                print("❌ Vision AI unavailable - Pillow not installed")
                return BillInfo("Vision AI unavailable", 0.0, "Install Pillow for Vision AI", 0.0)
            
            print("📸 Taking screenshot for vision AI analysis...")
            
            # Take screenshot of current page
            screenshot_path = "/tmp/autobilling_screenshot.png"
            self.driver.save_screenshot(screenshot_path)
            
            # Convert screenshot to base64 for vision model
            with open(screenshot_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            
            print("👁️ Analyzing screenshot with vision AI...")
            
            # Prepare vision AI prompt
            vision_prompt = """You are analyzing a screenshot of a utility billing website. Please extract ALL billing/transaction data visible on the page.

Look for:
- Bill amounts (like $199.00, $132.00, etc.)
- Bill dates (like 06/27/2025, 05/29/2025, etc.) 
- Account information
- Transaction history
- Payment records

Extract this data and return it in JSON format:
{
    "bills": [
        {
            "date": "MM/DD/YYYY",
            "amount": 199.00,
            "description": "Electric Service",
            "type": "bill"
        }
    ],
    "account_info": {
        "account_number": "if visible",
        "customer_name": "if visible"
    }
}

If you see a table or list of bills, extract ALL entries. Focus on finding historical billing data.
Be precise with numbers and dates. If no billing data is visible, return {"bills": [], "account_info": {}}.
"""

            # Call vision model with timeout for faster processing
            try:
                print(f"🧠 Using {VISION_MODEL} for faster analysis...")
                response = ollama.chat(
                    model=VISION_MODEL,
                    messages=[
                        {
                            'role': 'user',
                            'content': vision_prompt,
                            'images': [image_base64]
                        }
                    ],
                    options={
                        'temperature': 0.1,  # More focused responses
                        'num_predict': 1000,  # Limit response length for speed
                    }
                )
                
                vision_response = response['message']['content']
                print(f"🤖 Vision AI response: {vision_response[:200]}...")
                
                # Parse the JSON response
                import json
                
                # Extract JSON from response (might have extra text)
                json_match = re.search(r'\{.*\}', vision_response, re.DOTALL)
                if json_match:
                    billing_data = json.loads(json_match.group())
                    
                    bills = billing_data.get('bills', [])
                    account_info = billing_data.get('account_info', {})
                    
                    if bills:
                        print(f"👁️ Vision AI found {len(bills)} bills!")
                        
                        # Convert to our bill format
                        processed_bills = []
                        for bill in bills:
                            try:
                                bill_date = datetime.strptime(bill['date'], '%m/%d/%Y')
                                bill_amount = float(bill['amount'])
                                
                                processed_bills.append({
                                    'date': bill_date,
                                    'amount': bill_amount,
                                    'type': bill.get('type', 'bill'),
                                    'description': bill.get('description', 'Utility Bill')
                                })
                            except:
                                continue
                        
                        if processed_bills:
                            # Sort by date (newest first)
                            processed_bills.sort(key=lambda x: x['date'], reverse=True)
                            
                            # Create BillInfo object
                            current_bill = processed_bills[0] if processed_bills else None
                            previous_bill = processed_bills[1] if len(processed_bills) > 1 else None
                            
                            bill_result = BillInfo(
                                previous_month=f"Previous Bill ({previous_bill['date'].strftime('%m/%d/%Y')})" if previous_bill else "No previous data",
                                previous_amount=previous_bill['amount'] if previous_bill else 0.0,
                                current_month=f"Current Bill ({current_bill['date'].strftime('%m/%d/%Y')})" if current_bill else "No current data",
                                current_amount=current_bill['amount'] if current_bill else 0.0,
                                account_number=account_info.get('account_number', 'Vision AI Data')
                            )
                            
                            # Add comprehensive billing history
                            bill_result.all_bills = processed_bills
                            return bill_result
                    
                    print("👁️ Vision AI did not find billing data in screenshot")
                    
                else:
                    print("❌ Vision AI response was not valid JSON")
                    
            except Exception as e:
                print(f"❌ Vision AI analysis failed: {e}")
                
            return BillInfo("Vision AI found no data", 0.0, "Vision AI found no data", 0.0)
            
        except Exception as e:
            print(f"❌ Screenshot analysis failed: {e}")
            return BillInfo("Screenshot failed", 0.0, "Screenshot failed", 0.0)

    def enhanced_historical_transaction_search(self, html_content: str) -> BillInfo:
        """Enhanced search specifically for historical billing transactions"""
        try:
            print("🔍 Enhanced historical transaction search...")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            page_text = soup.get_text()
            
            # Strategy 1: Look for transaction/history tables with comprehensive patterns
            historical_data = []
            
            # Find actual transaction data containers (be more selective)
            transaction_containers = []
            
            # Look for tables with actual data first (most reliable)
            tables = soup.find_all('table')
            print(f"🔍 DEBUG - Found {len(tables)} tables on the page")
            

            
            for i, table in enumerate(tables):
                table_text = table.get_text()
                rows = table.find_all('tr')
                print(f"🔍 DEBUG - Table {i+1}: {len(rows)} rows, contains billing keywords: {any(keyword in table_text.lower() for keyword in ['date', 'amount', 'transaction', 'bill', 'payment'])}")
                
                # Show first few rows of each table
                if len(rows) > 0:
                    print(f"   First row text: {rows[0].get_text()[:100]}...")
                    if len(rows) > 1:
                        print(f"   Second row text: {rows[1].get_text()[:100]}...")
                
                # Check if table contains transaction-like data
                if (any(keyword in table_text.lower() for keyword in ['date', 'amount', 'transaction', 'bill', 'payment']) and
                    len(table.find_all('tr')) >= 3):  # At least header + 2 data rows
                    transaction_containers.append(table)
                    print(f"   ✅ Added table {i+1} as transaction container")
            
            # Look for specific transaction containers only if no good tables found
            if len(transaction_containers) < 1:
                transaction_selectors = [
                    '[class*="transaction"]',
                    '[class*="billing"]', 
                    '[class*="history"]',
                    '[id*="transaction"]',
                    '[id*="billing"]',
                    '[id*="history"]'
                ]
                
                for selector in transaction_selectors:
                    containers = soup.select(selector)
                    for container in containers:
                        container_text = container.get_text()
                        # Only include if it has transaction-like content
                        if (any(keyword in container_text.lower() for keyword in 
                               ['date', 'amount', 'transaction', 'bill', 'payment']) and
                            len(container_text) > 100):  # Has substantial content
                            transaction_containers.append(container)
            
            print(f"🔍 Found {len(transaction_containers)} qualified transaction containers")
            
            # Process each container for historical data (limit per container to avoid duplicates)
            total_processed = 0
            max_total_transactions = 50  # Global limit
            
            for container_idx, container in enumerate(transaction_containers):
                if total_processed >= max_total_transactions:
                    print(f"⚠️ Reached global limit of {max_total_transactions} transactions")
                    break
                    
                container_text = container.get_text()
                container_transactions = 0  # Count transactions from this container
                
                # Enhanced date patterns (prioritize 4-digit years)
                date_patterns = [
                    r'(\d{1,2}/\d{1,2}/\d{4})',          # MM/DD/YYYY (priority)
                    r'(\d{4}-\d{2}-\d{2})',              # YYYY-MM-DD  
                    r'(\d{1,2}-\d{1,2}-\d{4})',          # MM-DD-YYYY
                    r'(\w{3}\s+\d{1,2},?\s+\d{4})',      # Jan 15, 2024
                    r'(\d{1,2}/\d{1,2}/\d{2})',          # MM/DD/YY (last resort)
                    r'(\d{1,2}\s+\w{3}\s+\d{4})',        # 15 Jan 2024
                    r'(\w{3}-\d{1,2}-\d{4})',            # Jan-15-2024
                ]
                
                # Enhanced amount patterns
                amount_patterns = [
                    r'\$(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',          # $1,234.56
                    r'(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)\s*USD',      # 1234.56 USD
                    r'Amount:\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)', # Amount: $123.45
                    r'Total:\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',  # Total: $123.45
                    r'(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)\s*(?:billed|due|charged)', # 123.45 billed
                ]
                
                # Look for rows/items within containers
                if container.name == 'table':
                    rows = container.find_all('tr')
                elif container.name in ['ul', 'ol']:
                    rows = container.find_all('li')
                else:
                    # For divs, look for child elements that might be rows
                    rows = container.find_all(['div', 'tr', 'li'])
                
                for row in rows:
                    row_text = row.get_text()
                    
                    # Find dates in this row
                    dates_found = []
                    for date_pattern in date_patterns:
                        matches = re.finditer(date_pattern, row_text, re.IGNORECASE)
                        for match in matches:
                            dates_found.append(match.group(1))
                    
                    # Find amounts in this row
                    amounts_found = []
                    for amount_pattern in amount_patterns:
                        matches = re.finditer(amount_pattern, row_text, re.IGNORECASE)
                        for match in matches:
                            try:
                                amount_str = match.group(1).replace(',', '')
                                amount = float(amount_str)
                                if 5.0 <= amount <= 5000.0:  # Broader range for utility bills
                                    amounts_found.append(amount)
                            except:
                                continue
                    
                    # If we found both dates and amounts, create transaction records
                    if dates_found and amounts_found:
                        for date_str in dates_found:
                            for amount in amounts_found:
                                try:
                                    # Parse date with multiple format attempts
                                    parsed_date = None
                                    date_formats = [
                                        '%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y',
                                        '%b %d, %Y', '%d %b %Y', '%b-%d-%Y'
                                    ]
                                    
                                    for date_format in date_formats:
                                        try:
                                            parsed_date = datetime.strptime(date_str, date_format)
                                            break
                                        except:
                                            continue
                                    
                                    # Handle 2-digit years specially (assume 2020s)
                                    if not parsed_date and '/' in date_str:
                                        try:
                                            temp_date = datetime.strptime(date_str, '%m/%d/%y')
                                            # Convert 2-digit year to 2020s if it looks like recent utility bill
                                            if temp_date.year < 2000:  # 1900s interpretation
                                                corrected_year = temp_date.year + 100  # Make it 2000s
                                                parsed_date = temp_date.replace(year=corrected_year)
                                            else:
                                                parsed_date = temp_date
                                        except:
                                            pass
                                    
                                    if parsed_date:
                                        # Validate date is reasonable
                                        current_year = datetime.now().year
                                        if parsed_date.year < (current_year - 10) or parsed_date.year > (current_year + 1):
                                            continue  # Skip unreasonable dates
                                        
                                        # Determine transaction type
                                        transaction_type = 'bill'
                                        if any(word in row_text.lower() for word in ['payment', 'paid', 'credit']):
                                            transaction_type = 'payment'
                                        elif any(word in row_text.lower() for word in ['bill', 'charge', 'invoice', 'usage']):
                                            transaction_type = 'bill'
                                        
                                        # Create unique description
                                        clean_description = row_text.strip()[:100]
                                        
                                        historical_data.append({
                                            'date': parsed_date,
                                            'amount': amount,
                                            'type': transaction_type,
                                            'description': clean_description
                                        })
                                        
                                        container_transactions += 1
                                        total_processed += 1
                                        print(f"📅 Historical data: {date_str} → ${amount:.2f} ({transaction_type})")
                                        
                                        # Limit transactions per container to avoid duplicates
                                        if container_transactions >= 20 or total_processed >= max_total_transactions:
                                            print(f"⚠️ Limiting container {container_idx} (container: {container_transactions}, total: {total_processed})")
                                            break
                                        
                                except Exception as parse_error:
                                    continue
                            
                            # Break out of amount loop if we hit limits
                            if container_transactions >= 20 or total_processed >= max_total_transactions:
                                break
                        
                        # Break out of date loop if we hit limits
                        if container_transactions >= 20 or total_processed >= max_total_transactions:
                            break
            
            # Remove duplicates with more robust logic (month/day/amount combination)
            unique_data = {}
            for item in historical_data:
                # Create a unique key using month, day, and amount (ignore year for duplicates)
                month_day = item['date'].strftime('%m-%d')
                key = (month_day, item['amount'], item['type'])
                
                if key not in unique_data:
                    unique_data[key] = item
                else:
                    # Keep the one with the more recent/realistic year
                    existing_year = unique_data[key]['date'].year
                    current_year_val = datetime.now().year
                    
                    # Prefer dates closer to current year
                    if abs(item['date'].year - current_year_val) < abs(existing_year - current_year_val):
                        unique_data[key] = item
                    # If same distance from current year, keep the one with better description
                    elif (abs(item['date'].year - current_year_val) == abs(existing_year - current_year_val) and
                          len(item['description']) > len(unique_data[key]['description'])):
                        unique_data[key] = item
            
            # Convert back to list and sort by date (most recent first)
            deduplicated_data = list(unique_data.values())
            deduplicated_data.sort(key=lambda x: x['date'], reverse=True)
            
            # Filter and validate data (more permissive approach)
            bills_only = []
            current_year = datetime.now().year
            
            for item in deduplicated_data:
                # More permissive type filtering - include bills and unknown types
                if item['type'] == 'payment':
                    continue  # Only exclude obvious payments
                    
                # More permissive date validation (within last 15 years, future dates up to +2 years)
                if item['date'].year < (current_year - 15) or item['date'].year > (current_year + 2):
                    print(f"⚠️ Skipping invalid date: {item['date']} (amount: ${item['amount']})")
                    continue
                    
                # More permissive amount validation for utility bills ($1 to $5000)
                if item['amount'] < 1 or item['amount'] > 5000:
                    print(f"⚠️ Skipping unreasonable amount: ${item['amount']} (date: {item['date']})")
                    continue
                    
                bills_only.append(item)
            
            # Limit to max 24 months (2 years) of data for sanity
            bills_only = bills_only[:24]
            
            print(f"📊 Found {len(historical_data)} raw transactions, {len(deduplicated_data)} unique, {len(bills_only)} valid bills")
            
            # DEBUG: Show what raw data was extracted
            if len(historical_data) > 0:
                print("🔍 DEBUG - First 10 raw transactions found:")
                for i, item in enumerate(historical_data[:10]):
                    print(f"   {i+1}. {item['date'].strftime('%m/%d/%Y')}: ${item['amount']:.2f} ({item['type']}) - {item['description'][:50]}")
            
            # DEBUG: Show what bills were kept after filtering  
            if len(bills_only) > 0:
                print("🔍 DEBUG - Valid bills after filtering:")
                for i, bill in enumerate(bills_only):
                    print(f"   {i+1}. {bill['date'].strftime('%m/%d/%Y')}: ${bill['amount']:.2f} - {bill['description'][:50]}")
            
            # DEBUG: Check if comprehensive data is being created
            if len(bills_only) >= 1:
                print("🔍 DEBUG - Creating comprehensive billing data...")
            
            # Debug: Show what data was found and why it might be filtered
            if len(deduplicated_data) > 0 and len(bills_only) == 0:
                print("🔍 DEBUG: Raw data found but filtered out. Checking reasons...")
                current_year = datetime.now().year
                for item in deduplicated_data[:5]:  # Show first 5 for debugging
                    reason = []
                    if item['type'] != 'bill':
                        reason.append(f"type={item['type']}")
                    if item['date'].year < (current_year - 10) or item['date'].year > (current_year + 1):
                        reason.append(f"invalid_year={item['date'].year}")
                    if item['amount'] < 5 or item['amount'] > 2000:
                        reason.append(f"invalid_amount=${item['amount']}")
                    
                    filter_reason = ", ".join(reason) if reason else "SHOULD_BE_VALID"
                    print(f"   • {item['date'].strftime('%m/%d/%Y')}: ${item['amount']:.2f} ({item['type']}) -> {filter_reason}")
            
            # Debug: Show valid bills found
            if len(bills_only) > 0:
                print("✅ Valid bills found:")
                for bill in bills_only[:3]:  # Show first 3
                    print(f"   • {bill['date'].strftime('%m/%d/%Y')}: ${bill['amount']:.2f}")
            
            # Return ALL bills for comprehensive analysis
            if len(bills_only) >= 1:
                # For compatibility with BillInfo, still return the most recent 2
                current_bill = bills_only[0] if len(bills_only) >= 1 else None
                previous_bill = bills_only[1] if len(bills_only) >= 2 else None
                
                # Store all bills in a special attribute for comprehensive display
                bill_result = BillInfo(
                    previous_month=f"Previous Bill ({previous_bill['date'].strftime('%m/%d/%Y')})" if previous_bill else "No previous data",
                    previous_amount=previous_bill['amount'] if previous_bill else 0.0,
                    current_month=f"Current Bill ({current_bill['date'].strftime('%m/%d/%Y')})" if current_bill else "No current data",
                    current_amount=current_bill['amount'] if current_bill else 0.0,
                    account_number="Historical Data"
                )
                
                # Add all historical bills for comprehensive display
                bill_result.all_bills = bills_only
                return bill_result
            
            return BillInfo("No historical data found", 0.0, "No historical data found", 0.0)
            
        except Exception as e:
            print(f"❌ Enhanced historical search error: {e}")
            return BillInfo("Error in historical search", 0.0, "Error in historical search", 0.0)

    def has_meaningful_billing_data(self, bill_info: BillInfo) -> bool:
        """Check if BillInfo contains meaningful billing data regardless of attribute names"""
        try:
            # Check for comprehensive historical data
            if hasattr(bill_info, 'all_bills') and bill_info.all_bills:
                return len(bill_info.all_bills) > 0
            
            # Check for basic billing data
            if (bill_info.current_amount > 0 or 
                bill_info.previous_amount > 0 or
                bill_info.current_month not in ["No data found", "Error", "Screenshot failed", "Vision AI found no data"]):
                return True
                
            return False
        except:
            return False

    def smart_billing_extraction(self, html_content: str, is_billing_page: bool = False) -> BillInfo:
        """Smart billing extraction: tries HTML first, then Vision AI only on confirmed billing pages"""
        try:
            print("🧠 Smart billing extraction starting...")
            
            # Strategy 1: API detection (fastest, most reliable)
            print("🔍 Trying API detection...")
            api_result = self.detect_and_call_billing_apis(html_content)
            if self.has_meaningful_billing_data(api_result):
                print("✅ API detection found meaningful data!")
                return api_result
            
            # Strategy 2: Enhanced HTML parsing
            print("🔍 Trying HTML parsing...")
            html_result = self.enhanced_historical_transaction_search(html_content)
                if self.has_meaningful_billing_data(html_result):
                print("✅ HTML parsing found meaningful data!")
                return html_result
            
            # Strategy 3: Vision AI (only on confirmed billing history pages)
            if is_billing_page:
                if VISION_AI_AVAILABLE:
                    print("🎯 Confirmed billing page + HTML failed → Using Vision AI...")
                vision_result = self.vision_ai_screenshot_analysis()
                if self.has_meaningful_billing_data(vision_result):
                    print("✅ Vision AI found meaningful data!")
                    return vision_result
                else:
                print("⚠️ Vision AI unavailable - install Pillow: pip install Pillow")
            else:
                print("ℹ️ Not a billing history page - skipping Vision AI")
            
            # Final fallback: Basic dashboard extraction
            print("⚠️ All advanced methods failed, trying basic dashboard extraction...")
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for current bill indicators on dashboard
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
            
            # Strategy 2: Look for table rows with dates and amounts to sort chronologically
            date_amount_pairs = []
            
            # Check tables for date/amount patterns
            table_selectors = [
                'table',
                '[class*="table"]',
                '[class*="forge-table"]',
                '[class*="billing"]',
                '[class*="transaction"]',
                '[class*="statement"]'
            ]
            
            for selector in table_selectors:
                tables = soup.select(selector)
                for table in tables:
                    # Look for table rows with both dates and amounts
                    rows = table.find_all('tr')
                    for row in rows:
                        row_text = row.get_text()
                        
                        # Look for date patterns
                        date_patterns = [
                            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
                            r'(\d{4}-\d{2}-\d{2})',      # YYYY-MM-DD
                            r'(\d{1,2}-\d{1,2}-\d{4})',  # MM-DD-YYYY
                        ]
                        
                        # Look for amount patterns
                        amount_patterns = [
                            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $123.45
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
            
            # If we found bills with dates, return comprehensive data
            if len(recent_bills) >= 1:
                current_amount = recent_bills[0][1] if len(recent_bills) >= 1 else 0
                previous_amount = recent_bills[1][1] if len(recent_bills) >= 2 else 0
                
                print(f"✅ Found {len(recent_bills)} date-sorted bills")
                
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
                
                # Create comprehensive bill result
                bill_result = BillInfo(
                    previous_month=f"Previous Bill ({recent_bills[1][0].strftime('%m/%d/%Y')})" if len(recent_bills) >= 2 else "No previous data",
                    previous_amount=previous_amount,
                    current_month=f"Current Bill ({recent_bills[0][0].strftime('%m/%d/%Y')})",
                    current_amount=current_amount,
                    account_number=account_number or "Unknown"
                )
                
                # Add all bills for comprehensive display
                all_bills = []
                for date, amount in recent_bills:
                    all_bills.append({
                        'date': date,
                        'amount': amount,
                        'type': 'bill',
                        'description': f'Utility Bill for {date.strftime("%b %Y")}'
                    })
                
                bill_result.all_bills = all_bills
                return bill_result
            
            # Strategy 3: Fallback to amount-based extraction
            print("⚠️  No dates found, falling back to amount-based extraction...")
            amounts = []
            
            # Look for amounts in various elements
            amount_selectors = [
                '[class*="amount"]',
                '[class*="total"]', 
                '[class*="balance"]',
                '[class*="bill"]',
                '[class*="payment"]',
                'td', 'th', 'div', 'span'
            ]
            
            patterns_to_try = [
                r'\$[\d,]+\.?\d*',  # $123.45
                r'[\d,]+\.?\d*\s*USD',  # 123.45 USD
                r'Amount:\s*\$?[\d,]+\.?\d*',  # Amount: $123.45
                r'Total:\s*\$?[\d,]+\.?\d*',   # Total: $123.45
                r'Balance:\s*\$?[\d,]+\.?\d*'  # Balance: $123.45
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
                                    if 10.0 <= amount <= 2000.0:  # Reasonable range
                                        amounts.append(amount)
                            except:
                                continue
            
            # Remove duplicates and filter reasonable amounts
            reasonable_amounts = list(set(amounts))
            reasonable_amounts = [amt for amt in reasonable_amounts if 10.0 <= amt <= 2000.0]
            reasonable_amounts.sort(reverse=True)
            
            print(f"📊 Found {len(reasonable_amounts)} reasonable billing amounts: {reasonable_amounts[:5]}")
            
            # Extract current and previous amounts
            if len(reasonable_amounts) >= 2:
                current_amount = reasonable_amounts[0]
                previous_amount = reasonable_amounts[1]
                
                return BillInfo(
                    previous_month="Previous Bill",
                    previous_amount=previous_amount,
                    current_month="Current Bill",
                    current_amount=current_amount,
                    account_number="Unknown"
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
                return BillInfo("No data found", 0.0, "No data found", 0.0)
                
        except Exception as e:
            print(f"❌ Universal extraction error: {e}")
            return BillInfo("Error occurred", 0.0, "Error occurred", 0.0)
    
    def scrape_utility_bill(self, url: str, username: str, password: str) -> BillInfo:
        """Main function to scrape utility bill information"""
        try:
            # Setup driver
            self.setup_driver()
            
            print(f"🌐 Navigating to {url}")
            self.driver.get(url)
            
            # Human-like delay after page load
            print("⏳ Allowing page to fully load...")
            self.human_like_delay(2.0, 4.0)
            
            # Get initial page content
            html_content = self.driver.page_source
            
            # Find login elements
            print("🔍 Analyzing page for login elements...")
            login_data = self.find_login_elements(html_content)
            
            if login_data.get("found"):
                print("🔐 Login form found, attempting to login...")
                if self.perform_login(username, password, login_data):
                    print("✅ Login successful!")
                    
                    # Enhanced wait for SPA navigation and session establishment
                    print("⏳ Waiting for SPA navigation and session establishment...")
                    time.sleep(8)  # Initial wait extended for SPAs
                    
                    # Additional wait for dynamic content in SPAs
                    print("⏳ Allowing additional time for dynamic content loading...")
                    try:
                        # Wait for common SPA loading indicators to disappear
                        WebDriverWait(self.driver, 10).until_not(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".loading, .spinner, mat-spinner, .mat-progress-spinner"))
                        )
                    except:
                        pass  # Continue if no loading indicators found
                    
                    time.sleep(3)  # Additional buffer for content rendering
                    
                    # Check if we're still on login page after initial wait
                    current_url = self.driver.current_url
                    if "login" in current_url.lower():
                        print("🔄 Still on login page, waiting longer for SPA redirect...")
                        time.sleep(10)  # Additional wait for slow SPAs
                        
                        # Force refresh if still stuck
                        current_url = self.driver.current_url
                        if "login" in current_url.lower():
                            print("🔄 Refreshing page to trigger proper navigation...")
                            self.driver.refresh()
                            time.sleep(5)
                    
                    # Instead of hardcoded navigation, intelligently explore the site
                    return self.intelligent_post_login_exploration()
                    
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
    
    def ai_detect_billing_history_page(self, page_source: str) -> Dict:
        """AI specifically detects if current page is a billing history/transaction page"""
        try:
            print("🤖 AI detecting if this is a billing history page...")
            
            soup = BeautifulSoup(page_source, 'html.parser')
            page_text = soup.get_text(separator=' ', strip=True)
            
            # Quick analysis for AI
            analysis_prompt = f"""
You are analyzing a web page to determine if it contains UTILITY BILLING HISTORY or TRANSACTION HISTORY.

PAGE CONTENT SAMPLE (first 2000 characters):
{page_text[:2000]}

TASK: Determine if this page shows historical billing/transaction data (not just current bill).

BILLING HISTORY PAGE INDICATORS:
✅ Multiple billing entries with dates and amounts
✅ Tables with columns like: Date, Description, Amount, Balance
✅ Transaction history, payment history, billing statements
✅ Multiple months/periods of data
✅ Historical usage or consumption data

NOT BILLING HISTORY:
❌ Login pages, home dashboards, account settings
❌ Single current bill only (no history)
❌ Navigation menus, help pages
❌ Loading pages or error pages

Respond with JSON only:
{{
    "is_billing_history_page": true/false,
    "confidence": 0-100,
    "evidence": ["list of specific evidence found"],
    "data_type": "transaction_history|billing_statements|usage_history|current_bill_only|non_billing",
    "extraction_potential": "high|medium|low",
    "reasoning": "detailed explanation"
}}
"""
            
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": analysis_prompt}],
                options={"temperature": 0.1}
            )
            
            detection_result = json.loads(response["message"]["content"])
            print(f"🎯 Billing history page: {detection_result.get('is_billing_history_page', False)}")
            print(f"🎯 Confidence: {detection_result.get('confidence', 0)}%")
            print(f"🎯 Data type: {detection_result.get('data_type', 'unknown')}")
            
            return detection_result
            
        except Exception as e:
            print(f"❌ Billing history detection failed: {e}")
            return {"is_billing_history_page": False, "confidence": 0, "error": str(e)}

    def ai_page_content_analysis(self, page_source: str) -> Dict:
        """AI analyzes current page content for billing indicators and relevance"""
        try:
            print("🔍 AI analyzing current page content for billing data...")
            
            # Extract key content for analysis
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Get text content and structural elements
            page_text = soup.get_text(separator=' ', strip=True)
            tables = soup.find_all('table')
            lists = soup.find_all(['ul', 'ol'])
            divs_with_data = soup.find_all('div', class_=re.compile(r'(data|info|content|history|transaction|billing)'))
            
            # Extract potential billing patterns
            # re module already imported at top of file
            
            # Currency patterns
            currency_matches = re.findall(r'\$\d+\.?\d*', page_text)
            
            # Date patterns  
            date_patterns = [
                r'\d{1,2}\/\d{1,2}\/\d{4}',  # MM/DD/YYYY
                r'\d{4}-\d{2}-\d{2}',        # YYYY-MM-DD
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}',  # Month DD, YYYY
                r'\d{1,2}\/\d{1,2}\/\d{2}',  # MM/DD/YY
            ]
            
            all_dates = []
            for pattern in date_patterns:
                dates = re.findall(pattern, page_text, re.IGNORECASE)
                all_dates.extend(dates)
            
            # Utility billing keywords (more specific)
            billing_keywords = [
                # Direct billing terms
                'payment', 'charge', 'bill', 'billing', 'invoice', 'statement', 'balance', 'due', 'amount',
                # Transaction terms
                'transaction', 'history', 'payment history', 'billing history', 'statement history',
                # Utility specific
                'usage', 'consumption', 'meter', 'reading', 'service', 'utility', 'energy', 'electric',
                # Time periods
                'previous', 'current', 'period', 'cycle', 'monthly', 'annual', 'recent',
                # Account terms
                'account', 'summary', 'overview', 'dashboard', 'my account'
            ]
            
            keyword_matches = []
            for keyword in billing_keywords:
                matches = len(re.findall(r'\b' + keyword + r'\b', page_text, re.IGNORECASE))
                if matches > 0:
                    keyword_matches.append({"keyword": keyword, "count": matches})
            
            # Structured data analysis
            table_analysis = []
            for i, table in enumerate(tables):
                rows = table.find_all('tr')
                cells = table.find_all(['td', 'th'])
                table_text = table.get_text(separator=' ', strip=True)
                
                has_currency = bool(re.search(r'\$\d+', table_text))
                has_dates = any(re.search(pattern, table_text, re.IGNORECASE) for pattern in date_patterns)
                
                table_analysis.append({
                    "index": i,
                    "rows": len(rows),
                    "cells": len(cells),
                    "has_currency": has_currency,
                    "has_dates": has_dates,
                    "relevance_score": (has_currency * 30) + (has_dates * 20) + len(rows) * 2
                })
            
            # Prepare analysis for AI
            content_summary = {
                "page_length": len(page_text),
                "currency_count": len(currency_matches),
                "currency_examples": currency_matches[:5],
                "date_count": len(all_dates),
                "date_examples": all_dates[:5],
                "billing_keywords": keyword_matches,
                "table_count": len(tables),
                "table_analysis": table_analysis,
                "list_count": len(lists),
                "structured_content_divs": len(divs_with_data),
                "page_text_sample": page_text[:500] + "..." if len(page_text) > 500 else page_text
            }
            
            print(f"🔍 Content analysis: {len(currency_matches)} currencies, {len(all_dates)} dates, {len(keyword_matches)} billing keywords, {len(tables)} tables")
            if keyword_matches:
                print(f"🔍 Top billing keywords found: {[k['keyword'] for k in keyword_matches[:5]]}")
            
            # AI Analysis Prompt
            analysis_prompt = f"""
            You are an expert at analyzing UTILITY COMPANY web pages to determine billing/transaction data relevance.
            
            CURRENT PAGE CONTENT ANALYSIS:
            {json.dumps(content_summary, indent=2)}
            
            TASK: Determine if this page contains useful UTILITY BILLING/TRANSACTION history data.
            
            EVALUATION CRITERIA FOR UTILITY BILLING PAGES:
            1. **Billing Data Presence**: Multiple billing amounts, dates, usage figures
            2. **Historical Data**: Previous months/periods with amounts and dates
            3. **Transaction Records**: Payment history, charge details, service periods
            4. **Usage Information**: Energy consumption, meter readings, usage patterns
            5. **Account Summary**: Current balance, due dates, service details
            
            TRANSACTION HISTORY PAGE INDICATORS (Score 90-100):
            - Tables with columns: Date, Description, Amount, Balance
            - Multiple transaction rows with dates and dollar amounts
            - Headers like "Transaction history", "Billing history", "Payment records"
            - Date ranges or filtering controls for historical data
            - Running balance or account activity displays
            
            UTILITY-SPECIFIC INDICATORS:
            - Currency amounts (especially multiple amounts suggesting history)
            - Date patterns (billing cycles, service periods, payment dates)
            - Utility terms: usage, consumption, meter, energy, service, account
            - Structured data: tables with billing/usage information
            - Time-based data: monthly, quarterly, annual summaries
            
            SCORING FOR UTILITY PAGES:
            - 90-100: Complete utility billing history (multiple periods + amounts + usage)
            - 70-89: Good billing/usage data (amounts + dates OR usage data)
            - 50-69: Some billing indicators (account info + some financial data)
            - 30-49: Utility page but minimal billing data (account overview only)
            - 0-29: No billing data (login page, home page, settings, etc.)
            
            CONSIDER:
            - Single Page Applications may load content dynamically
            - Some pages may be navigation/dashboard pages that lead to billing data
            - Look for both completed transactions AND account status information
            
            Respond with JSON only:
            {{
                "relevance_score": <0-100>,
                "has_billing_data": <true/false>,
                "data_completeness": <"complete"|"partial"|"minimal"|"none">,
                "missing_elements": ["dates", "amounts", "usage_data", "transaction_details", "historical_periods"],
                "best_data_location": {{"type": "table"|"list"|"div", "index": <number>}},
                "exploration_needed": <true/false>,
                "confidence": <0-100>,
                "page_type": "<billing_history|usage_data|account_overview|dashboard|navigation|other>",
                "reasoning": "<detailed explanation focusing on utility billing indicators>"
            }}
            """
            
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": analysis_prompt}],
                options={"temperature": 0.1}
            )
            
            ai_assessment = json.loads(response["message"]["content"])
            
            # Add raw data for debugging
            ai_assessment["raw_data"] = content_summary
            
            return ai_assessment
            
        except Exception as e:
            print(f"❌ Page content analysis failed: {e}")
            return {"relevance_score": 0, "has_billing_data": False, "exploration_needed": True, "error": str(e)}
    
    def ai_link_discovery_and_ranking(self, page_source: str, visited_urls: set) -> List[Dict]:
        """AI discovers and ranks all clickable links for billing potential"""
        try:
            print("🔗 AI discovering and ranking navigation links...")
            
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract all clickable elements more comprehensively
            clickable_elements = []
            
            # Find all potential clickable elements (enhanced for SPAs)
            links = soup.find_all('a', href=True)
            buttons_with_onclick = soup.find_all(['button', 'div', 'span'], onclick=True)
            ng_click_elements = soup.find_all(attrs={'ng-click': True})
            clickable_elements_soup = soup.find_all(attrs={'click': True})
            router_links = soup.find_all(attrs={'routerlink': True})
            
            # Additional SPA-specific selectors
            angular_ui_sref = soup.find_all(attrs={'ui-sref': True})  # Angular UI-Router
            vue_click = soup.find_all(attrs={'@click': True})  # Vue.js
            material_buttons = soup.find_all('button', class_=lambda x: x and 'mat-' in str(x))  # Angular Material
            nav_items = soup.find_all(['li', 'div', 'span'], class_=lambda x: x and any(nav in str(x).lower() for nav in ['nav', 'menu', 'sidebar', 'tab']))
            
            # Find elements that might be clickable based on classes/roles
            potential_clickable = soup.find_all(attrs={'role': lambda x: x and x.lower() in ['button', 'tab', 'menuitem', 'link']})
            
            all_soup_elements = (links + buttons_with_onclick + ng_click_elements + clickable_elements_soup + 
                               router_links + angular_ui_sref + vue_click + material_buttons + nav_items + potential_clickable)
            
            current_url = self.driver.current_url
            base_domain = '/'.join(current_url.split('/')[:3])
            
            print(f"🔍 Found {len(links)} href links, {len(buttons_with_onclick)} onclick elements, {len(ng_click_elements)} ng-click, {len(router_links)} router-links, {len(material_buttons)} material buttons, {len(nav_items)} nav items")
            
            for element in all_soup_elements:
                try:
                    full_url = None
                    navigation_type = "unknown"
                    is_sidebar_nav = False
                    
                    # Check if this is likely a sidebar/menu navigation item
                    parent = element.parent
                    while parent and parent.name != 'body':
                        parent_classes = parent.get('class', [])
                        parent_class_str = ' '.join(parent_classes).lower() if parent_classes else ''
                        if any(nav_indicator in parent_class_str for nav_indicator in 
                               ['sidebar', 'nav', 'menu', 'navigation', 'left-panel', 'side-panel']):
                            is_sidebar_nav = True
                            break
                        parent = parent.parent
                    
                    if element.name == 'a' and element.get('href'):
                        href = element.get('href', '')
                        navigation_type = "href"
                        if href.startswith('/'):
                            full_url = base_domain + href
                        elif href.startswith('#'):
                            # Handle Angular hash routing
                            full_url = base_domain + href
                            navigation_type = "hash"
                        elif href.startswith('javascript:'):
                            continue  # Skip javascript links
                        elif not href.startswith('http'):
                            full_url = base_domain + '/' + href
                        else:
                            full_url = href
                    
                    elif element.get('routerlink'):
                        # Angular router-link
                        router_link = element.get('routerlink', '')
                        navigation_type = "router"
                        if router_link.startswith('/'):
                            full_url = base_domain + '/ui' + router_link  # Common SPA pattern
                        else:
                            full_url = base_domain + '/ui/' + router_link
                    
                    elif element.get('ng-click'):
                        # Angular ng-click
                        ng_click = element.get('ng-click', '')
                        navigation_type = "ng-click"
                        # Try to extract navigation info from ng-click
                        if 'navigate' in ng_click or 'go' in ng_click or 'route' in ng_click:
                            # Try to extract path from ng-click
                            path_match = re.search(r'["\']([^"\']+)["\']', ng_click)
                            if path_match:
                                extracted_path = path_match.group(1)
                                if extracted_path.startswith('/'):
                                    full_url = base_domain + extracted_path
                                else:
                                    full_url = base_domain + '/' + extracted_path
                            else:
                                continue
                        else:
                            continue
                    
                    elif element.get('onclick'):
                        onclick = element.get('onclick', '')
                        navigation_type = "onclick"
                        if 'location' in onclick or 'href' in onclick or 'navigate' in onclick:
                            # Try to extract URL from onclick
                            url_match = re.search(r'["\']([^"\']+)["\']', onclick)
                            if url_match:
                                extracted_url = url_match.group(1)
                                if extracted_url.startswith('/'):
                                    full_url = base_domain + extracted_url
                                else:
                                    full_url = base_domain + '/' + extracted_url
                            else:
                                continue
                        else:
                            continue
                    
                    else:
                        continue
                    
                    if not full_url:
                        continue
                    
                    # Skip already visited URLs
                    if full_url in visited_urls:
                        continue
                    
                    # Skip external domains (basic check)
                    if base_domain not in full_url:
                        continue
                    
                    # Get element context
                    text = element.get_text(separator=' ', strip=True)
                    title = element.get('title', '')
                    aria_label = element.get('aria-label', '')
                    
                    # Get surrounding context (parent elements)
                    parent_text = ""
                    parent = element.parent
                    if parent:
                        parent_text = parent.get_text(separator=' ', strip=True)
                    
                    clickable_elements.append({
                        "url": full_url,
                        "text": text,
                        "title": title,
                        "aria_label": aria_label,
                        "parent_context": parent_text[:200],
                        "tag": element.name,
                        "classes": element.get('class', []),
                        "element_html": str(element)[:300],
                        "navigation_type": navigation_type,
                        "ng_click": element.get('ng-click', ''),
                        "router_link": element.get('routerlink', ''),
                        "onclick": element.get('onclick', ''),
                        "is_sidebar_nav": is_sidebar_nav
                    })
                    
                except Exception as e:
                    continue
            
            if not clickable_elements:
                print("🔗 No clickable elements found")
                return []
            
            # AI Ranking Prompt
            ranking_prompt = f"""
            You are an expert at analyzing UTILITY COMPANY websites to find billing/transaction history pages.
            
            DISCOVERED CLICKABLE ELEMENTS:
            {json.dumps(clickable_elements, indent=2)}
            
            TASK: Rank these navigation elements by likelihood of leading to UTILITY BILLING/TRANSACTION history data.
            
            PRIORITY RANKING CRITERIA:
            1. **TRANSACTION HISTORY PAGES** (Score 95-100):
               - "transaction history", "transactions", "transaction records"
               - "billing history", "bill history", "payment history"
               - "account history", "statement history", "transaction details"
               - URLs containing: "/transactions", "/history", "/billing-history"
               
            2. **DEDICATED BILLING SECTIONS** (Score 90-95):
               - "bills", "billing", "statements", "invoices"
               - "payment records", "payment details", "billing records"
               - "monthly statements", "account statements"
               - Navigation items specifically for billing data
               
            3. **UTILITY USAGE PAGES** (Score 80-90):
               - "usage", "usage history", "energy usage", "consumption"
               - "meter", "meter reading", "service history", "usage details"
               - "consumption history", "usage records"
               
            4. **ACCOUNT DETAIL PAGES** (Score 70-80):
               - "account detail", "account information", "account summary"
               - "manage accounts", "account overview", "service details"
               - Pages that might contain billing summaries
               
            5. **GENERAL NAVIGATION** (Score 40-60):
               - "dashboard", "overview", "home", "summary"
               - "balance", "due", "amount due", "charges"
               - "fees", "cost", "total"
            
            SPECIAL PATTERNS FOR UTILITY WEBSITES:
            - Angular routes like "/usage", "/billing", "/history"
            - Hash routes like "#/bills", "#/statements"
            - Navigation elements with utility-specific classes
            - Parent context mentioning utility services
            
            AVOID COMPLETELY (Score 0-20):
            - "help", "support", "contact", "faq"
            - "settings", "preferences", "profile", "password"
            - "news", "outages", "maps", "programs"
            - "logout", "sign out", "exit"
            
            ANALYSIS INSTRUCTIONS:
            - HIGHEST PRIORITY: Sidebar/menu navigation items with "is_sidebar_nav": true
            - PRIORITIZE links with text: "Transactions", "Transaction history", "Billing history"
            - URLs containing "/transactions", "/history", "/billing" get highest priority (95-100 score)
            - Sidebar navigation items get +20 bonus points over regular links
            - Consider text, aria_label, title, AND parent_context for transaction indicators
            - Navigation items in sidebars/menus are much more important than dashboard summaries
            - Consider navigation_type (router-link, ng-click may be SPA navigation)
            - Look for links that suggest dedicated data tables (not just summaries)
            - Exact text matches for "Transactions" should get 95-100 score if in sidebar
            
            Respond with JSON only:
            {{
                "ranked_links": [
                    {{
                        "url": "<full_url>",
                        "score": <0-100>,
                        "reasoning": "<specific terms found and why scored this way>",
                        "category": "<billing|usage|account|transaction|financial|other>",
                        "confidence": <0-100>,
                        "key_indicators": ["<list of key terms/patterns found>"]
                    }}
                ],
                "total_links_analyzed": <count>,
                "high_potential_count": <count of links with score >= 70>,
                "analysis_summary": "<brief summary of what types of navigation were found>"
            }}
            """
                
                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=[{"role": "user", "content": ranking_prompt}],
                options={"temperature": 0.1}
            )
            
            ai_response = response["message"]["content"]
            print(f"🤖 AI Response (first 500 chars): {ai_response[:500]}...")
            
            # Try to extract JSON from response (sometimes AI adds extra text)
            try:
                ranking_result = json.loads(ai_response)
            except json.JSONDecodeError:
                # Try to find JSON block in response
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if json_match:
                    ranking_result = json.loads(json_match.group())
                else:
                    print(f"❌ Could not parse AI response as JSON")
                    print(f"❌ Raw response: {ai_response[:1000]}")
                    return []
            
            # Sort by score (highest first)
            ranked_links = sorted(ranking_result.get("ranked_links", []), 
                                key=lambda x: x.get("score", 0), reverse=True)
            
            print(f"🔗 AI ranked {len(ranked_links)} links")
            if ranked_links:
                print(f"🏆 Top link: {ranked_links[0]['url']} (score: {ranked_links[0]['score']})")
                print(f"🧠 Reasoning: {ranked_links[0]['reasoning']}")
            
            return ranked_links
            
        except Exception as e:
            print(f"❌ Link discovery and ranking failed: {e}")
            return []
    
    def autonomous_billing_exploration(self) -> BillInfo:
        """Systematic billing exploration: Find ALL billing URLs → Rank → Explore systematically"""
        try:
            import time
            start_time = time.time()
            max_exploration_time = 180  # 3 minutes max exploration
            
            print("🧭 Starting systematic billing exploration...")
            print("📋 Phase 1: Discovering ALL billing-related URLs...")
            print(f"⏰ Max exploration time: {max_exploration_time//60} minutes")
            
            # Phase 1: Discover and collect ALL billing-related URLs from current page
            current_url = self.driver.current_url
            page_source = self.driver.page_source
            
            print(f"🔍 Analyzing initial page: {current_url}")
            
            # Wait for SPA content to load
            self.wait_for_spa_content()
            page_source = self.driver.page_source
            
            # Discover ALL billing-related links from the current page
            all_billing_links = self.ai_link_discovery_and_ranking(page_source, set())
            
            if not all_billing_links:
                print("⚠️ No billing-related links found on initial page")
                # Try current page extraction as fallback
                    return self.extract_from_current_page_only()
            
            print(f"📊 Found {len(all_billing_links)} potential billing URLs")
            print("📋 Phase 2: Ranking URLs by billing relevance...")
            
            # Phase 2: Rank ALL discovered URLs by billing relevance  
            ranked_urls = self.rank_billing_urls_comprehensively(all_billing_links)
            
            print(f"🎯 Top 5 ranked billing URLs:")
            for i, url_info in enumerate(ranked_urls[:5]):
                print(f"   {i+1}. {url_info['url']} (score: {url_info['score']}/100)")
            
            print("📋 Phase 3: Systematically exploring each URL...")
            
            # Phase 3: Systematically explore each URL in ranked order
            best_billing_data = BillInfo("No data found", 0.0, "No data found", 0.0)
            visited_urls = {current_url}
            
            for i, url_info in enumerate(ranked_urls):
                # Check timeout
                elapsed_time = time.time() - start_time
                if elapsed_time > max_exploration_time:
                    print(f"⏰ Exploration timeout reached ({elapsed_time:.1f}s)")
                    break
                
                target_url = url_info['url']
                expected_content = url_info.get('expected_content', 'billing data')
                
                if target_url in visited_urls:
                    print(f"⏭️ Already visited {target_url}")
                    continue
                
                print(f"\n🎯 Exploring URL {i+1}/{len(ranked_urls)}: {target_url}")
                print(f"📝 Expected: {expected_content}")
                print(f"⏱️  Time elapsed: {elapsed_time:.1f}s / {max_exploration_time}s")
                
                # Navigate to the billing URL
                try:
                    self.driver.get(target_url)
                    self.wait_for_spa_content()
                    visited_urls.add(target_url)
                    page_source = self.driver.page_source
                    
                    # AI detection: Is this a billing history page?
                    billing_detection = self.ai_detect_billing_history_page(page_source)
                    is_billing_page = billing_detection.get('is_billing_history_page', False)
                    confidence = billing_detection.get('confidence', 0)
                    
                    print(f"🤖 Billing history page: {is_billing_page} (confidence: {confidence}%)")
                    
                    # Extract data using smart extraction
                    billing_data = self.smart_billing_extraction(page_source, is_billing_page=is_billing_page)
                    
                    # Check if we found comprehensive data
                    if self.has_meaningful_billing_data(billing_data):
                        if hasattr(billing_data, 'all_bills') and billing_data.all_bills:
                            print(f"🎉 Found comprehensive billing history! {len(billing_data.all_bills)} records")
                            return billing_data
                        elif is_billing_page and confidence > 80:
                            print(f"🎉 Found good billing data on high-confidence page!")
                                best_billing_data = billing_data
                            # Continue exploring to see if we find even better data
                        elif billing_data.current_amount > best_billing_data.current_amount:
                            print(f"🏆 Found better billing data: ${billing_data.current_amount}")
                            best_billing_data = billing_data
                    
                except Exception as e:
                    print(f"❌ Error exploring {target_url}: {e}")
                    continue
            
            print(f"\n🏁 Exploration complete. Returning best data found.")
            return best_billing_data if self.has_meaningful_billing_data(best_billing_data) else BillInfo("No billing data found", 0.0, "No billing data found", 0.0)
        
        except Exception as e:
            print(f"❌ Systematic exploration error: {e}")
            return BillInfo("Exploration error", 0.0, "Exploration error", 0.0)
        finally:
            print("🔄 Exploration complete")

    def wait_for_spa_content(self):
        """Wait for SPA/Angular content to load"""
        try:
            print("⏳ Waiting for SPA content to load...")
            # Wait for loading indicators to disappear
            try:
                WebDriverWait(self.driver, 5).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".loading, .spinner, mat-spinner, .mat-progress-spinner, .loading-overlay"))
                )
            except:
                pass
            
            # Wait for content to render
            for i in range(3):  # Reduced attempts
                time.sleep(1.5)
                try:
                    content_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                        "mat-card, .mat-card, [role='main'], main, .content, nav, table")
                    if len(content_elements) > 2:
                        print(f"✅ SPA content loaded ({len(content_elements)} elements)")
                        return
                except:
                    pass
                if i < 2:
                    print(f"⏳ Waiting for content... (attempt {i+1}/3)")
        except Exception as e:
            print(f"⚠️ SPA content wait error: {e}")

    def extract_from_current_page_only(self) -> BillInfo:
        """Fallback: extract from current page only when no links found"""
        try:
            print("🔍 Fallback: Extracting from current page only...")
            page_source = self.driver.page_source
            billing_detection = self.ai_detect_billing_history_page(page_source)
            is_billing_page = billing_detection.get('is_billing_history_page', False)
            
            return self.smart_billing_extraction(page_source, is_billing_page=is_billing_page)
        except Exception as e:
            print(f"❌ Current page extraction error: {e}")
            return BillInfo("Current page extraction failed", 0.0, "Current page extraction failed", 0.0)

    def rank_billing_urls_comprehensively(self, all_links: List[Dict]) -> List[Dict]:
        """Rank ALL discovered URLs by billing relevance"""
        try:
            print("🧠 AI ranking ALL URLs by billing relevance...")
            
            # Prepare links for AI ranking
            links_summary = []
            for i, link in enumerate(all_links[:10]):  # Limit for AI processing
                links_summary.append({
                    "index": i,
                    "url": link.get('href', ''),
                    "text": link.get('text', ''),
                    "context": link.get('context', ''),
                    "billing_score": link.get('billing_score', 0)
                })
            
            ranking_prompt = f"""
You are an expert at identifying UTILITY BILLING HISTORY pages. Rank these URLs by their likelihood of containing comprehensive billing/transaction history.

DISCOVERED URLS:
{json.dumps(links_summary, indent=2)}

TASK: Rank these URLs by billing relevance (highest to lowest).

HIGH PRIORITY (90-100 points):
- "billing history", "transaction history", "payment history" 
- "statements", "bills", "invoices"
- URLs with "history", "transactions", "billing" in path

MEDIUM PRIORITY (70-89 points):
- "account", "usage", "my account"
- "dashboard" with billing context
- Previous/recent bills

LOW PRIORITY (50-69 points):
- Generic "home", "overview"
- Settings, profile, help pages

Respond with JSON only:
{{
    "ranked_urls": [
        {{
            "url": "full_url",
            "score": 0-100,
            "expected_content": "what you expect to find",
            "reasoning": "why this score"
        }}
    ]
}}
"""
            
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": ranking_prompt}],
                options={"temperature": 0.1}
            )
            
            ranking_result = json.loads(response["message"]["content"])
            ranked_urls = ranking_result.get('ranked_urls', [])
            
            print(f"🎯 AI ranked {len(ranked_urls)} URLs")
            return ranked_urls
            
        except Exception as e:
            print(f"❌ URL ranking error: {e}")
            # Fallback: simple scoring based on keywords
            simple_ranked = []
            for link in all_links:
                url = link.get('href', '')
                text = link.get('text', '').lower()
                score = 50  # Base score
                
                if any(word in url.lower() for word in ['billing', 'history', 'transaction', 'statement']):
                    score += 40
                if any(word in text for word in ['billing', 'history', 'transaction', 'statement']):
                    score += 30
                if any(word in text for word in ['account', 'usage', 'dashboard']):
                    score += 20
                    
                simple_ranked.append({
                    'url': url,
                    'score': min(score, 100),
                    'expected_content': 'billing data',
                    'reasoning': 'simple keyword matching'
                })
            
            return sorted(simple_ranked, key=lambda x: x['score'], reverse=True)

    def intelligent_post_login_exploration(self) -> BillInfo:
        """Intelligently explore the site after login to find billing information"""
                # Enhanced wait for SPA content loading
                print("⏳ Waiting for SPA dynamic content...")
                
                # Wait for loading indicators to disappear
                try:
                    WebDriverWait(self.driver, 8).until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".loading, .spinner, mat-spinner, .mat-progress-spinner, .loading-overlay"))
                    )
                except:
                    pass  # Continue if no loading indicators
                
                # Wait for Angular/SPA to fully render content
                print("⏳ Waiting for Angular/SPA content to render...")
                content_detected = False
                
                for i in range(4):  # Reduced from 8 to 4 attempts for speed
                    time.sleep(1.5)  # Reduced from 3 to 1.5 seconds per attempt
                    
                    # Check for actual billing content (not just page structure)
                    try:
                        # Look for billing-specific content
                        billing_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                            "table, .billing, .bill, .amount, .balance, .due, .payment, .transaction, .statement")
                        
                        # Look for any substantial content (not just page title)
                        content_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                            "mat-card, .mat-card, [role='main'], main, .content, .page-content, nav, .navigation, .sidebar, .menu")
                        
                        # Check if page has loaded beyond just the title
                        page_text = self.driver.page_source
                        word_count = len(page_text.split())
                        
                        if billing_elements or len(content_elements) > 5 or word_count > 100:
                            print(f"✅ SPA content detected ({len(content_elements)} elements, {len(billing_elements)} billing elements, {word_count} words)")
                            content_detected = True
                            break
                    except:
                        pass
                    
                    if i < 3:  # Don't print on last iteration  
                        print(f"⏳ SPA content not ready, waiting... (attempt {i+1}/4)")
                
                if not content_detected:
                    print("⚠️ SPA content may not be fully loaded, but proceeding...")
                
                time.sleep(3)  # Final buffer for content rendering
                
                # Get current page content
                page_source = self.driver.page_source
                

                
                # AI Content Analysis
                content_analysis = self.ai_page_content_analysis(page_source)
                relevance_score = content_analysis.get("relevance_score", 0)
                has_billing_data = content_analysis.get("has_billing_data", False)
                
                print(f"🤖 Page relevance score: {relevance_score}/100")
                print(f"🤖 Has billing data: {has_billing_data}")
                print(f"🧠 AI assessment: {content_analysis.get('reasoning', 'No reasoning')}")
                
                # Smart billing detection and extraction
                billing_detection = self.ai_detect_billing_history_page(page_source)
                is_billing_history_page = billing_detection.get('is_billing_history_page', False)
                confidence = billing_detection.get('confidence', 0)
                
                print(f"💰 Extracting billing data from current page...")
                print(f"📄 Billing history page: {is_billing_history_page} (confidence: {confidence}%)")
                
                current_billing_data = self.smart_billing_extraction(page_source, is_billing_page=is_billing_history_page)
                
                # Check if we found meaningful billing data
                if self.has_meaningful_billing_data(current_billing_data):
                    # If it's comprehensive historical data, we're done!
                    if hasattr(current_billing_data, 'all_bills') and current_billing_data.all_bills:
                        print(f"🎉 Found comprehensive transaction history! {len(current_billing_data.all_bills)} bills")
                        print("🏁 Stopping exploration - comprehensive data found!")
                        return current_billing_data
                    # If it's good billing data on a billing history page, also stop
                    elif is_billing_history_page and confidence > 70:
                        print(f"🎉 Found good billing data on high-confidence billing page!")
                        print("🏁 Stopping exploration - billing data found!")
                        return current_billing_data
                
                # Otherwise, update best data for fallback if it's better
                if (current_billing_data.current_amount > best_billing_data.current_amount):
                    best_billing_data = current_billing_data
                    print(f"🏆 New best billing data found! Current: ${current_billing_data.current_amount}")
                
                # Special case: If we're on a home page with some billing data, don't navigate away immediately
                if ('home' in current_url.lower() and self.has_meaningful_billing_data(current_billing_data)):
                    print("🏠 Found billing data on home page - this might be the main billing dashboard")
                    if len(exploration_results) == 0:  # First page analyzed
                        print("🔍 Giving home page more time to load additional content...")
                        time.sleep(5)  # Extra time for AJAX content
                        
                        # Try extraction again after extra wait (retry as non-billing page to avoid vision AI)
                        page_source = self.driver.page_source
                        retry_billing_data = self.smart_billing_extraction(page_source, is_billing_page=False)
                        if self.has_meaningful_billing_data(retry_billing_data):
                            print(f"🎉 Found better data on retry!")
                            if hasattr(retry_billing_data, 'all_bills') and retry_billing_data.all_bills:
                                print(f"📊 Comprehensive data: {len(retry_billing_data.all_bills)} bills")
                                return retry_billing_data
                            elif retry_billing_data.current_amount > current_billing_data.current_amount:
                                best_billing_data = retry_billing_data
                
                # Store exploration result
                exploration_results.append({
                    "url": current_url,
                    "relevance_score": relevance_score,
                    "has_billing_data": has_billing_data,
                    "extracted_amount": best_billing_data.current_amount if has_billing_data else 0
                })
                
                # Check if we found a transaction history page (higher threshold)
                page_type = content_analysis.get("page_type", "")
                if (page_type in ["billing_history", "usage_data"] and 
                    relevance_score >= 70 and
                    hasattr(current_billing_data, 'all_bills') and 
                    len(getattr(current_billing_data, 'all_bills', [])) >= 3):
                    print("🎉 Found comprehensive transaction history page! Exploration complete.")
                    break
                
                # Continue exploration if we haven't found a dedicated history page
                exploration_needed = content_analysis.get("exploration_needed", True)
                if not exploration_needed and relevance_score >= 80:
                    print("✅ AI determined this page has sufficient data, stopping exploration")
                    break
                
                # AI Link Discovery and Ranking
                ranked_links = self.ai_link_discovery_and_ranking(page_source, visited_urls)
                
                # Navigate to next best link
                if ranked_links:
                    navigated = False
                    
                    # Try top 3 links in case the highest scored one fails
                    for i, next_link in enumerate(ranked_links[:3]):
                        next_url = next_link["url"]
                        
                        print(f"🔗 Trying link #{i+1} (score: {next_link['score']}/100):")
                        print(f"   URL: {next_url}")
                        print(f"   Category: {next_link.get('category', 'unknown')}")
                        print(f"   Key indicators: {next_link.get('key_indicators', [])}")
                        
                        try:
                            # Try direct navigation first
                            self.driver.get(next_url)
                            self.human_like_delay(2.0, 4.0)  # Human-like delay
                            
                            # Verify we actually navigated somewhere new
                            new_current_url = self.driver.current_url
                            if new_current_url != current_url:
                                navigated = True
                                print(f"✅ Successfully navigated to: {new_current_url}")
                                break
                            else:
                                print(f"⚠️ URL didn't change, trying next link...")
                                continue
                                
                        except Exception as e:
                            print(f"⚠️ Failed to navigate to {next_url}: {e}")
                            
                            # Try clicking instead of direct navigation for SPA apps
                            try:
                                # Look for clickable element with matching text or href
                                clickable_selectors = [
                                    f"a[href*='{next_url.split('/')[-1]}']",
                                    f"*[ng-click*='{next_url.split('/')[-1]}']",
                                    f"*[routerlink*='{next_url.split('/')[-1]}']"
                                ]
                                
                                for selector in clickable_selectors:
                                    try:
                                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                        element.click()
                                        self.human_like_delay(2.0, 4.0)
                                        
                                        new_current_url = self.driver.current_url
                                        if new_current_url != current_url:
                                            navigated = True
                                            print(f"✅ Successfully clicked to navigate: {new_current_url}")
                                            break
                                    except:
                                        continue
                                        
                                if navigated:
                                    break
                                    
                            except Exception as click_error:
                                print(f"⚠️ Click navigation also failed: {click_error}")
                                continue
                    
                    if not navigated:
                        print("❌ Failed to navigate to any ranked links")
                        
                else:
                    print("🔗 No ranked links found, trying common utility paths...")
                    
                    # Try common utility company navigation patterns as fallback
                    base_url = '/'.join(current_url.split('/')[:3])
                    
                    # Comprehensive utility billing patterns - PRIORITIZE TRANSACTION HISTORY
                    common_utility_paths = [
                        # HIGHEST PRIORITY: Transaction history pages
                        "/ui/#/transactions",
                        "/ui/#/transaction-history", 
                        "/ui/#/billing-history",
                        "/ui/#/payment-history",
                        "/ui/#/account-history",
                        "/ui/#/usage-history",
                        "/ui/transactions",
                        "/ui/transaction-history",
                        "/ui/billing-history", 
                        "/ui/payment-history",
                        "/transactions",
                        "/transaction-history",
                        "/billing-history",
                        "/#transactions",
                        "/#transaction-history",
                        "/#billing-history",
                        
                        # Platform-specific patterns (SmartHub, etc.)
                        "/ui/#/account/usage",
                        "/ui/#/account/billing", 
                        "/ui/#/account/history",
                        "/ui/#/account/transactions",
                        "/ui/#/my-account/usage",
                        "/ui/#/my-account/billing",
                        "/ui/#/my-account/history",
                        "/account/usage",
                        "/account/billing",
                        "/account/history",
                        "/my-account/usage",
                        "/my-account/billing", 
                        "/my-account/history",
                        
                        # MEDIUM PRIORITY: Billing sections
                        "/ui/#/bills",
                        "/ui/#/billing",
                        "/ui/#/statements", 
                        "/ui/#/bill-history",
                        "/ui/#/statement-history",
                        "/ui/#/invoice-history",
                        "/ui/bills",
                        "/ui/billing",
                        "/ui/statements",
                        "/bills",
                        "/billing", 
                        "/statements",
                        "/#bills",
                        "/#billing",
                        
                        # LOWER PRIORITY: Usage and general
                        "/ui/#/usage",
                        "/ui/#/consumption",
                        "/ui/#/account",
                        "/ui/#/history", 
                        "/ui/#/dashboard",
                        "/ui/#/home/billing",
                        "/ui/#/home/usage",
                        "/ui/usage",
                        "/ui/history",
                        "/usage",
                        "/history",
                        "/#usage",
                        "/#history",
                        "/#account",
                        "/#dashboard"
                    ]
                    
                    tried_fallback = False
                    successful_fallback = False
                    redirect_count = 0
                    max_redirects = 5  # Limit redirect attempts
                    
                    for path in common_utility_paths:
                        if redirect_count >= max_redirects:
                            print(f"🔄 Hit redirect limit ({max_redirects}), stopping navigation attempts")
                            break
                            
                        fallback_url = base_url + path
                        if fallback_url not in visited_urls:
                            print(f"🔗 Trying common utility pattern: {fallback_url}")
                            try:
                                self.driver.get(fallback_url)
                                self.human_like_delay(3.0, 5.0)  # More time for SPA loading
                                tried_fallback = True
                                
                                # Check if we successfully navigated to a different page
                                new_url = self.driver.current_url
                                if new_url != current_url and new_url not in visited_urls:
                                    print(f"✅ Successfully navigated to: {new_url}")
                                    successful_fallback = True
                                    break
                                else:
                                    print(f"🔄 Redirected back to same/visited page: {new_url}")
                                    visited_urls.add(fallback_url)  # Mark as visited to avoid retrying
                                    redirect_count += 1
                                    
                                    # If we keep getting redirected to home with billing data, stop trying
                                    if redirect_count >= 3 and best_billing_data.current_amount > 0:
                                        print("🏠 Multiple redirects to home page with billing data - using current data")
                                        successful_fallback = False
                                        break
                                    continue
                                    
                            except Exception as e:
                                print(f"⚠️ Fallback failed: {e}")
                                visited_urls.add(fallback_url)  # Mark as visited
                                continue
                    
                    if not tried_fallback:
                        print("🔗 No more unvisited fallback paths available")
                        break
                    elif not successful_fallback:
                        if redirect_count > 0:
                            print("🔄 Multiple redirects detected - likely home page contains all data")
                        else:
                            print("🔗 All fallback paths redirected back to visited pages")
                        break
            
            # Final results summary
            print(f"\n🏁 Exploration complete! Visited {pages_explored} pages:")
            for i, result in enumerate(exploration_results):
                print(f"   {i+1}. {result['url']} (score: {result['relevance_score']}/100)")
            
            if best_billing_data.current_amount > 0:
                print(f"🎯 Best billing data found: Current: ${best_billing_data.current_amount}, Previous: ${best_billing_data.previous_amount}")
            else:
                print("❌ No billing data found during exploration")
            
            return best_billing_data
            
        except Exception as e:
            print(f"❌ Autonomous exploration failed: {e}")
            return BillInfo("Exploration failed", 0.0, "Exploration failed", 0.0)

    def intelligent_post_login_exploration(self) -> BillInfo:
        """Intelligently explore the site after login to find billing information"""
        try:
            print("🧭 Starting intelligent post-login exploration...")
            
            current_url = self.driver.current_url
            print(f"📍 Current location: {current_url}")
            
            # Check for registration/account setup redirect
            if "registration" in current_url.lower() or "register" in current_url.lower():
                print("⚠️ DETECTED: Redirected to account registration/setup page")
                print("💡 This means login worked, but your account needs to be linked to your utility account")
                print("🔧 Manual action required: Complete account setup at CoServ SmartHub first")
                return BillInfo("Account setup required", 0.0, "Login works, but account needs linking", 0.0)
            
            # Check page content for registration indicators (but ignore normal login page links)
            page_source = self.driver.page_source.lower()
            
            # Only flag as registration needed if we're actually on a registration page
            # or if there are clear registration forms (not just links)
            if "login" in current_url.lower():
                print("🔍 Still on login page - checking if login actually worked...")
                # If we're still on login page, the login probably failed
                # Let's check for error messages or try to navigate away
                pass  # Continue with normal exploration
            else:
                # Check for actual registration forms/requirements (not just links)
                registration_form_indicators = [
                    "complete your registration", "link your utility account",
                    "account setup required", "finish account setup"
                ]
                
                if any(indicator in page_source for indicator in registration_form_indicators):
                    print("⚠️ DETECTED: Account setup required")
                    print("💡 Your login credentials work, but account setup is needed")
                    
                    # Save the page for user inspection
                    with open("registration_redirect_page.html", 'w', encoding='utf-8') as f:
                        f.write(self.driver.page_source)
                    print("📁 Saved page content to: registration_redirect_page.html")
                    
                    return BillInfo("Account setup required", 0.0, "Complete account setup", 0.0)
            
            # 🚀 NEW: Use Autonomous AI Billing Exploration System
            print("🤖 Activating autonomous AI billing exploration system...")
            billing_data = self.autonomous_billing_exploration()
            
            return billing_data
                
        except Exception as e:
            print(f"❌ Error during post-login exploration: {e}")
            return BillInfo("Exploration error", 0.0, "Exploration error", 0.0)
    
    def find_billing_navigation_links(self) -> List[Dict]:
        """Find navigation links that might lead to billing information"""
        try:
            billing_links = []
            
            # Get all links on the page
            links = self.driver.find_elements(By.TAG_NAME, "a")
            
            # Keywords that suggest billing-related content
            billing_keywords = [
                'bill', 'billing', 'account', 'statement', 'usage', 'payment', 
                'history', 'transaction', 'charges', 'balance', 'invoice',
                'summary', 'detail', 'manage', 'view', 'my account', 'dashboard'
            ]
            
            for link in links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip().lower()
                    
                    if not href or not text:
                        continue
                        
                    # Calculate relevance score
                    relevance = 0
                    for keyword in billing_keywords:
                        if keyword in text:
                            relevance += 2
                        if keyword in href.lower():
                            relevance += 1
                    
                    # Boost score for high-priority terms
                    high_priority = ['billing', 'account', 'statement', 'usage', 'bill']
                    for priority_term in high_priority:
                        if priority_term in text:
                            relevance += 3
                    
                    if relevance >= 2:  # Only include relevant links
                        billing_links.append({
                            "url": href,
                            "text": text[:50],  # Truncate for display
                            "relevance": relevance
                        })
                        
                except Exception as e:
                    continue
            
            # Also check for buttons with onclick navigation
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                try:
                    text = button.text.strip().lower()
                    onclick = button.get_attribute('onclick') or ''
                    
                    if not text:
                        continue
                        
                    relevance = 0
                    for keyword in billing_keywords:
                        if keyword in text:
                            relevance += 2
                            
                    if relevance >= 3:  # Higher threshold for buttons
                        # Try to extract URL from onclick if present
                        url_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                        if url_match:
                            button_url = url_match.group(1)
                            if not button_url.startswith('http'):
                                current_url = self.driver.current_url
                                base_url = '/'.join(current_url.split('/')[:3])
                                button_url = base_url + button_url if button_url.startswith('/') else base_url + '/' + button_url
                            
                            billing_links.append({
                                "url": button_url,
                                "text": f"Button: {text[:30]}",
                                "relevance": relevance
                            })
                        else:
                            # For buttons without clear URLs, we could try clicking them
                            # but that's more complex, so skip for now
                            pass
                            
                except Exception as e:
                    continue
            
            print(f"🔗 Found {len(billing_links)} potentially relevant navigation links")
            for link in billing_links[:5]:  # Show top 5
                print(f"   • {link['text']} (relevance: {link['relevance']})")
            
            return billing_links
            
        except Exception as e:
            print(f"❌ Error finding navigation links: {e}")
            return []

def display_billing_table(bill_info: BillInfo):
    """Display comprehensive billing history in a nice table format"""
    
    # Check if we have comprehensive historical data
    if hasattr(bill_info, 'all_bills') and bill_info.all_bills:
        print("\n" + "="*50)
        print("💡 UTILITY BILLING HISTORY")
        print("="*50)
        print(f"📊 Found {len(bill_info.all_bills)} billing records")
        print("="*50)
        
        # Prepare clean historical data table
        historical_data = []
        total_amount = 0.0
        
        for i, bill in enumerate(bill_info.all_bills):
            # Format date consistently
            date_str = bill['date'].strftime('%m/%d/%Y')
            amount = bill['amount']
            total_amount += amount
            
            # Simple row with just Date and Amount
            historical_data.append([
                date_str,
                f"${amount:.2f}"
            ])
        
        # Display clean table
        print(tabulate(
            historical_data, 
            headers=["Date", "Amount"], 
            tablefmt="grid"
        ))
        
        # Clean summary statistics
        print("\n" + "="*50)
        print("📊 BILLING SUMMARY")
        print("="*50)
        
        summary_data = []
        
        # Basic statistics
        avg_amount = total_amount / len(bill_info.all_bills) if bill_info.all_bills else 0
        min_amount = min(bill['amount'] for bill in bill_info.all_bills) if bill_info.all_bills else 0
        max_amount = max(bill['amount'] for bill in bill_info.all_bills) if bill_info.all_bills else 0
        
        # Calculate date range
        if bill_info.all_bills:
            earliest_date = min(bill['date'] for bill in bill_info.all_bills)
            latest_date = max(bill['date'] for bill in bill_info.all_bills)
            date_range = f"{earliest_date.strftime('%m/%d/%Y')} to {latest_date.strftime('%m/%d/%Y')}"
        else:
            date_range = "No data"
        
        # Show up to 6 months of billing data with actual dates
        months_to_show = min(6, len(bill_info.all_bills))
        if months_to_show >= 1:
            summary_data.append(["📅 Recent Bills", "", ""])
            
            for i in range(months_to_show):
                bill = bill_info.all_bills[i]
                date_str = bill['date'].strftime('%m/%d/%Y')
                amount = bill['amount']
                
                # Calculate trend vs previous month
                trend = ""
                if i > 0:
                    prev_amount = bill_info.all_bills[i-1]['amount']
                    if amount > prev_amount:
                        trend = "↑"
                    elif amount < prev_amount:
                        trend = "↓"
                    else:
                        trend = "→"
                
                summary_data.append([date_str, f"${amount:.2f}", trend])
            
            summary_data.append(["", "", ""])
        
        summary_data.extend([
            ["Total Bills Found", str(len(bill_info.all_bills)), ""],
            ["Date Range", date_range, ""],
            ["Average Amount", f"${avg_amount:.2f}", ""],
            ["Lowest Amount", f"${min_amount:.2f}", ""],
            ["Highest Amount", f"${max_amount:.2f}", ""]
        ])
        
        print(tabulate(summary_data, headers=["Metric", "Value", "Trend"], tablefmt="grid"))
        
    else:
        # Fallback to simple display if no comprehensive data
        print("\n" + "="*50)
        print("💡 UTILITY BILL SUMMARY")
        print("="*50)
        
        data = [
            [bill_info.previous_month, f"${bill_info.previous_amount:.2f}"],
            [bill_info.current_month, f"${bill_info.current_amount:.2f}"],
            ["Difference", f"${bill_info.current_amount - bill_info.previous_amount:.2f}"]
        ]
        
        print(tabulate(data, headers=["Date", "Amount"], tablefmt="grid"))
        
        # Show additional info if available
        if bill_info.account_number and bill_info.account_number != "Unknown":
            print(f"\n📧 Account Number: {bill_info.account_number}")
        
        if bill_info.due_date:
            print(f"📅 Due Date: {bill_info.due_date}")
    
    print("="*50)

def main():
    """Simple main function that asks for URL, username, and password"""
    print("🏠 AutoBilling - Universal AI-Powered Utility Bill Scraper")
    print("🤖 Works with ANY utility website automatically!")
    print("=" * 60)
    
    try:
        # Simple input prompts
        url = input("🌐 Enter utility website URL: ").strip()
        username = input("👤 Enter username/email: ").strip()
        password = input("🔒 Enter password: ").strip()
        
        if not all([url, username, password]):
            print("❌ All fields are required!")
            return
        
        print("\n🧠 Starting AI analysis...")
        print("✨ The AI will automatically:")
        print("   • Find and fill login forms")
        print("   • Navigate and intelligently detect billing history pages")  
        print("   • Try HTML extraction first on each page")
        print("   • Use Vision AI only when HTML fails on confirmed billing pages")
        print("   • Extract ALL historical transaction data")
        print("   • Sort by date (newest first) for accuracy")
        print("   • Display comprehensive billing history table")
        
        # Create scraper and run
        scraper = UtilityBillScraper()
        bill_info = scraper.scrape_utility_bill(url, username, password)
        
        # Display results
        display_billing_table(bill_info)
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please ensure Ollama is running and qwen2.5:latest model is available")
        print("Run: ollama pull qwen2.5:latest")
        print("For faster vision AI fallback: ollama pull qwen2.5vl:7b")
        if not VISION_AI_AVAILABLE:
            print("For vision AI support: pip install Pillow")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    main() 