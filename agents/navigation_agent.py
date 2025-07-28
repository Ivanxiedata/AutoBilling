#!/usr/bin/env python3
"""
Navigation Agent for AutoBilling
AI-powered intelligent navigation and exploration of billing sites
"""

import time
import json
import re
from typing import Dict, List, Set, Optional

import ollama
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from utils.config import (
    OLLAMA_MODEL, MAX_EXPLORATION_TIME, EXPLORATION_THRESHOLD, 
    HIGH_PRIORITY_NAV, MEDIUM_PRIORITY_NAV, LOW_PRIORITY_NAV,
    COMMON_BILLING_PATTERNS
)
from utils.utils import wait_for_spa_content, has_meaningful_billing_data
from utils.prompts import PromptLibrary

class NavigationAgent:
    """AI-powered intelligent navigation and exploration agent for billing sites"""
    
    def __init__(self, driver):
        """Initialize the navigation agent with a WebDriver instance"""
        self.driver = driver
        self.visited_urls: Set[str] = set()
        
        # Import other agents to avoid circular dependency
        from .billing_evaluator import BillingDataEvaluator
        from .exploration_strategist import ExplorationStrategist
        self.billing_evaluator = BillingDataEvaluator()
        self.exploration_strategist = ExplorationStrategist()
    
    def explore_for_billing_data(self, extraction_orchestrator) -> 'BillInfo':
        """Main exploration method that systematically finds billing data"""
        print("🧭 Starting systematic billing exploration...")
        
        start_time = time.time()
        current_url = self.driver.current_url
        self.visited_urls.add(current_url)
        
        # Check for registration redirect first
        if self._check_registration_redirect():
            from utils import BillInfo
            return BillInfo("Account setup required", 0.0, "Complete account setup", 0.0)
        
        # ENHANCED: Try dashboard extraction on main page first
        print("🏠 Checking main dashboard for billing data...")
        main_page_source = self.driver.page_source
        dashboard_result = extraction_orchestrator.extract_billing_data(main_page_source, self.driver, False)
        
        # NEW: Score the page for billing quality based on date-amount pairs
        billing_score = self._score_billing_page_quality(main_page_source)
        print(f"📊 Billing page score: {billing_score}/100")
        
        # If score >= 85, this is a good billing page - stop and extract
        if billing_score >= 85:
            print(f"🎯 High billing score ({billing_score}) - this page has sufficient billing data!")
            print("🛑 Stopping exploration and using current page data")
            if has_meaningful_billing_data(dashboard_result):
                return dashboard_result
            else:
                print("⚠️ High score but no extractable data - continuing exploration...")
        
        # Use AI evaluation to check if dashboard data is sufficient (fallback)
        ai_evaluation = self.billing_evaluator.evaluate_page_sufficiency(main_page_source)
        
        if ai_evaluation.get('has_sufficient_billing_data'):
            months_found = ai_evaluation.get('months_of_data_found', 0)
            print(f"🏠 Dashboard has sufficient billing data ({months_found} months) - using dashboard extraction")
            return dashboard_result
        elif has_meaningful_billing_data(dashboard_result):
            print(f"🏠 Dashboard has some billing data (${dashboard_result.current_amount:.2f}) - will use as fallback")
            best_dashboard_result = dashboard_result
        else:
            print(f"🏠 Dashboard has no meaningful billing data - continuing exploration...")
            best_dashboard_result = None
        
        # Phase 1: Discover billing links
        billing_links = self._discover_billing_links()
        
        if not billing_links:
            print("⚠️ No billing links found, trying common patterns...")
            billing_links = self._try_common_billing_patterns()
        
        if not billing_links:
            print("❌ No billing links found at all")
            # Return dashboard result if we found any
            if best_dashboard_result and has_meaningful_billing_data(best_dashboard_result):
                print(f"🏠 Returning dashboard data as fallback: ${best_dashboard_result.current_amount:.2f}")
                return best_dashboard_result
            from utils import BillInfo
            return BillInfo("No billing links found", 0.0, "No navigation available", 0.0)
        
        # Phase 2: Rank links by AI
        ranked_links = self._rank_billing_links(billing_links)
        
        if not ranked_links:
            print("❌ No links meet ranking criteria")
            # Return dashboard result if we found any
            if best_dashboard_result and has_meaningful_billing_data(best_dashboard_result):
                print(f"🏠 Returning dashboard data as fallback: ${best_dashboard_result.current_amount:.2f}")
                return best_dashboard_result
            from utils import BillInfo
            return BillInfo("No suitable links found", 0.0, "No ranked links", 0.0)
        
        # Phase 3: Systematic exploration with scoring
        exploration_result = self._explore_links_with_scoring(ranked_links, extraction_orchestrator, start_time)
        
        # If exploration found better data, use it; otherwise use dashboard data
        if has_meaningful_billing_data(exploration_result) and hasattr(exploration_result, 'all_bills') and exploration_result.all_bills:
            print(f"🎯 Exploration found comprehensive data: {len(exploration_result.all_bills)} bills")
            return exploration_result
        elif best_dashboard_result and has_meaningful_billing_data(best_dashboard_result):
            print(f"🏠 Using dashboard data: ${best_dashboard_result.current_amount:.2f}")
            return best_dashboard_result
        else:
            return exploration_result
    
    def _check_registration_redirect(self) -> bool:
        """Check if we've been redirected to a registration page"""
        current_url = self.driver.current_url
        page_source = self.driver.page_source.lower()
        
        # Check URL patterns
        if any(term in current_url.lower() for term in ["registration", "register", "setup"]):
            print("⚠️ Detected registration/setup redirect")
            return True
        
        # Check page content
        registration_indicators = [
            "complete your registration",
            "link your utility account", 
            "account setup required",
            "finish account setup"
        ]
        
        if any(indicator in page_source for indicator in registration_indicators):
            print("⚠️ Detected account setup requirement")
            return True
        
        return False
    
    def _discover_billing_links(self) -> List[Dict]:
        """Discover billing-related links on current page"""
        print("🔗 Discovering billing-related links...")
        
        wait_for_spa_content(self.driver)
        
        # ENHANCED: Try to expand dropdown menus first
        self._try_expand_dropdown_menus()
        
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        elements = self._find_clickable_elements(soup)
        
        current_url = self.driver.current_url
        base_domain = '/'.join(current_url.split('/')[:3])
        
        billing_links = []
        
        print(f"🔍 Scanning {len(elements)} clickable elements...")
        
        for element in elements:
            link_info = self._analyze_element_for_billing(element, base_domain)
            if link_info:
                billing_links.append(link_info)
                # Debug: Show what was found
                print(f"   • Found: '{link_info['text'][:50]}' → {link_info['url']} (score: {link_info['score']})")
        
        print(f"📊 Found {len(billing_links)} potential billing links")
        
        # Show top 5 discovered links
        if billing_links:
            print("🏆 Top discovered links:")
            sorted_links = sorted(billing_links, key=lambda x: x['score'], reverse=True)
            for i, link in enumerate(sorted_links[:5]):
                print(f"   {i+1}. '{link['text']}' (score: {link['score']})")
                print(f"      → {link['url']}")
        else:
            print("⚠️ No billing-related links found on this page")
        
        return billing_links
    
    def _try_expand_dropdown_menus(self):
        """Try to expand dropdown menus that might contain billing links"""
        try:
            print("🔽 Attempting to expand dropdown menus...")
            
            # Common dropdown menu triggers for billing
            dropdown_triggers = [
                "BILL & PAY", "BILLING", "PAYMENTS", "ACCOUNT", "SERVICES", "USAGE"
            ]
            
            expanded_any = False
            
            # Method 1: Find by exact text content
            for trigger_text in dropdown_triggers:
                try:
                    print(f"   🔍 Looking for dropdown trigger: '{trigger_text}'")
                    
                    # Find elements with this text that might be dropdown triggers
                    elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{trigger_text}')]")
                    print(f"       Found {len(elements)} elements with text '{trigger_text}'")
                    
                    for element in elements:
                        try:
                            # Check if this element or its parent has dropdown indicators
                            parent = element.find_element(By.XPATH, "./..")
                            element_classes = element.get_attribute("class") or ""
                            parent_classes = parent.get_attribute("class") or ""
                            
                            print(f"       Element classes: '{element_classes}'")
                            print(f"       Parent classes: '{parent_classes}'")
                            
                            # Look for dropdown indicators
                            is_dropdown = any(indicator in (element_classes + " " + parent_classes).lower() for indicator in [
                                'dropdown', 'collapse', 'toggle', 'expand', 'menu', 'nav-item', 'mat-', 'angular'
                            ])
                            
                            # Check for aria-expanded attribute
                            aria_expanded = element.get_attribute("aria-expanded")
                            parent_aria_expanded = parent.get_attribute("aria-expanded")
                            
                            print(f"       Is dropdown: {is_dropdown}, aria-expanded: {aria_expanded}/{parent_aria_expanded}")
                            
                            if is_dropdown or aria_expanded == "false" or parent_aria_expanded == "false":
                                print(f"   🔽 Clicking dropdown trigger: '{trigger_text}'")
                                
                                # Try clicking the element
                                self.driver.execute_script("arguments[0].click();", element)
                                
                                # Wait a moment for dropdown to expand
                                import time
                                time.sleep(2)
                                
                                expanded_any = True
                                print(f"       ✅ Successfully clicked '{trigger_text}'")
                                break
                                
                        except Exception as e:
                            print(f"       ❌ Error clicking element: {e}")
                            continue
                            
                except Exception as e:
                    print(f"   ❌ Error finding '{trigger_text}': {e}")
                    continue
            
            # Method 2: Find sidebar elements by CSS selectors
            sidebar_selectors = [
                # Angular Material selectors
                "mat-nav-list button", "mat-nav-list mat-list-item", 
                ".mat-nav-list button", ".mat-nav-list .mat-list-item",
                # General sidebar selectors
                "nav button", "aside button", ".sidebar button",
                ".nav-item", ".nav-link", ".menu-item",
                # Look for elements with dropdown arrows
                "*[class*='dropdown']", "*[class*='collapse']", "*[class*='toggle']"
            ]
            
            print(f"   🔍 Trying CSS selectors for sidebar elements...")
            for selector in sidebar_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"       Found {len(elements)} elements with selector '{selector}'")
                        
                        for element in elements[:3]:  # Check first 3 elements
                            try:
                                element_text = element.text.strip()
                                if any(trigger in element_text.upper() for trigger in ["BILL", "PAY", "BILLING", "USAGE"]):
                                    print(f"       🎯 Found billing-related sidebar element: '{element_text}'")
                                    print(f"       Clicking sidebar element...")
                                    
                                    self.driver.execute_script("arguments[0].click();", element)
                                    time.sleep(2)
                                    expanded_any = True
                                    print(f"       ✅ Successfully clicked sidebar element")
                                    break
                            except Exception as e:
                                print(f"       ❌ Error with sidebar element: {e}")
                                continue
                        
                        if expanded_any:
                            break
                            
                except Exception as e:
                    print(f"       ❌ Error with selector '{selector}': {e}")
                    continue
            
            # Method 3: Find all clickable elements and check their text
            if not expanded_any:
                print(f"   🔍 Scanning all clickable elements for billing keywords...")
                try:
                    all_clickable = self.driver.find_elements(By.XPATH, "//*[@onclick or @ng-click or @routerlink or name()='button' or name()='a']")
                    print(f"       Found {len(all_clickable)} total clickable elements")
                    
                    billing_elements = []
                    for element in all_clickable:
                        try:
                            element_text = element.text.strip().upper()
                            if any(keyword in element_text for keyword in ["BILL", "PAY", "BILLING", "USAGE", "ACCOUNT"]):
                                billing_elements.append((element, element_text))
                        except:
                            continue
                    
                    print(f"       Found {len(billing_elements)} elements with billing keywords:")
                    for element, text in billing_elements[:5]:  # Show first 5
                        print(f"         • '{text}'")
                        
                    # Try clicking the first promising one
                    if billing_elements:
                        element, text = billing_elements[0]
                        print(f"   🔽 Clicking first billing element: '{text}'")
                        self.driver.execute_script("arguments[0].click();", element)
                        time.sleep(2)
                        expanded_any = True
                        
                except Exception as e:
                    print(f"   ❌ Error scanning clickable elements: {e}")
            
            if expanded_any:
                print("   ✅ Dropdown menus expanded, waiting for content...")
                wait_for_spa_content(self.driver)
            else:
                print("   ⚠️ No dropdown menus found to expand")
                
        except Exception as e:
            print(f"   ❌ Error expanding dropdowns: {e}")
    
    def _find_clickable_elements(self, soup) -> List:
        """Find all potentially clickable elements"""
        elements = []
        
        # Standard links
        elements.extend(soup.find_all('a', href=True))
        
        # Buttons with onclick
        elements.extend(soup.find_all(['button', 'div', 'span'], onclick=True))
        
        # SPA-specific elements
        elements.extend(soup.find_all(attrs={'ng-click': True}))
        elements.extend(soup.find_all(attrs={'routerlink': True}))
        elements.extend(soup.find_all(attrs={'ui-sref': True}))
        
        # Elements with billing-related text
        all_elements = soup.find_all(['a', 'button', 'div', 'span', 'li'])
        for element in all_elements:
            text = element.get_text(strip=True).lower()
            if any(keyword in text for keyword in HIGH_PRIORITY_NAV + MEDIUM_PRIORITY_NAV):
                if element not in elements:
                    elements.append(element)
        
        return elements
    
    def _analyze_element_for_billing(self, element, base_domain: str) -> Optional[Dict]:
        """Analyze element to determine if it's billing-related"""
        try:
            # Get element properties
            text = element.get_text(strip=True).lower()
            href = element.get('href', '')
            
            # Skip if no meaningful text
            if len(text) < 2:
                return None
            
            # Calculate billing relevance score
            score = self._calculate_billing_score(text, href)
            
            if score < 30:  # Skip irrelevant links
                return None
            
            # Construct URL
            full_url = self._construct_full_url(element, base_domain)
            
            if not full_url or full_url in self.visited_urls:
                return None
            
            return {
                'url': full_url,
                'text': text[:50],
                'score': score,
                'element_type': element.name,
                'navigation_type': self._get_navigation_type(element)
            }
            
        except Exception:
            return None
    
    def _calculate_billing_score(self, text: str, href: str) -> int:
        """Calculate relevance score for billing content"""
        score = 0
        
        # High priority terms
        for term in HIGH_PRIORITY_NAV:
            if term in text:
                score += 50
            if term in href.lower():
                score += 30
        
        # Medium priority terms
        for term in MEDIUM_PRIORITY_NAV:
            if term in text:
                score += 30
            if term in href.lower():
                score += 20
        
        # Low priority terms
        for term in LOW_PRIORITY_NAV:
            if term in text:
                score += 15
        
        # URL-based scoring
        if any(pattern in href.lower() for pattern in ['billing', 'transaction', 'history']):
            score += 40
        
        return min(score, 100)
    
    def _construct_full_url(self, element, base_domain: str) -> Optional[str]:
        """Construct full URL from element"""
        # Standard href
        href = element.get('href', '')
        if href:
            if href.startswith('/'):
                return base_domain + href
            elif href.startswith('#'):
                return base_domain + href
            elif href.startswith('http'):
                return href if base_domain in href else None
            else:
                return base_domain + '/' + href
        
        # Angular router-link
        router_link = element.get('routerlink', '')
        if router_link:
            return base_domain + '/ui' + router_link if router_link.startswith('/') else base_domain + '/ui/' + router_link
        
        # Try to construct from text for special cases
        text = element.get_text(strip=True).lower()
        if 'billing history' in text:
            return base_domain + '/#/billing-history'
        elif 'transaction history' in text:
            return base_domain + '/#/transaction-history'
        
        return None
    
    def _get_navigation_type(self, element) -> str:
        """Determine navigation type of element"""
        if element.get('href'):
            return 'href'
        elif element.get('routerlink'):
            return 'router'
        elif element.get('ng-click'):
            return 'ng-click'
        elif element.get('onclick'):
            return 'onclick'
        else:
            return 'text-based'
    
    def _try_common_billing_patterns(self) -> List[Dict]:
        """Try common billing URL patterns when no links found"""
        base_url = '/'.join(self.driver.current_url.split('/')[:3])
        pattern_links = []
        
        for pattern in COMMON_BILLING_PATTERNS:
            pattern_url = base_url + pattern
            pattern_links.append({
                'url': pattern_url,
                'text': pattern.replace('/#/', '').replace('-', ' ').title(),
                'score': 85,
                'element_type': 'pattern',
                'navigation_type': 'pattern'
            })
        
        print(f"📊 Added {len(pattern_links)} common billing patterns")
        return pattern_links
    
    def _rank_billing_links(self, billing_links: List[Dict]) -> List[Dict]:
        """Rank billing links by AI analysis"""
        try:
            print("🧠 AI ranking billing links...")
            
            # Prepare simplified data for AI
            links_for_ai = []
            for i, link in enumerate(billing_links[:10]):  # Limit for AI processing
                links_for_ai.append({
                    'index': i,
                    'url': link['url'],
                    'text': link['text'],
                    'score': link['score']
                })
            
            prompt = f"""
            You are a utility billing expert. Rank these links by billing relevance. RETURN ONLY JSON.

            LINKS TO RANK:
            {json.dumps(links_for_ai, indent=2)}

            RANKING CRITERIA:
            - 90-100: Transaction/billing/payment history, statements
            - 70-89: Account details, usage data, bills  
            - 50-69: Dashboard, overview
            - 0-49: Settings, help, non-billing

            RETURN ONLY THIS JSON FORMAT:
            {{
                "ranked_links": [
                    {{
                        "url": "full_url", 
                        "score": 95,
                        "reasoning": "transaction history page"
                    }}
                ]
            }}
            """
            
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 800
                }
            )
            
            response_content = response["message"]["content"]
            print(f"🤖 AI ranking response preview: {response_content[:150]}...")
            
            # Better JSON parsing
            try:
                result = json.loads(response_content)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found in AI response")
            
            ranked_links = result.get('ranked_links', [])
            
            # Apply threshold filter
            filtered_links = [link for link in ranked_links if link.get('score', 0) >= EXPLORATION_THRESHOLD]
            
            if not filtered_links:
                print(f"🚫 No links meet threshold of {EXPLORATION_THRESHOLD}")
                # Lower threshold if no links meet criteria
                filtered_links = [link for link in ranked_links if link.get('score', 0) >= 50]
                if filtered_links:
                    print(f"🔄 Using lower threshold (50+): {len(filtered_links)} links")
            
            if not filtered_links:
                print("🔄 Using all available links")
                return billing_links[:5]  # Return original links
            
            print(f"🎯 {len(filtered_links)} links meet exploration threshold")
            for i, link in enumerate(filtered_links[:3]):
                print(f"   {i+1}. {link['url']} (score: {link['score']})")
            
            return filtered_links
            
        except Exception as e:
            print(f"❌ AI ranking failed: {e}")
            print(f"🔄 Using fallback ranking based on text keywords...")
            
            # Enhanced fallback ranking
            for link in billing_links:
                text = link.get('text', '').lower()
                # Boost scores for key terms
                if 'billing history' in text or 'transaction history' in text:
                    link['score'] = 95
                elif 'payment history' in text or 'account history' in text:
                    link['score'] = 90
                elif 'bills' in text or 'statements' in text:
                    link['score'] = 85
                elif 'billing' in text or 'transactions' in text:
                    link['score'] = 80
                elif 'account' in text or 'usage' in text:
                    link['score'] = 70
            
            # Sort by enhanced scores
            enhanced_links = sorted(billing_links, key=lambda x: x['score'], reverse=True)
            print(f"🎯 Fallback ranking: Top link is '{enhanced_links[0]['text']}' (score: {enhanced_links[0]['score']})")
            
            return enhanced_links[:5]
    
    def _explore_links_with_scoring(self, ranked_links: List[Dict], extraction_orchestrator, start_time: float) -> 'BillInfo':
        """Systematically explore billing links with page scoring to stop early if good data found"""
        print("📋 Starting AI-driven systematic exploration...")
        print("")
        
        best_result = None
        highest_score = 0
        
        for i, link in enumerate(ranked_links):
            elapsed = time.time() - start_time
            
            if elapsed > MAX_EXPLORATION_TIME:
                print(f"⏰ Time limit reached ({MAX_EXPLORATION_TIME}s)")
                break
                
            url = link['url']
            score = link.get('score', 0)
            
            print(f"🎯 Exploring {i+1}/{len(ranked_links)}: {url}")
            print(f"⏱️  Time: {elapsed:.1f}s/{MAX_EXPLORATION_TIME}s")
            
            if url in self.visited_urls:
                print("⏭️  Already visited, skipping...")
                continue
                
            try:
                result = self._explore_single_link(url, link, extraction_orchestrator, start_time)
                
                if result and has_meaningful_billing_data(result):
                    # Score this page for billing quality
                    page_source = self.driver.page_source
                    billing_score = self._score_billing_page_quality(page_source)
                    
                    print(f"📊 Page billing score: {billing_score}/100")
                    
                    # If score >= 85, this is a great billing page - stop exploration
                    if billing_score >= 85:
                        print(f"🎯 Excellent billing score ({billing_score}) - stopping exploration!")
                        print("🛑 Found high-quality billing page")
                        return result
                    
                    # Track the best result found so far
                    if billing_score > highest_score:
                        highest_score = billing_score
                        best_result = result
                        print(f"🏆 New best result (score: {billing_score})")
                
            except Exception as e:
                print(f"❌ Error exploring {url}: {e}")
                continue
        
        # Return the best result found, or a default if nothing was found
        if best_result:
            print(f"📊 Returning best result with score: {highest_score}/100")
            return best_result
        else:
            from utils import BillInfo
            return BillInfo("No meaningful data found", 0.0, "Exploration completed", 0.0)
    
    def _explore_single_link(self, url: str, link_info: Dict, extraction_orchestrator, start_time: float = None) -> 'BillInfo':
        """Explore a single link and extract billing data."""
        print(f"🔗 Navigating to: {url}")
        
        try:
            self.driver.get(url)
            wait_for_spa_content(self.driver)
            self.visited_urls.add(url)
            
            # Check if this is a billing history page
            page_source = self.driver.page_source
            is_billing_page = self._is_billing_history_page(page_source)
            
            print(f"�� Billing page: {is_billing_page}")
            
            # Extract data
            billing_data = extraction_orchestrator.extract_billing_data(page_source, self.driver, is_billing_page)
            
            # ALWAYS use AI evaluation to determine data sufficiency (even if extraction succeeded)
            print(f"📊 Basic extraction complete, now using AI evaluation for quality assessment...")
            
            # AI Evaluation: Does this page have sufficient billing data (4+ months)?
            ai_evaluation = self.billing_evaluator.evaluate_page_sufficiency(page_source)
            
            if ai_evaluation.get('has_sufficient_billing_data'):
                months_found = ai_evaluation.get('months_of_data_found', 0)
                data_quality = ai_evaluation.get('data_quality', 'unknown')
                print(f"🤖 AI Evaluation: SUFFICIENT billing data ({months_found} months, {data_quality} quality)")
                
                # AI confirms sufficient data - use the best available extraction
                if has_meaningful_billing_data(billing_data):
                    print(f"✅ Using basic extraction data (AI confirmed sufficient)")
                    return billing_data
                else:
                    # Basic extraction failed but AI found data - try AI-guided extraction
                    billing_entries = ai_evaluation.get('billing_entries_found', [])
                    if billing_entries:
                        print(f"📊 AI identified {len(billing_entries)} billing entries - extracting...")
                        enhanced_data = self.billing_evaluator.extract_with_ai_guidance(billing_entries, extraction_orchestrator, page_source)
                        if has_meaningful_billing_data(enhanced_data):
                            return enhanced_data
            else:
                months_found = ai_evaluation.get('months_of_data_found', 0)
                evaluation_reason = ai_evaluation.get('evaluation_reason', 'No reason provided')
                print(f"🤖 AI Evaluation: INSUFFICIENT billing data ({months_found} months)")
                print(f"   Reason: {evaluation_reason}")
                print(f"   🧠 Consulting exploration AI for next steps...")
                
                # AI says insufficient data - use exploration strategy AI
                ai_strategy = self.exploration_strategist.determine_exploration_strategy(url, page_source, self.visited_urls)
                
                if ai_strategy.get('exploration_needed'):
                    strategy_plan = ai_strategy.get('strategy', 'No strategy provided')
                    print(f"🧠 AI Strategy: {strategy_plan}")
                    
                    next_links = ai_strategy.get('next_links', [])
                    if next_links:
                        print(f"🔗 AI recommends exploring {len(next_links)} additional links:")
                        
                        # Sort by AI priority and explore top links
                        sorted_links = sorted(next_links, key=lambda x: x.get('priority', 0), reverse=True)
                        
                        for j, ai_link in enumerate(sorted_links[:3]):  # Limit to top 3 AI recommendations
                            if start_time and time.time() - start_time > MAX_EXPLORATION_TIME:
                                break
                                        
                            ai_url = ai_link.get('url')
                            if not ai_url or ai_url in self.visited_urls:
                                continue
                                        
                            ai_text = ai_link.get('text', 'Unknown')
                            ai_reason = ai_link.get('reason', 'No reason provided')
                            ai_priority = ai_link.get('priority', 0)
                            
                            print(f"  🎯 AI Sub-exploring {j+1}: '{ai_text}' (priority: {ai_priority})")
                            print(f"      Reason: {ai_reason}")
                            print(f"      URL: {ai_url}")
                            
                            try:
                                self.driver.get(ai_url)
                                wait_for_spa_content(self.driver)
                                self.visited_urls.add(ai_url)
                                
                                # Try extraction on AI-recommended page
                                sub_page_source = self.driver.page_source
                                sub_is_billing = self._is_billing_history_page(sub_page_source)
                                print(f"    🤖 AI sub-page billing: {sub_is_billing}")
                                
                                sub_billing_data = extraction_orchestrator.extract_billing_data(sub_page_source, self.driver, sub_is_billing)
                                
                                if has_meaningful_billing_data(sub_billing_data):
                                    print(f"    ✅ Found billing data on AI-recommended page!")
                                    return sub_billing_data
                                else:
                                    print(f"    ⚠️ No data on AI-recommended page")
                                        
                            except Exception as sub_error:
                                print(f"    ❌ AI sub-exploration error: {sub_error}")
                                continue
                    else:
                        print(f"🤖 AI found no promising links to explore further")
                else:
                    print(f"🤖 AI determined no further exploration needed")
            
            # Keep track of best partial result and return it
            if has_meaningful_billing_data(billing_data):
                return billing_data
            else:
                # Return None if no meaningful data found on this link
                return None
                
        except Exception as e:
            print(f"❌ Error exploring {url}: {e}")
            return None
    
    def _is_billing_history_page(self, page_source: str) -> bool:
        """Quick check if page contains billing history"""
        page_text = page_source.lower()
        
        # Look for billing history indicators
        history_indicators = [
            'transaction history',
            'billing history', 
            'payment history',
            'account history',
            'statement history'
        ]
        
        # Look for table structures with billing data
        table_indicators = [
            '<table' in page_text and 'amount' in page_text,
            '<table' in page_text and 'date' in page_text,
            'billing' in page_text and 'amount' in page_text
        ]
        
        return (any(indicator in page_text for indicator in history_indicators) or
                any(table_indicators))
    
    def _common_billing_patterns(self, base_url: str) -> List[str]:
        """Generate common billing URL patterns."""
        patterns = []
        for pattern in COMMON_BILLING_PATTERNS:
            patterns.append(base_url + pattern)
        return patterns 

    def _score_billing_page_quality(self, page_source: str) -> int:
        """Score a page for billing data quality based on date-amount pairs
        
        Criteria:
        - Look for at least 3 different dates with corresponding amounts
        - Score based on quantity and quality of billing data found
        - Return score 0-100, where 85+ means "good billing page"
        """
        print("📊 Scoring page for billing data quality...")
        
        try:
            from bs4 import BeautifulSoup
            import re
            from datetime import datetime
            
            soup = BeautifulSoup(page_source, 'html.parser')
            page_text = soup.get_text()
            
            # Find date-amount pairs
            date_amount_pairs = []
            
            # Enhanced date patterns
            date_patterns = [
                r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
                r'(\d{4}-\d{1,2}-\d{1,2})',  # YYYY-MM-DD
                r'([A-Za-z]+ \d{1,2},? \d{4})',  # Month DD, YYYY
                r'(\d{1,2} [A-Za-z]+ \d{4})',  # DD Month YYYY
                r'([A-Za-z]+ \d{4})',  # Month YYYY
            ]
            
            # Enhanced amount patterns (look for currency amounts)
            amount_patterns = [
                r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $123.45 or $1,234.56
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|USD|\$)',  # 123.45 dollars
            ]
            
            # Look for structured data first (tables, lists)
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    row_text = row.get_text()
                    dates_in_row = []
                    amounts_in_row = []
                    
                    # Find dates in this row
                    for date_pattern in date_patterns:
                        dates_in_row.extend(re.findall(date_pattern, row_text))
                    
                    # Find amounts in this row
                    for amount_pattern in amount_patterns:
                        amounts_in_row.extend(re.findall(amount_pattern, row_text))
                    
                    # If we found both dates and amounts in the same row, it's likely billing data
                    if dates_in_row and amounts_in_row:
                        for date_str in dates_in_row:
                            for amount_str in amounts_in_row:
                                try:
                                    amount = float(amount_str.replace(',', ''))
                                    if 5.0 <= amount <= 5000.0:  # Reasonable utility bill range
                                        date_amount_pairs.append({
                                            'date': date_str,
                                            'amount': amount,
                                            'source': 'table_row'
                                        })
                                        print(f"   📋 Found table entry: {date_str} → ${amount:.2f}")
                                except:
                                    continue
            
            # Look for dashboard-style date-amount pairs
            dashboard_patterns = [
                # Look for "PAID on Date" followed by amount nearby
                r'(?:paid|due|bill)\s+(?:on|date)?\s*([A-Za-z]+ \d{1,2},? \d{4}).*?\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?).*?(?:paid|due|on)\s+([A-Za-z]+ \d{1,2},? \d{4})',
                # Look for amount followed by date
                r'(?:amount|bill|payment).*?\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?).*?(\d{1,2}/\d{1,2}/\d{4})',
            ]
            
            for pattern in dashboard_patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    try:
                        groups = match.groups()
                        if len(groups) == 2:
                            # Try both orders (date-amount or amount-date)
                            for i, group in enumerate(groups):
                                try:
                                    amount = float(group.replace(',', ''))
                                    date_str = groups[1-i]  # The other group
                                    if 5.0 <= amount <= 5000.0:
                                        date_amount_pairs.append({
                                            'date': date_str,
                                            'amount': amount,
                                            'source': 'dashboard_pattern'
                                        })
                                        print(f"   🏠 Found dashboard entry: {date_str} → ${amount:.2f}")
                                        break
                                except:
                                    continue
                    except:
                        continue
            
            # Look for current bill amounts with implied current date
            current_bill_patterns = [
                r'current.*bill.*amount.*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                r'amount.*due.*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                r'balance.*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                # Enhanced patterns for dashboard billing
                r'bill.*amount.*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                r'paid.*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                r'payment.*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            ]
            
            current_date = datetime.now().strftime('%m/%d/%Y')
            current_bill_count = 0
            
            for pattern in current_bill_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for amount_str in matches:
                    try:
                        amount = float(amount_str.replace(',', ''))
                        if 5.0 <= amount <= 5000.0:
                            # Use slightly different dates for multiple current bill amounts to avoid deduplication
                            current_bill_count += 1
                            pseudo_date = datetime.now()
                            pseudo_date = pseudo_date.replace(day=min(28, pseudo_date.day + current_bill_count - 1))
                            date_str = pseudo_date.strftime('%m/%d/%Y')
                            
                            date_amount_pairs.append({
                                'date': date_str,
                                'amount': amount,
                                'source': 'current_bill'
                            })
                            print(f"   💳 Found current bill: {date_str} → ${amount:.2f}")
                    except:
                        continue
            
            # Remove duplicates with enhanced logic for dashboard pages
            unique_pairs = []
            seen_combinations = set()
            
            for pair in date_amount_pairs:
                # For dashboard pages, allow multiple amounts on same/similar dates
                if pair['source'] == 'current_bill':
                    amount_key = f"current_{pair['amount']:.2f}"
                else:
                    amount_key = f"{pair['date']}_{pair['amount']:.2f}"
                
                if amount_key not in seen_combinations:
                    seen_combinations.add(amount_key)
                    unique_pairs.append(pair)
            
            print(f"   📊 Found {len(unique_pairs)} unique date-amount pairs")
            
            # Calculate score based on criteria
            score = 0
            
            # Base score for having billing-related content
            billing_keywords = ['bill', 'payment', 'amount', 'due', 'balance', 'paid', 'current']
            keyword_count = sum(1 for keyword in billing_keywords if keyword in page_text.lower())
            if keyword_count >= 3:
                score += 30
                print(f"   ✅ +30 points: Contains {keyword_count} billing keywords")
            elif keyword_count >= 1:
                score += 20
                print(f"   ✅ +20 points: Contains {keyword_count} billing keywords")
            
            # Score based on number of date-amount pairs
            pair_count = len(unique_pairs)
            if pair_count >= 3:
                score += 50  # Meets minimum criteria
                print(f"   ✅ +50 points: Has {pair_count} date-amount pairs (≥3 required)")
                
                # Bonus points for more pairs
                bonus = min((pair_count - 3) * 10, 20)  # Up to 20 bonus points
                score += bonus
                if bonus > 0:
                    print(f"   ✅ +{bonus} points: Bonus for {pair_count} pairs")
            elif pair_count >= 2:
                score += 35  # Good progress toward criteria
                print(f"   ⚠️  +35 points: Has {pair_count} date-amount pairs (need ≥3)")
            elif pair_count >= 1:
                score += 25  # Some data found
                print(f"   ⚠️  +25 points: Has {pair_count} date-amount pairs (need ≥3)")
            else:
                print(f"   ❌ No date-amount pairs found")
            
            # Bonus for dashboard pages with multiple current amounts
            current_amounts = [pair for pair in unique_pairs if pair['source'] == 'current_bill']
            if len(current_amounts) >= 2:
                bonus = min(len(current_amounts) * 10, 20)
                score += bonus
                print(f"   ✅ +{bonus} points: Dashboard with {len(current_amounts)} current billing amounts")
            
            # Bonus for structured data (tables)
            if any(pair['source'] == 'table_row' for pair in unique_pairs):
                score += 10
                print(f"   ✅ +10 points: Contains structured table data")
            
            # Bonus for recent dates
            recent_dates = 0
            current_year = datetime.now().year
            for pair in unique_pairs:
                try:
                    if str(current_year) in pair['date'] or str(current_year-1) in pair['date']:
                        recent_dates += 1
                except:
                    continue
            
            if recent_dates > 0:
                bonus = min(recent_dates * 5, 15)
                score += bonus
                print(f"   ✅ +{bonus} points: {recent_dates} recent dates")
            
            score = min(score, 100)  # Cap at 100
            
            print(f"   📊 Final billing score: {score}/100")
            return score
            
        except Exception as e:
            print(f"   ❌ Error scoring page: {e}")
            return 0 