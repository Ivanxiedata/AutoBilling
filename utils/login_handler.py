#!/usr/bin/env python3
"""
Login handling for AutoBilling
Detects and fills login forms using AI and fallback methods
"""

import time
import json
import re
from typing import Dict, List, Optional

import ollama
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

from .config import OLLAMA_MODEL, LOGIN_WAIT_TIME, MAX_HTML_LENGTH, DEBUG_MODE
from .utils import human_like_delay, human_like_typing, generate_reliable_selector, is_element_visible_and_enabled
from .prompts import PromptLibrary

class LoginHandler:
    """Handles login form detection and authentication"""
    
    def __init__(self, driver):
        self.driver = driver
    
    def find_and_fill_login(self, html_content: str, username: str, password: str) -> bool:
        """Main method to find login form and perform login"""
        print("🔍 Analyzing page for login elements...")
        
        # Debug: Show what input elements exist on the page
        if DEBUG_MODE:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                inputs = soup.find_all('input')
                print(f"   • Found {len(inputs)} input elements on page")
                
                for i, inp in enumerate(inputs[:5]):  # Show first 5 inputs
                    inp_type = inp.get('type', 'text')
                    inp_name = inp.get('name', 'no-name')
                    inp_id = inp.get('id', 'no-id')
                    inp_placeholder = inp.get('placeholder', '')
                    print(f"     {i+1}. type='{inp_type}' name='{inp_name}' id='{inp_id}' placeholder='{inp_placeholder}'")
                
                buttons = soup.find_all('button')
                print(f"   • Found {len(buttons)} button elements")
                
                for i, btn in enumerate(buttons[:3]):  # Show first 3 buttons
                    btn_text = btn.get_text(strip=True)
                    btn_type = btn.get('type', 'button')
                    print(f"     {i+1}. type='{btn_type}' text='{btn_text}'")
                
                # Look for login triggers (links/buttons that might show login form)
                login_triggers = []
                
                # Check for links with login-related text
                links = soup.find_all('a')
                for link in links:
                    link_text = link.get_text(strip=True).lower()
                    if any(trigger in link_text for trigger in ['login', 'sign in', 'log in', 'sign on']):
                        href = link.get('href', '#')
                        login_triggers.append(f"Link: '{link.get_text(strip=True)}' → {href}")
                
                # Check for buttons with login-related text
                for btn in buttons:
                    btn_text = btn.get_text(strip=True).lower()
                    if any(trigger in btn_text for trigger in ['login', 'sign in', 'log in', 'sign on']):
                        login_triggers.append(f"Button: '{btn.get_text(strip=True)}'")
                
                # Check for iframes that might contain login forms
                iframes = soup.find_all('iframe')
                if iframes:
                    print(f"   • Found {len(iframes)} iframes (might contain login forms)")
                    for i, iframe in enumerate(iframes[:3]):
                        src = iframe.get('src', 'no-src')
                        print(f"     {i+1}. iframe src='{src}'")
                
                if login_triggers:
                    print(f"   • Found {len(login_triggers)} potential login triggers:")
                    for trigger in login_triggers[:5]:
                        print(f"     • {trigger}")
                else:
                    print("   • No obvious login triggers found")
                    
            except Exception as e:
                print(f"   • Debug element scan failed: {e}")
        
        # Primary: AI-based detection
        ai_result = self._ai_login_detection(html_content)
        
        if ai_result.get("found") and self._verify_selectors(ai_result):
            print(f"✅ AI detected login form (confidence: {ai_result.get('confidence', 0)}%)")
            login_data = ai_result
        else:
            if ai_result.get("error"):
                print(f"❌ AI detection failed: {ai_result['error']}")
            else:
                print("❌ AI detection failed or selectors invalid")
            
            # Fallback: HTML-based detection
            print("🔄 Using fallback login detection...")
            login_data = self._fallback_login_detection(html_content)
        
        if login_data.get("found"):
            print("🔐 Login form found, attempting to login...")
            return self._perform_login(username, password, login_data)
        else:
            print("❌ Login form not found")
            return False
    
    def _ai_login_detection(self, html_content: str) -> Dict:
        """Use AI to detect login form elements"""
        try:
            print("🧠 Using AI for login detection...")
            
            truncated_html = html_content[:MAX_HTML_LENGTH] if len(html_content) > MAX_HTML_LENGTH else html_content
            
            prompt = PromptLibrary.get_prompt('login_form_detection', html_content=truncated_html)
            
            try:
                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    options={
                        "temperature": 0.1,
                        "num_predict": 500,
                        "top_p": 0.8
                    }
                )

                response_content = response["message"]["content"]
                print(f"🤖 AI response preview: {response_content[:200]}...")

                # Better JSON extraction and parsing
                try:
                    # Try to parse entire response as JSON first
                    ai_result = json.loads(response_content)
                except json.JSONDecodeError:
                    # If that fails, try to extract JSON block from response
                    json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                    if json_match:
                        try:
                            ai_result = json.loads(json_match.group())
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON parsing failed: {e}")
                            print(f"🤖 Raw AI response: {response_content}")
                            return {"found": False, "error": f"JSON parse error: {e}"}
                    else:
                        print(f"❌ No JSON found in AI response")
                        print(f"🤖 Raw AI response: {response_content}")
                        return {"found": False, "error": "No JSON in response"}

                return ai_result

            except Exception as e:
                print(f"❌ AI login detection error: {e}")
                print(f"🤖 AI model: {OLLAMA_MODEL}")
                return {"found": False, "error": str(e)}
                
        except Exception as e:
            print(f"❌ AI login detection error: {e}")
            return {"found": False}
    
    def _fallback_login_detection(self, html_content: str) -> Dict:
        """Fallback pattern-based login detection"""
        print("🔄 Using fallback login detection...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find username field
        username_field = None
        username_selectors = [
            "input[type='email']",
            "input[type='text'][name*='user']",
            "input[type='text'][id*='user']",
            "input[type='text'][placeholder*='user']",
            "input[type='text'][placeholder*='email']"
        ]
        
        for selector in username_selectors:
            elements = soup.select(selector)
            if elements:
                username_field = selector
                break
        
        if not username_field:
            # Generic text input
            text_inputs = soup.select("input[type='text']")
            if text_inputs:
                username_field = "input[type='text']"
        
        # Find password field  
        password_field = None
        password_inputs = soup.select("input[type='password']")
        if password_inputs:
            password_field = "input[type='password']"
        
        # Find submit button
        submit_button = None
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']", 
            "button:contains('Login')",
            "button:contains('Sign In')",
            "button"
        ]
        
        for selector in submit_selectors:
            elements = soup.select(selector)
            if elements:
                submit_button = selector
                break
        
        found = bool(username_field and password_field)
        
        if found:
            print(f"✅ Fallback detection found login form")
            
        return {
            "found": found,
            "username_field": username_field,
            "password_field": password_field,
            "submit_button": submit_button
        }
    
    def _verify_selectors(self, login_data: Dict) -> bool:
        """Verify that selectors actually find elements on the page"""
        try:
            selectors_to_test = [
                login_data.get("username_field"),
                login_data.get("password_field")
            ]
            
            for selector in selectors_to_test:
                if not selector:
                    continue
                    
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if not is_element_visible_and_enabled(element):
                        return False
                except:
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Selector verification failed: {e}")
            return False
    
    def _perform_login(self, username: str, password: str, login_data: Dict) -> bool:
        """Fill login form and submit"""
        try:
            # Find username element
            username_element = self._find_element_universal(login_data.get("username_field"))
            if not username_element:
                print("❌ Could not find username field")
                return False
            
            # Find password element
            password_element = self._find_element_universal(login_data.get("password_field"))
            if not password_element:
                print("❌ Could not find password field")
                return False
            
            # Fill username
            print("📝 Filling username field...")
            username_element.click()
            human_like_delay(0.3, 0.8)
            human_like_typing(username_element, username)
            human_like_delay(0.5, 1.2)
            
            # Fill password
            print("📝 Filling password field...")
            password_element.click()
            human_like_delay(0.2, 0.6)
            human_like_typing(password_element, password)
            human_like_delay(0.8, 1.5)
            
            # Verify fields are filled
            if not username_element.get_attribute('value') or not password_element.get_attribute('value'):
                print("❌ Failed to fill login fields")
                return False
            
            # Submit form
            return self._submit_login_form(login_data, password_element)
            
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def _find_element_universal(self, selector: str):
        """Find element using various selector methods"""
        if not selector:
            return None
            
        try:
            if selector.startswith('#'):
                return self.driver.find_element(By.ID, selector[1:])
            elif selector.startswith('.'):
                return self.driver.find_element(By.CLASS_NAME, selector[1:])
            else:
                return self.driver.find_element(By.CSS_SELECTOR, selector)
        except:
            try:
                return self.driver.find_element(By.NAME, selector)
            except:
                try:
                    return self.driver.find_element(By.ID, selector)
                except:
                    return None
    
    def _submit_login_form(self, login_data: Dict, password_element) -> bool:
        """Submit the login form using various methods"""
        url_before = self.driver.current_url
        
        # Try submit button first
        submit_element = self._find_element_universal(login_data.get("submit_button"))
        
        if submit_element and is_element_visible_and_enabled(submit_element):
            print("🔘 Clicking submit button...")
            try:
                submit_element.click()
            except:
                try:
                    self.driver.execute_script("arguments[0].click();", submit_element)
                except:
                    password_element.send_keys(Keys.RETURN)
        else:
            print("🔘 Pressing Enter on password field...")
            password_element.send_keys(Keys.RETURN)
        
        # Wait for response
        print("⏳ Waiting for login response...")
        time.sleep(LOGIN_WAIT_TIME)
        
        # Check if login was successful
        return self._verify_login_success(url_before)
    
    def _verify_login_success(self, url_before: str) -> bool:
        """Verify if login was successful"""
        try:
            url_after = self.driver.current_url
            page_source = self.driver.page_source.lower()
            
            # Check for error messages
            error_indicators = [
                "invalid username or password",
                "invalid email or password", 
                "login failed",
                "authentication failed",
                "incorrect username",
                "incorrect password"
            ]
            
            has_error = any(error in page_source for error in error_indicators)
            if has_error:
                print("❌ Login failed - error message detected")
                return False
            
            # Check for success indicators
            success_indicators = [
                "dashboard", "account", "welcome", "billing",
                "logout", "sign out", "my account"
            ]
            
            has_success = any(indicator in page_source for indicator in success_indicators)
            url_changed = url_before != url_after
            still_on_login = any(term in url_after.lower() for term in ["login", "signin", "auth"])
            
            print(f"🔍 URL changed: {url_changed}")
            print(f"🔍 Still on login URL: {still_on_login}")
            print(f"🔍 Success indicators: {has_success}")
            
            if url_changed and not still_on_login:
                print("✅ Login successful - redirected away from login page")
                return True
            elif has_success and not has_error:
                print("✅ Login successful - success indicators found")
                return True
            else:
                print("⚠️ Login status unclear - proceeding with caution")
                return True  # Give benefit of doubt
                
        except Exception as e:
            print(f"❌ Login verification error: {e}")
            return False 