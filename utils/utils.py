#!/usr/bin/env python3
"""
Utility functions for AutoBilling
Common helpers used across modules
"""

import time
import random
import re
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from .config import (
    HUMAN_DELAY, TYPING_DELAY, SPA_LOADING_SELECTORS, SPA_CONTENT_SELECTORS,
    DATE_PATTERNS, AMOUNT_PATTERNS, MIN_UTILITY_AMOUNT, MAX_UTILITY_AMOUNT,
    MAX_YEARS_BACK, MAX_YEARS_FORWARD, SPA_CONTENT_WAIT
)

@dataclass
class BillInfo:
    """Data class to store billing information"""
    previous_month: str
    previous_amount: float
    current_month: str
    current_amount: float
    account_number: Optional[str] = None
    due_date: Optional[str] = None
    all_bills: Optional[List[Dict]] = None

def human_like_delay(min_seconds: float = None, max_seconds: float = None):
    """Add random delay to simulate human behavior"""
    if min_seconds is None or max_seconds is None:
        min_seconds, max_seconds = HUMAN_DELAY
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def human_like_typing(element, text: str, delay_range: tuple = None):
    """Type text character by character with human-like delays"""
    if delay_range is None:
        delay_range = TYPING_DELAY
    
    element.clear()
    time.sleep(0.2)
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*delay_range))

def wait_for_spa_content(driver, max_wait: int = SPA_CONTENT_WAIT):
    """Wait for SPA/Angular content to load"""
    try:
        print("⏳ Waiting for SPA content to load...")
        
        # Wait for loading indicators to disappear
        try:
            WebDriverWait(driver, 5).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, SPA_LOADING_SELECTORS))
            )
        except:
            pass
        
        # Wait for content to render
        for i in range(max_wait):
            time.sleep(1.5)
            try:
                content_elements = driver.find_elements(By.CSS_SELECTOR, SPA_CONTENT_SELECTORS)
                if len(content_elements) > 2:
                    print(f"✅ SPA content loaded ({len(content_elements)} elements)")
                    return
            except:
                pass
            if i < max_wait - 1:
                print(f"⏳ Waiting for content... (attempt {i+1}/{max_wait})")
                
    except Exception as e:
        print(f"⚠️ SPA content wait error: {e}")

def generate_reliable_selector(element) -> str:
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

def extract_dates_and_amounts(text: str) -> List[Dict]:
    """Extract dates and amounts from text using regex patterns"""
    dates_found = []
    amounts_found = []
    
    # Find dates
    for date_pattern in DATE_PATTERNS:
        matches = re.finditer(date_pattern, text, re.IGNORECASE)
        for match in matches:
            dates_found.append(match.group(1))
    
    # Find amounts
    for amount_pattern in AMOUNT_PATTERNS:
        matches = re.finditer(amount_pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                amount_str = match.group(1).replace(',', '')
                amount = float(amount_str)
                if MIN_UTILITY_AMOUNT <= amount <= MAX_UTILITY_AMOUNT:
                    amounts_found.append(amount)
            except:
                continue
    
    # Combine dates and amounts
    transactions = []
    for date_str in dates_found:
        for amount in amounts_found:
            parsed_date = parse_date_flexible(date_str)
            if parsed_date and is_valid_utility_date(parsed_date):
                transactions.append({
                    'date': parsed_date,
                    'amount': amount,
                    'date_str': date_str
                })
    
    return transactions

def parse_date_flexible(date_str: str) -> Optional[datetime]:
    """Parse date with multiple format attempts"""
    date_formats = [
        '%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y',
        '%b %d, %Y', '%d %b %Y', '%b-%d-%Y'
    ]
    
    for date_format in date_formats:
        try:
            return datetime.strptime(date_str, date_format)
        except:
            continue
    
    # Handle 2-digit years specially (assume 2020s)
    if '/' in date_str:
        try:
            temp_date = datetime.strptime(date_str, '%m/%d/%y')
            if temp_date.year < 2000:  # Convert 1900s to 2000s
                corrected_year = temp_date.year + 100
                return temp_date.replace(year=corrected_year)
            return temp_date
        except:
            pass
    
    return None

def is_valid_utility_date(date: datetime) -> bool:
    """Check if date is reasonable for utility billing"""
    current_year = datetime.now().year
    return (current_year - MAX_YEARS_BACK) <= date.year <= (current_year + MAX_YEARS_FORWARD)

def extract_account_number_from_url(url: str) -> Optional[str]:
    """Extract account number from URL using common patterns"""
    account_patterns = [
        r'/(\d{2,}-\d{4,}-\d{2,})',  # XX-XXXX-XX format
        r'/(\d{8,})',  # 8+ digit account numbers
    ]
    
    for pattern in account_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def find_elements_by_multiple_selectors(driver, selectors: List[str]):
    """Find elements using multiple CSS selectors"""
    elements = []
    for selector in selectors:
        try:
            found = driver.find_elements(By.CSS_SELECTOR, selector)
            elements.extend(found)
        except:
            continue
    return elements

def is_element_visible_and_enabled(element) -> bool:
    """Check if element is both visible and enabled"""
    try:
        return element.is_displayed() and element.is_enabled()
    except:
        return False

def get_element_text_content(element) -> str:
    """Get clean text content from element"""
    try:
        text = element.text.strip()
        if not text:
            text = element.get_attribute('value') or ''
        return text
    except:
        return ''

def clean_amount_string(amount_str: str) -> float:
    """Clean and convert amount string to float"""
    try:
        # Remove currency symbols and commas
        cleaned = re.sub(r'[^\d.]', '', amount_str)
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

def has_meaningful_billing_data(bill_info: BillInfo) -> bool:
    """Check if BillInfo contains meaningful billing data"""
    try:
        # Check for comprehensive historical data
        if hasattr(bill_info, 'all_bills') and bill_info.all_bills:
            return len(bill_info.all_bills) > 0
        
        # List of non-meaningful data indicators
        empty_indicators = [
            "No data found", "Error", "Screenshot failed", "Vision AI found no data",
            "No driver", "API extraction needs driver", "No APIs found", 
            "No API endpoints detected", "HTML extraction failed", "Vision extraction failed",
            "No billing data found", "Exploration complete"
        ]
        
        # Check if current_month contains error/empty indicators
        if bill_info.current_month in empty_indicators:
            return False
            
        # Check for basic billing data (must have positive amounts)
        if (bill_info.current_amount > 0 or bill_info.previous_amount > 0):
            return True
            
        return False
    except:
        return False

def deduplicate_transactions(transactions: List[Dict]) -> List[Dict]:
    """Remove duplicate transactions using month/day/amount combination"""
    unique_data = {}
    
    for item in transactions:
        # Create unique key using month, day, and amount
        month_day = item['date'].strftime('%m-%d')
        key = (month_day, item['amount'], item.get('type', 'bill'))
        
        if key not in unique_data:
            unique_data[key] = item
        else:
            # Keep the one with the more recent/realistic year
            existing_year = unique_data[key]['date'].year
            current_year = datetime.now().year
            
            # Prefer dates closer to current year
            if abs(item['date'].year - current_year) < abs(existing_year - current_year):
                unique_data[key] = item
            # If same distance, keep the one with better description
            elif (abs(item['date'].year - current_year) == abs(existing_year - current_year) and
                  len(item.get('description', '')) > len(unique_data[key].get('description', ''))):
                unique_data[key] = item
    
    return list(unique_data.values())

def truncate_html_content(html_content: str, max_length: int = 15000) -> str:
    """Truncate HTML content for AI processing"""
    return html_content[:max_length] if len(html_content) > max_length else html_content 