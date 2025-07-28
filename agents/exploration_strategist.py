#!/usr/bin/env python3
"""
Exploration Strategist Agent for AutoBilling
AI agent responsible for determining next exploration steps when insufficient billing data is found
"""

import json
import re
from typing import Dict, List
from bs4 import BeautifulSoup

import ollama

from utils.config import OLLAMA_MODEL
from utils.prompts import PromptLibrary


class ExplorationStrategist:
    """AI agent that determines exploration strategy for finding billing data"""
    
    def __init__(self):
        self.model = OLLAMA_MODEL
    
    def determine_exploration_strategy(self, current_url: str, page_source: str, visited_urls: set) -> Dict:
        """
        Determine exploration strategy for current page
        
        Args:
            current_url: Current page URL
            page_source: Raw HTML content of the page
            visited_urls: Set of already visited URLs
            
        Returns:
            Dict with exploration strategy including next links and priorities
        """
        try:
            print(f"🧠 Consulting AI for exploration strategy...")
            
            # Get page title
            soup = BeautifulSoup(page_source, 'html.parser')
            page_title = soup.title.get_text(strip=True) if soup.title else "No title"
            
            # Discover available links on current page
            discovered_links = self._discover_available_links(soup, current_url, visited_urls)
            
            # Prepare prompt data
            prompt_data = {
                'current_url': current_url,
                'page_title': page_title,
                'discovered_links': json.dumps(discovered_links, indent=2)
            }
            
            # Get AI exploration strategy
            prompt = PromptLibrary.get_prompt('exploration_strategy', **prompt_data)
            
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 1000
                }
            )
            
            response_content = response["message"]["content"]
            print(f"🤖 AI strategy response preview: {response_content[:150]}...")
            
            # Parse AI response
            ai_strategy = self._parse_ai_response(response_content)
            
            # Log strategy results
            self._log_strategy_results(ai_strategy)
            
            return ai_strategy
            
        except Exception as e:
            print(f"❌ AI strategy consultation failed: {e}")
            return self._get_default_strategy()
    
    def _discover_available_links(self, soup: BeautifulSoup, current_url: str, visited_urls: set) -> List[Dict]:
        """Discover available links on current page with sidebar prioritization"""
        elements = self._find_clickable_elements(soup)
        base_domain = '/'.join(current_url.split('/')[:3])
        
        discovered_links = []
        for element in elements[:20]:  # Increased limit for better coverage
            try:
                text = element.get_text(strip=True)
                if len(text) < 2:
                    continue
                    
                href = element.get('href', '')
                full_url = self._construct_full_url(element, base_domain)
                
                if full_url and full_url not in visited_urls:
                    # Determine element location and priority
                    location, priority_boost = self._analyze_element_location(element)
                    
                    discovered_links.append({
                        'text': text[:50],  # Limit text length for AI
                        'url': full_url,
                        'href': href,
                        'location': location,
                        'priority_boost': priority_boost
                    })
            except:
                continue
        
        return discovered_links
    
    def _analyze_element_location(self, element) -> tuple:
        """Analyze where the element is located and assign priority boost"""
        # Check if element is in sidebar
        parent = element.parent
        location = "main"
        priority_boost = 0
        
        # Traverse up the DOM to check for sidebar containers
        current = element
        for _ in range(5):  # Check up to 5 levels up
            if current is None:
                break
                
            # Check element classes and IDs for sidebar indicators
            classes = current.get('class', [])
            element_id = current.get('id', '')
            
            if isinstance(classes, list):
                classes = ' '.join(classes)
            
            sidebar_indicators = [
                'sidebar', 'nav', 'navigation', 'menu', 'side-nav', 
                'left-nav', 'right-nav', 'utility-nav', 'account-nav'
            ]
            
            if any(indicator in classes.lower() for indicator in sidebar_indicators):
                location = "sidebar"
                priority_boost = 5  # High boost for sidebar elements
                break
            elif any(indicator in element_id.lower() for indicator in sidebar_indicators):
                location = "sidebar"
                priority_boost = 5
                break
            
            # Check for header/footer
            if any(indicator in classes.lower() for indicator in ['header', 'top-nav']):
                location = "header"
                priority_boost = 2
                break
            elif any(indicator in classes.lower() for indicator in ['footer', 'bottom']):
                location = "footer"
                priority_boost = 1
                break
                
            current = current.parent
        
        # Additional boost for high-priority billing keywords
        text = element.get_text(strip=True).lower()
        high_priority_keywords = [
            'transactions', 'transaction history', 'account detail', 
            'billing history', 'payment history', 'account history'
        ]
        
        if any(keyword in text for keyword in high_priority_keywords):
            priority_boost += 3
            
        return location, priority_boost
    
    def _find_clickable_elements(self, soup: BeautifulSoup) -> List:
        """Find all potentially clickable elements with special focus on sidebar navigation and SPA elements"""
        elements = []
        
        # PRIORITY 1: Sidebar navigation elements (highest priority)
        sidebar_selectors = [
            'nav', 'aside', '.sidebar', '#sidebar', '.nav-sidebar', 
            '.side-nav', '.navigation', '.menu', '.nav-menu',
            '.left-nav', '.right-nav', '[role="navigation"]',
            '.utility-nav', '.account-nav', '.billing-nav',
            # Angular Material and SPA specific selectors
            'mat-nav-list', 'mat-list-item', '.mat-list-item',
            '[routerlink]', '[ng-click]', '[ui-sref]',
            # Common SPA sidebar patterns
            '.nav-item', '.nav-link', '.menu-item', '.sidebar-menu'
        ]
        
        for selector in sidebar_selectors:
            sidebar_elements = soup.select(selector)
            for sidebar in sidebar_elements:
                # Find links within sidebar
                sidebar_links = sidebar.find_all('a', href=True)
                elements.extend(sidebar_links)
                # Also check for clickable divs/spans in sidebar
                sidebar_clickable = sidebar.find_all(['div', 'span', 'li', 'button'], onclick=True)
                elements.extend(sidebar_clickable)
                # SPA specific clickable elements
                spa_clickable = sidebar.find_all(['div', 'span', 'li', 'button'], attrs={
                    'routerlink': True, 'ng-click': True, 'ui-sref': True, 'data-target': True
                })
                elements.extend(spa_clickable)
        
        # PRIORITY 2: Look for expandable/dropdown menu triggers
        dropdown_selectors = [
            '[data-toggle="collapse"]', '[data-bs-toggle="collapse"]',
            '.dropdown-toggle', '.collapse-toggle', '.menu-toggle',
            # Angular Material expansion panels
            'mat-expansion-panel-header', '.mat-expansion-panel-header',
            # Bootstrap and common dropdown patterns
            '.nav-item.dropdown', '.dropdown', '[aria-expanded]'
        ]
        
        for selector in dropdown_selectors:
            dropdown_elements = soup.select(selector)
            elements.extend(dropdown_elements)
        
        # PRIORITY 3: Standard links with billing keywords
        standard_links = soup.find_all('a', href=True)
        elements.extend(standard_links)
        
        # PRIORITY 4: Buttons and interactive elements
        buttons = soup.find_all(['button', 'div', 'span'], onclick=True)
        elements.extend(buttons)
        
        # PRIORITY 5: SPA-specific elements
        spa_elements = []
        spa_elements.extend(soup.find_all(attrs={'ng-click': True}))
        spa_elements.extend(soup.find_all(attrs={'routerlink': True}))
        spa_elements.extend(soup.find_all(attrs={'ui-sref': True}))
        spa_elements.extend(soup.find_all(attrs={'data-target': True}))
        spa_elements.extend(soup.find_all(attrs={'data-toggle': True}))
        elements.extend(spa_elements)
        
        # PRIORITY 6: Elements with high-priority billing text
        from .config import HIGH_PRIORITY_NAV, MEDIUM_PRIORITY_NAV
        
        billing_keywords = HIGH_PRIORITY_NAV + MEDIUM_PRIORITY_NAV + [
            'transactions', 'transaction history', 'account detail', 'account history',
            'billing history', 'payment history', 'bill history', 'my account',
            'bill & pay', 'bill pay', 'billing & payments', 'bills & payments'
        ]
        
        all_elements = soup.find_all(['a', 'button', 'div', 'span', 'li'])
        for element in all_elements:
            text = element.get_text(strip=True).lower()
            if any(keyword in text for keyword in billing_keywords):
                if element not in elements:
                    elements.append(element)
        
        # Remove duplicates while preserving order (prioritizing sidebar elements)
        seen = set()
        unique_elements = []
        for element in elements:
            element_id = id(element)
            if element_id not in seen:
                seen.add(element_id)
                unique_elements.append(element)
        
        return unique_elements
    
    def _construct_full_url(self, element, base_domain: str) -> str:
        """Construct full URL from element"""
        try:
            href = element.get('href', '')
            onclick = element.get('onclick', '')
            ng_click = element.get('ng-click', '')
            router_link = element.get('routerlink', '')
            
            # Handle different URL patterns
            if href:
                if href.startswith('http'):
                    return href
                elif href.startswith('/'):
                    return base_domain + href
                elif href.startswith('#'):
                    return None  # Skip anchor links
                else:
                    return base_domain + '/' + href
            elif router_link:
                return base_domain + router_link if not router_link.startswith('/') else base_domain + router_link
            elif onclick and 'location' in onclick:
                # Extract URL from onclick
                url_match = re.search(r'["\']([^"\']+)["\']', onclick)
                if url_match:
                    url = url_match.group(1)
                    if url.startswith('/'):
                        return base_domain + url
                    elif not url.startswith('http'):
                        return base_domain + '/' + url
                    return url
            
            return None
        except:
            return None
    
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
                print(f"❌ Could not parse AI strategy response")
                return self._get_default_strategy()
    
    def _log_strategy_results(self, ai_strategy: Dict) -> None:
        """Log detailed strategy results"""
        exploration_needed = ai_strategy.get('exploration_needed', False)
        has_billing = ai_strategy.get('current_page_has_billing', False)
        next_links = ai_strategy.get('next_links', [])
        strategy = ai_strategy.get('strategy', 'No strategy provided')
        
        print(f"🧠 AI Analysis:")
        print(f"   • Current page has billing: {has_billing}")
        print(f"   • Exploration needed: {exploration_needed}")
        print(f"   • Recommended links: {len(next_links)}")
        print(f"   • Strategy: {strategy}")
    
    def _get_default_strategy(self) -> Dict:
        """Return default strategy when AI fails"""
        return {
            'exploration_needed': False, 
            'current_page_has_billing': False,
            'next_links': [],
            'strategy': 'AI strategy consultation failed'
        } 