#!/usr/bin/env python3
"""
Debug version of AutoBilling to troubleshoot login form detection
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import ollama
import json
import config

def setup_debug_driver():
    """Setup Chrome driver with debug options"""
    chrome_options = Options()
    # Don't run headless so we can see what's happening
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-agent={config.USER_AGENT}")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def save_page_content(html_content, filename):
    """Save HTML content to file for manual inspection"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"📁 Page content saved to: {filename}")

def analyze_with_ai_debug(html_content, task):
    """Debug version of AI analysis with more verbose output"""
    try:
        # Truncate HTML but show more details
        original_length = len(html_content)
        truncated_html = html_content[:config.MAX_HTML_LENGTH] if len(html_content) > config.MAX_HTML_LENGTH else html_content
        
        print(f"📄 HTML Length: {original_length} chars (using first {len(truncated_html)} chars)")
        
        prompt = f"""
        You are an expert web scraper. Analyze this HTML carefully and find login elements.
        
        Task: {task}
        
        HTML Content:
        {truncated_html}
        
        Look for:
        1. Any form elements with action="/login" or similar
        2. Input fields with type="text", type="email", name="username", name="email", etc.
        3. Input fields with type="password"
        4. Submit buttons or login buttons
        5. Any JavaScript that might load forms dynamically
        
        Respond with JSON only:
        {{
            "login_form": {{
                "found": true/false,
                "username_field": "exact selector, name, or id",
                "password_field": "exact selector, name, or id", 
                "submit_button": "exact selector, name, or id",
                "form_element": "form selector if found",
                "analysis": "brief explanation of what you found"
            }},
            "page_info": {{
                "title": "page title if visible",
                "has_forms": true/false,
                "form_count": "number of forms found",
                "has_javascript": true/false,
                "seems_like_login_page": true/false
            }}
        }}
        """
        
        print("🤖 Sending to AI for analysis...")
        response = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0.1,
                "num_predict": 1000,
                "top_p": 0.9
            }
        )
        
        response_content = response['message']['content']
        print(f"📝 Raw AI Response: {response_content}")
        
        # Try to extract JSON
        json_start = response_content.find('{')
        json_end = response_content.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_content = response_content[json_start:json_end]
            parsed = json.loads(json_content)
            print(f"✅ Parsed AI Response: {json.dumps(parsed, indent=2)}")
            return parsed
        else:
            print(f"❌ Could not parse JSON from AI response")
            return {"error": "JSON parsing failed"}
            
    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        return {"error": str(e)}

def manual_form_detection(html_content):
    """Manual form detection as backup"""
    print("\n🔍 Manual Form Detection:")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all forms
    forms = soup.find_all('form')
    print(f"📋 Found {len(forms)} form(s)")
    
    for i, form in enumerate(forms):
        print(f"\n📝 Form {i+1}:")
        print(f"   Action: {form.get('action', 'None')}")
        print(f"   Method: {form.get('method', 'None')}")
        print(f"   ID: {form.get('id', 'None')}")
        print(f"   Class: {form.get('class', 'None')}")
        
        # Find inputs in this form
        inputs = form.find_all('input')
        print(f"   Inputs: {len(inputs)}")
        for inp in inputs:
            print(f"     - Type: {inp.get('type', 'None')}, Name: {inp.get('name', 'None')}, ID: {inp.get('id', 'None')}")
    
    # Look for specific login patterns
    username_inputs = soup.find_all('input', {'type': ['text', 'email']})
    password_inputs = soup.find_all('input', {'type': 'password'})
    
    print(f"\n🔍 Found {len(username_inputs)} potential username field(s)")
    print(f"🔒 Found {len(password_inputs)} password field(s)")
    
    return {
        "forms_found": len(forms),
        "username_fields": len(username_inputs),
        "password_fields": len(password_inputs)
    }

def debug_utility_site(url):
    """Debug a utility website to see why login detection failed"""
    print(f"🐛 Debug Mode: Analyzing {url}")
    print("=" * 60)
    
    driver = None
    try:
        # Setup driver (visible browser)
        driver = setup_debug_driver()
        
        print(f"🌐 Navigating to {url}")
        driver.get(url)
        
        # Wait a bit for page to load
        time.sleep(5)
        
        print(f"📄 Current URL: {driver.current_url}")
        print(f"📝 Page Title: {driver.title}")
        
        # Get page source
        html_content = driver.page_source
        
        # Save for manual inspection
        save_page_content(html_content, "debug_page.html")
        
        # Manual form detection
        manual_results = manual_form_detection(html_content)
        
        # AI analysis
        print("\n🤖 AI Analysis:")
        ai_results = analyze_with_ai_debug(html_content, "Find login form elements")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 DEBUG SUMMARY")
        print("=" * 60)
        print(f"🌐 URL: {url}")
        print(f"📝 Title: {driver.title}")
        print(f"📋 Forms Found: {manual_results['forms_found']}")
        print(f"👤 Username Fields: {manual_results['username_fields']}")
        print(f"🔒 Password Fields: {manual_results['password_fields']}")
        
        if ai_results.get('login_form', {}).get('found'):
            print("🤖 AI Status: ✅ Login form detected")
        else:
            print("🤖 AI Status: ❌ Login form not detected")
        
        # Keep browser open for manual inspection
        input("\n⏸️  Browser will stay open for manual inspection. Press Enter to close...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        if driver:
            driver.quit()

def main():
    """Run debug analysis"""
    print("🐛 AutoBilling Debug Tool")
    print("=" * 40)
    
    url = input("🌐 Enter utility website URL to debug: ").strip()
    if not url:
        print("❌ URL required!")
        return
    
    debug_utility_site(url)

if __name__ == "__main__":
    main() 