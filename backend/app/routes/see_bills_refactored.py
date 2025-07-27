"""see_bills_refactored.py

Clean, phased implementation of utility-bill extraction.
The original `see_bills.py` grew organically; this file narrows the
scope to one clear goal: log in & return the latest bill amount/date.

Major design points
───────────────────
• Analyze page HTML first to understand structure
• Use AI to discover login selectors dynamically
• Handle different login patterns (modal, separate page, in-place)
• Strict validation – no placeholder amounts

Usage
-----
python see_bills_refactored.py
"""

from __future__ import annotations

import asyncio, json, os, re, time, base64
from pathlib import Path
from typing import Dict, Optional, List
import logging

from playwright.async_api import async_playwright, Page
import yaml
# Import existing LLM infrastructure
import ollama
# from see_bills import analyze_with_ai, get_prompt, parse_login_selectors_json

import requests

# Set up logging to work with FastAPI
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CACHE_PATH = Path(__file__).with_suffix(".selector_cache.json")
PLACEHOLDER_AMOUNTS = {"$123.45", "$99.99", "$25", "$25.00", "$0.00"}
DEFAULT_VIEWPORT = {"width": 1280, "height": 800}

# Timeout settings for complex utility sites
PAGE_TIMEOUT = 180000  # 3 minutes for page loads (increased from 60 seconds)
NAVIGATION_TIMEOUT = 180000  # 3 minutes for navigation (increased from 60 seconds)
FORM_TIMEOUT = 60000  # 1 minute for form interactions (increased from 30 seconds)

# Test credentials
URL = "https://account.municipalonlinepayments.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3Dwww.municipalonlinepayments.com%26redirect_uri%3Dhttps%253A%252F%252Fflowermoundtx.municipalonlinepayments.com%252Fsignin-oidc%26response_type%3Dcode%2520id_token%2520token%26scope%3Dopenid%2520profile%2520email%26state%3DOpenIdConnect.AuthenticationProperties%253D7W-E_CE6l_odcCm-Bt7nfM5z8usKURcgTpdPEGkzcftFD6DQUd1rMCVTTwWf5_kAA9XQsLKoCsgWiGzcjOopvCnNjDvTjMfz5Vq2mMYiMcXw5clVngzFz4J0NgPMot2dkrRFoiU5yv_lEUrXAs_lH-X544OSb2PuIh4qEp7i7w_MxkSc15rs_Ac4pIomPXmznA-2r_00UJFZ62K_xxuefcuSb4fzl-48azlXlrWJpz5b8CCofO6Ej5gfqoDX-Ea1woTAlaSdiIRL-_V1H1HxbmBJk25DXqH0eeH_snqvE3YVMVXGQRO9daOZl7b90rJJanvDVNiryMiOkWKlg4HQ3yR4P5s%26response_mode%3Dform_post%26nonce%3D638871806911928078.M2QyNTcwNTEtZGFjZi00M2EyLTlhZDktZThlYjA0OGJkOWU5OTAyYTY3YmQtZGM3Ny00YWZmLWJmNjQtZTZhMzhjOWViNWZi%26site%3Dflowermoundtx%26x-client-SKU%3DID_NET461%26x-client-ver%3D5.5.0.0"
# URL='https://coserv.smarthub.coop/ui/#/login'
USERNAME = "vygemnguyen@gmail.com"
PASSWORD = "Dancingapple42!"

# ---------------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------------

def clear_cache():
    """Clear the selector cache for debugging"""
    try:
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()
            logger.info("Cache cleared")
    except Exception as e:
        logger.error("Failed to clear cache: %s", e)

def load_cache() -> Dict[str, Dict[str, str]]:
    try:
        return json.loads(CACHE_PATH.read_text())
    except Exception:
        return {}

def save_cache(cache: dict):
    CACHE_PATH.write_text(json.dumps(cache, indent=2))

def _is_placeholder(val: str) -> bool:
    return val.strip() in PLACEHOLDER_AMOUNTS if val else False

def clean_html_for_analysis(html: str) -> str:
    """Extract only relevant elements for login analysis"""
    # Keep forms, inputs, buttons, links, and any element with login-related text
    patterns = [
        r'<form[^>]*>.*?</form>',
        r'<input[^>]*>',
        r'<button[^>]*>.*?</button>',
        r'<a[^>]*>.*?</a>',
        r'<[^>]*(?:login|sign|user|pass|email)[^>]*>.*?</[^>]*>',
        # Angular/Material components
        r'<mat-form-field[^>]*>.*?</mat-form-field>',
        r'<cml-text-box[^>]*>.*?</cml-text-box>',
        r'<cml-toggleable-obscured-text-box[^>]*>.*?</cml-toggleable-obscured-text-box>',
        r'<app-login[^>]*>.*?</app-login>',
        r'<app-login-container[^>]*>.*?</app-login-container>',
        # Any custom component that might contain inputs
        r'<[^>]*-text-box[^>]*>.*?</[^>]*>',
        r'<[^>]*-input[^>]*>.*?</[^>]*>',
        r'<[^>]*-field[^>]*>.*?</[^>]*>',
    ]
    
    important_elements = []
    for pattern in patterns:
        matches = re.findall(pattern, html, flags=re.DOTALL | re.IGNORECASE)
        important_elements.extend(matches)
    
    # If we found important elements, use those; otherwise use cleaned full content
    if important_elements:
        cleaned_content = '\n'.join(important_elements)
        logger.info("Extracted %s important HTML elements for AI analysis", len(important_elements))
    else:
        # Fallback: use cleaned full content but limit size
        cleaned_content = html[:8000]  # Limit to 8000 characters
        logger.info("Using cleaned full HTML content (limited to 8000 characters)")
    
    return cleaned_content

def clean_html_for_billing_analysis(html: str) -> str:
    """Extract relevant elements for billing analysis - focus on content, not forms"""
    # Remove script and style tags that might confuse AI
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Keep elements that might contain billing information
    billing_patterns = [
        # Main content areas
        r'<main[^>]*>.*?</main>',
        r'<div[^>]*class[^>]*>.*?</div>',
        r'<section[^>]*>.*?</section>',
        r'<article[^>]*>.*?</article>',
        
        # Dashboard and billing specific elements
        r'<[^>]*(?:dashboard|billing|account|payment|balance)[^>]*>.*?</[^>]*>',
        r'<[^>]*(?:card|panel|widget)[^>]*>.*?</[^>]*>',
        
        # Elements containing dollar amounts or dates
        r'<[^>]*>\s*\$[^<]*</[^>]*>',
        r'<[^>]*>\s*\d{1,2}/\d{1,2}/\d{4}[^<]*</[^>]*>',
        r'<[^>]*>\s*\d{1,2}-\d{1,2}-\d{4}[^<]*</[^>]*>',
        
        # Tables and lists that might contain billing data
        r'<table[^>]*>.*?</table>',
        r'<ul[^>]*>.*?</ul>',
        r'<ol[^>]*>.*?</ol>',
        
        # Angular/Material components that might show billing info
        r'<mat-card[^>]*>.*?</mat-card>',
        r'<mat-panel[^>]*>.*?</mat-panel>',
        r'<app-[^>]*>.*?</app-[^>]*>',
    ]
    
    important_elements = []
    for pattern in billing_patterns:
        matches = re.findall(pattern, html, flags=re.DOTALL | re.IGNORECASE)
        important_elements.extend(matches)
    
    # If we found important elements, use those; otherwise use a larger chunk of the page
    if important_elements:
        cleaned_content = '\n'.join(important_elements)
        logger.info("Extracted %s billing-related HTML elements for AI analysis", len(important_elements))
    else:
        # Fallback: use a larger portion of the page content
        cleaned_content = html[:15000]  # Larger limit for billing analysis
        logger.info("Using larger HTML content chunk for billing analysis (limited to 15000 characters)")
    
    return cleaned_content

def load_prompts_from_yaml(yaml_path: str = None) -> dict:
    """Load prompts from YAML file."""
    if yaml_path is None:
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        yaml_path = script_dir / "prompts.yaml"
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            return data.get('prompts', {})
    except Exception as e:
        logger.error(f"Failed to load prompts from {yaml_path}: {e}")
        return {}

def parse_login_selectors(ai_response: str) -> Dict[str, str]:
    """Extract login selectors from AI response"""
    # Look for JSON in the response
    json_match = re.search(r'\{[^}]*"username"[^}]*\}', ai_response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass
    
    # Fallback: extract individual selectors
    selectors = {}
    patterns = {
        'username': r'username["\s]*:["\s]*["\']([^"\']+)["\']',
        'password': r'password["\s]*:["\s]*["\']([^"\']+)["\']',
        'submit': r'submit["\s]*:["\s]*["\']([^"\']+)["\']',
        'login_link': r'login_link["\s]*:["\s]*["\']([^"\']+)["\']',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, ai_response, re.IGNORECASE)
        if match:
            selectors[key] = match.group(1)
    
    return selectors

def get_prompt(prompt_key: str, yaml_path: str = None) -> str:
    """Get a prompt by its key from the YAML file."""
    prompts = load_prompts_from_yaml(yaml_path)
    prompt_data = prompts.get(prompt_key, {})
    
    if isinstance(prompt_data, dict):
        return prompt_data.get('prompt', "Please analyze this content and provide helpful information.")
    else:
        return "Please analyze this content and provide helpful information."

def parse_login_selectors_json(ai_response: str) -> dict:
    """Attempt to slice a JSON object out of the LLM response and return it.

    Expected keys: username, password, submit (optional).  Returns empty dict
    if parsing fails.
    """
    import json as _json, re as _re

    start = ai_response.find('{')
    end = ai_response.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        json_blob = ai_response[start:end + 1]
        return _json.loads(json_blob)
    except Exception:
        # Sometimes the model outputs markdown fences or trailing text; try to
        # strip non-json characters.
        cleaned = _re.sub(r'```.*?```', '', json_blob, flags=_re.S)
        try:
            return _json.loads(cleaned)
        except Exception:
            return {}

# ---------------------------------------------------------------------------
# PHASE 1 – Analyze page and discover login elements
# ---------------------------------------------------------------------------

async def analyze_page_for_login(page: Page, url: str) -> Dict[str, str]:
    """Analyze the page HTML to find login-related elements"""
    logger.info("=== ANALYZE_PAGE_FOR_LOGIN START ===")
    host = re.sub(r"^https?://", "", url).split("/")[0]
    cache = load_cache()
    
    if host in cache:
        logger.info("Using cached selectors for %s", host)
        return cache[host]
    
    logger.info("Analyzing page structure for login elements...")
    
    # Get page HTML
    logger.info("Getting page HTML...")
    html = await page.content()
    logger.info(f"Page HTML length: {len(html)} characters")
    cleaned_html = clean_html_for_analysis(html)
    logger.info(f"Cleaned HTML length: {len(cleaned_html)} characters")
    
    # Try AI analysis first
    logger.info("Starting AI analysis...")
    selectors = await analyze_with_ai_for_selectors(cleaned_html)
    
    # Fallback to heuristics if AI fails
    if not selectors:
        logger.info("AI analysis failed, falling back to heuristics")
        selectors = await discover_heuristic_selectors(page, cleaned_html)
    
    if selectors:
        cache[host] = selectors
        save_cache(cache)
        logger.info("Discovered selectors: %s", selectors)
    
    logger.info("=== ANALYZE_PAGE_FOR_LOGIN END ===")
    return selectors

async def analyze_with_ai_for_selectors(html: str) -> Dict[str, str]:
    """Use AI to analyze HTML and find login selectors"""
    logger.info("=== ANALYZE_WITH_AI_FOR_SELECTORS START ===")
    try:
        # Use the existing LLM infrastructure with enhanced prompt
        logger.info("Loading prompt from YAML...")
        selector_prompt = get_prompt('login_selectors')
        
        # Add specific guidance for Angular/Material components
        enhanced_prompt = f"""
{selector_prompt}

IMPORTANT: Look for complex nested selectors, especially:
- Angular components like <cml-text-box>, <mat-form-field>
- Material Design components with nested input structures
- Custom components that wrap standard input elements
- XPath-style selectors if CSS selectors are too complex

The HTML may contain complex nested structures. Find the actual input elements even if they're deeply nested.
"""
        
        logger.info("Calling AI analysis...")
        ai_response = analyze_with_ai(enhanced_prompt, html_content=html)
        logger.info(f"AI response length: {len(ai_response)} characters")
        
        # Parse the AI response to extract selectors
        logger.info("Parsing AI response...")
        selectors = parse_login_selectors_json(ai_response)
        
        if selectors:
            logger.info("AI found selectors: %s", selectors)
        else:
            logger.warning("AI analysis returned no valid selectors")
            # Log a sample of the HTML for debugging
            logger.debug("HTML sample for debugging: %s", html[:500])
        
        logger.info("=== ANALYZE_WITH_AI_FOR_SELECTORS END ===")
        return selectors
        
    except Exception as e:
        logger.error("AI analysis failed: %s", e)
        logger.info("=== ANALYZE_WITH_AI_FOR_SELECTORS FAILED ===")
        return {}

async def discover_heuristic_selectors(page, html: str) -> Dict[str, str]:
    """Heuristic selector discovery (placeholder for AI analysis)"""
    selectors = {}
    
    # Debug: show all input fields on the page
    all_inputs = await page.locator('input').all()
    logger.info("Found %s input fields on page", len(all_inputs))
    for i, inp in enumerate(all_inputs[:5]):  # Show first 5
        try:
            input_type = await inp.get_attribute('type') or 'no-type'
            input_name = await inp.get_attribute('name') or 'no-name'
            input_id = await inp.get_attribute('id') or 'no-id'
            input_placeholder = await inp.get_attribute('placeholder') or 'no-placeholder'
            logger.info("Input %s: type='%s', name='%s', id='%s', placeholder='%s'", 
                       i, input_type, input_name, input_id, input_placeholder)
        except:
            pass
    
    # Common patterns for login elements
    username_patterns = [
        'input[type="email"]',
        'input[name*="email"]',
        'input[name*="user"]',
        'input[placeholder*="email"]',
        'input[placeholder*="user"]',
        'input[placeholder*="username"]',
        'input[id*="email"]',
        'input[id*="user"]',
        'input[type="text"]',  # Many sites use type="text" for username
        'input[name="username"]',
        'input[name="login"]',
        'input[name="account"]',
        'input[autocomplete="username"]',
        'input[autocomplete="email"]',
        # Angular/Material patterns
        'input[formcontrolname*="user"]',
        'input[formcontrolname*="email"]',
        'input[formcontrolname*="login"]',
        'mat-form-field input',
        'input[matinput]',
        # Complex nested patterns
        'cml-text-box input',
        'cml-text-box mat-form-field input',
        'mat-form-field div input',
        'form input[type="text"]:first-child',
    ]
    
    password_patterns = [
        'input[type="password"]',
        'input[name*="pass"]',
        'input[placeholder*="pass"]',
        # Angular/Material patterns
        'input[formcontrolname*="pass"]',
        'mat-form-field input[type="password"]',
        # Complex nested patterns
        'cml-toggleable-obscured-text-box input',
        'cml-toggleable-obscured-text-box mat-form-field input',
        'form input[type="password"]',
    ]
    
    submit_patterns = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Sign In")',
        'button:has-text("Login")',
        'button:has-text("Submit")',
        # Angular/Material patterns
        'button[mat-raised-button]',
        'button[mat-button]',
        'button[mat-flat-button]',
        'button.mat-raised-button',
        'button.mat-button',
        'button.mat-flat-button',
        'cml-button-with-loading-spinner button',
        'button:has-text("SIGN IN")',
        'button:has-text("LOGIN")',
    ]
    
    login_link_patterns = [
        'a:has-text("Sign In")',
        'a:has-text("Login")',
        'button:has-text("Sign In")',
        'button:has-text("Login")',
        '[onclick*="login"]',
        '[href*="login"]',
        # Angular/Material patterns
        'button:has-text("SIGN IN")',
        'button:has-text("LOGIN")',
        'cml-button-with-loading-spinner button',
    ]
    
    # Test each pattern
    for pattern in username_patterns:
        if await page.locator(pattern).count() > 0:
            selectors['username'] = pattern
            logger.info("Found username selector: %s", pattern)
            break
    
    # Fallback: if no username found, try any input that's not password
    if 'username' not in selectors:
        non_password_inputs = await page.locator('input:not([type="password"])').all()
        if len(non_password_inputs) > 0:
            # Use the first non-password input as username
            selectors['username'] = 'input:not([type="password"]):nth-child(1)'
            logger.info("Fallback: using first non-password input as username")
    
    for pattern in password_patterns:
        if await page.locator(pattern).count() > 0:
            selectors['password'] = pattern
            logger.info("Found password selector: %s", pattern)
            break
    
    for pattern in submit_patterns:
        if await page.locator(pattern).count() > 0:
            selectors['submit'] = pattern
            logger.info("Found submit selector: %s", pattern)
            break
    
    # Fallback: if no submit found, try any button
    if 'submit' not in selectors:
        buttons = await page.locator('button').all()
        if len(buttons) > 0:
            selectors['submit'] = 'button:nth-child(1)'
            logger.info("Fallback: using first button as submit")
    
    for pattern in login_link_patterns:
        if await page.locator(pattern).count() > 0:
            selectors['login_link'] = pattern
            logger.info("Found login link selector: %s", pattern)
            break
    
    return selectors

# ---------------------------------------------------------------------------
# PHASE 2 – Perform login
# ---------------------------------------------------------------------------

async def perform_login(
    page: Page,
    selectors: Dict[str, str],
    username: str,
    password: str,
) -> bool:
    """Perform login using discovered selectors"""
    logger.info("=== PERFORM_LOGIN START ===")
    logger.info(f"Selectors: {selectors}")
    
    username_sel = selectors.get('username')
    password_sel = selectors.get('password')
    submit_sel = selectors.get('submit')
    login_link_sel = selectors.get('login_link')
    
    if not all([username_sel, password_sel, submit_sel]):
        logger.error("Missing required login selectors: username=%s, password=%s, submit=%s", 
                    username_sel, password_sel, submit_sel)
        return False
    
    # Step 1: Check if login form is already visible
    logger.info("Checking if login form is visible...")
    username_field = page.locator(username_sel).first
    password_field = page.locator(password_sel).first
    submit_btn = page.locator(submit_sel).first
    
    form_visible = (
        await username_field.count() > 0 and 
        await password_field.count() > 0 and 
        await submit_btn.count() > 0
    )
    
    if form_visible:
        logger.info("Login form already visible - proceeding directly")
    else:
        # Step 2: Login form not visible, need to click login button
        if login_link_sel:
            logger.info("Login form not visible, clicking login link: %s", login_link_sel)
            await page.click(login_link_sel)
            
            # Wait for either navigation OR form to appear
            try:
                logger.info("Waiting for login form to appear...")
                await asyncio.wait_for(
                    asyncio.wait([
                        page.wait_for_load_state("networkidle"),
                        username_field.wait_for(state="visible"),
                        password_field.wait_for(state="visible"),
                        submit_btn.wait_for(state="visible"),
                    ], return_when=asyncio.FIRST_COMPLETED),
                    timeout=FORM_TIMEOUT / 1000  # Convert to seconds
                )
                logger.info("Login form appeared after clicking login link")
            except Exception:
                logger.error("Login form not found after clicking login link")
                return False
        else:
            logger.error("No login link found and login form not visible")
            return False
    
    # Step 3: Ensure form is visible and fill credentials
    logger.info("Ensuring form fields are visible...")
    try:
        await username_field.wait_for(state="visible", timeout=FORM_TIMEOUT)
        logger.info("Username field visible")
        await password_field.wait_for(state="visible", timeout=FORM_TIMEOUT)
        logger.info("Password field visible")
        await submit_btn.wait_for(state="visible", timeout=FORM_TIMEOUT)
        logger.info("Submit button visible")
    except Exception:
        logger.error("Login form fields not visible")
        return False
    
    # Step 4: Fill and submit
    logger.info("Filling login form...")
    await username_field.fill(username)
    logger.info("Username filled")
    await password_field.fill(password)
    logger.info("Password filled")
    await submit_btn.click()
    logger.info("Submit button clicked")
    
    # Step 5: Wait for login to complete and check what happened
    logger.info("Waiting for login response...")
    try:
        await page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
        logger.info("Login response received")
    except Exception as e:
        # Some portals keep long-polling or firing analytics requests – "networkidle" may never be reached.
        logger.warning("Network idle state not reached within %sms (reason: %s). Continuing with extraction anyway.", NAVIGATION_TIMEOUT, e)
        # Give the SPA a moment to render dynamic content even if networkidle didn't fire.
        await asyncio.sleep(3)
        logger.info("Extra wait completed")
    
    # Step 6: Check if login was successful FIRST (before looking for errors)
    current_url = page.url
    current_title = await page.title()
    
    logger.info("After submit - URL: %s", current_url)
    logger.info("After submit - Title: %s", current_title)
    
    # Check for success indicators (URL change OR content change)
    logger.info("Checking for success indicators...")
    success_indicators = [
        # URL-based success (traditional sites)
        "login" not in current_url.lower() and "signin" not in current_url.lower(),
        
        # Content-based success (SPAs)
        await page.locator('text=/dashboard/i').count() > 0,
        await page.locator('text=/account/i').count() > 0,
        await page.locator('text=/welcome/i').count() > 0,
        await page.locator('text=/logout/i').count() > 0,
        await page.locator('text=/profile/i').count() > 0,
        await page.locator('text=/billing/i').count() > 0,
        await page.locator('text=/payment/i').count() > 0,
        
        # Angular/Material specific success indicators
        await page.locator('app-dashboard').count() > 0,
        await page.locator('app-account').count() > 0,
        await page.locator('app-billing').count() > 0,
    ]
    
    if any(success_indicators):
        logger.info("Login appears successful (URL or content changed)")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)  # Wait an extra 3 seconds for all content to load
        logger.info("=== PERFORM_LOGIN SUCCESS ===")
        return True
    
    # Only look for errors if we're still on login page
    logger.info("Still on login page, checking for error messages...")
    
    # Check for error messages
    error_selectors = [
        'text=/error/i',
        'text=/invalid/i', 
        'text=/incorrect/i',
        'text=/failed/i',
        '.error',
        '.alert',
        '[class*="error"]',
        '[class*="alert"]',
        '[role="alert"]',
        'mat-error',
        '.mat-error',
    ]
    
    for error_sel in error_selectors:
        try:
            error_elem = page.locator(error_sel).first
            if await error_elem.count() > 0:
                error_text = await error_elem.text_content()
                if error_text and error_text.strip():
                    # Only treat as error if it's actually a login-related error
                    error_lower = error_text.lower()
                    login_error_keywords = ['invalid', 'incorrect', 'failed', 'error', 'wrong', 'not found']
                    
                    if any(keyword in error_lower for keyword in login_error_keywords):
                        logger.error("Login error detected: '%s'", error_text.strip())
                        return False
                    else:
                        logger.info("Ignoring non-login message: '%s'", error_text.strip())
        except:
            pass
    
    # Check if there are additional required fields we missed
    all_inputs = await page.locator('input').all()
    logger.info("Checking for additional required fields...")
    for i, inp in enumerate(all_inputs):
        try:
            input_type = await inp.get_attribute('type') or 'no-type'
            input_name = await inp.get_attribute('name') or 'no-name'
            input_id = await inp.get_attribute('id') or 'no-id'
            input_placeholder = await inp.get_attribute('placeholder') or 'no-placeholder'
            input_required = await inp.get_attribute('required')
            input_value = await inp.input_value()
            
            if input_required or 'required' in str(input_placeholder).lower():
                logger.warning("Required field found: type='%s', name='%s', id='%s', placeholder='%s', value='%s'", 
                             input_type, input_name, input_id, input_placeholder, input_value)
        except:
            pass
    
    logger.error("Still on login page after submit")
    logger.info("=== PERFORM_LOGIN FAILED ===")
    return False

# ---------------------------------------------------------------------------
# PHASE 3 – Extract bill directly from current page (skip navigation)
# ---------------------------------------------------------------------------
def analyze_with_ai(prompt: str,
                    screenshot_path: str | None = None,
                    html_content: str | None = None) -> str:
    """Run two specialised AI calls and merge their answers.

    • DeepSeek-R1 (text-only) → receives the cleaned HTML when provided.
    • Llama-3 Vision          → receives the screenshot when provided.

    By returning a single concatenated string we keep *all existing callers*
    unchanged while boosting accuracy for textual selectors and retaining
    visual understanding for screenshots.
    """

    logger.info("🔍 Analyzing content with AI (DeepSeek-R1 for HTML, Llama-Vision for screenshot)…")

    try:
        combined_parts: list[str] = []

        # --- HTML → DeepSeek -------------------------------------------------
        if html_content:
            logger.info("Starting DeepSeek-R1 analysis for HTML...")
            html_prompt = f"{prompt}\n\nHTML Content:\n{html_content}"
            ds_messages = [{
                'role': 'user',
                'content': html_prompt
            }]

            # Prefer the locally-available tag. If you later pull a different
            # DeepSeek-R1 variant you can change this in one place.
            deepseek_tag = "deepseek-r1:1.5b"
            try:
                logger.info(f"Calling DeepSeek with model: {deepseek_tag}")
                ds_response = ollama.chat(
                    model=deepseek_tag,
                    messages=ds_messages
                )
                logger.info("DeepSeek-R1 call completed successfully")
            except Exception as ds_err:
                # Fallback to generic tag if the specific one is missing.
                logger.warning(f"⚠️ DeepSeek tag {deepseek_tag} not found: {ds_err}; falling back to 'deepseek-r1:latest'.")
                ds_response = ollama.chat(
                    model="deepseek-r1:latest",
                    messages=ds_messages
                )
                logger.info("DeepSeek-R1 fallback call completed successfully")

            html_result = ds_response['message']['content']
            combined_parts.append(f"HTML_ANALYSIS:\n{html_result}")

        # --- Screenshot → Llama-Vision --------------------------------------
        if screenshot_path:
            logger.info("Starting Llama-Vision analysis for screenshot...")
            lv_messages = [{
                'role': 'user',
                'content': prompt,
                'images': [screenshot_path]
            }]

            logger.info("Calling Llama-Vision...")
            lv_response = ollama.chat(
                model="llama3.2-vision:latest",
                messages=lv_messages
            )
            logger.info("Llama-Vision call completed successfully")

            image_result = lv_response['message']['content']
            combined_parts.append(f"IMAGE_ANALYSIS:\n{image_result}")

        # --------------------------------------------------------------------
        result = "\n\n".join(combined_parts) if combined_parts else "No analysis run."

        logger.info(f"AI Analysis Result:\n{result[:400]}…")
        return result

    except Exception as e:
        logger.error(f"❌ Error in AI analysis: {e}")
        return f"Error: {str(e)}"

def extract_bill_by_label_context(visible_text: str) -> str:
    """Extract the dollar amount labeled as 'Current Bill Amount' from visible text."""
    lines = [line.strip() for line in visible_text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if 'current bill amount' in line.lower():
            # Try to find a dollar amount on this line or the next
            for j in [i, i+1]:
                if j < len(lines):
                    match = re.search(r'\$\d{1,4}(?:\.\d{2})?', lines[j])
                    if match:
                        candidate = match.group(0)
                        if not _is_placeholder(candidate):
                            logger.info("[LabelContext] Found 'Current Bill Amount': %s on line %s", candidate, j)
                            return candidate
    return None

async def save_screenshot_for_analysis(page: Page, screenshot_type: str = "post_login") -> str:
    """Save a screenshot for manual analysis and return the path."""
    import os
    import time
    os.makedirs("screenshots", exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"screenshots/{screenshot_type}_{timestamp}.png"
    await page.screenshot(path=screenshot_path, full_page=True)
    logger.info(f"Screenshot saved to {screenshot_path} for vision analysis")
    return screenshot_path

def call_ollama_vision(image_path: str, prompt: str, model: str = "llama3.2-vision:latest") -> str:
    """Send screenshot to Ollama vision model and return the response (using Python client)."""
    import ollama
    
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                    'images': [image_data]
                }
            ]
        )
        return response['message']['content']
    except Exception as e:
        logger.error(f"Vision model call failed: {e}")
        return "N/A"

async def extract_bill(page: Page) -> Dict[str, str]:
    """Extract billing information using vision LLM and text/regex fallback."""
    logger.info("Extracting billing data from current page...")
    
    # Save screenshot for vision analysis
    screenshot_path = await save_screenshot_for_analysis(page, "billing_analysis")
    
    # Vision prompt
    vision_prompt = (
        "Look at this utility bill screenshot and extract:\n"
        "1. The current bill amount (e.g., $XXX.XX)\n"
        "2. The bill month (e.g., XXX XXXX). The bill month is the month before the due date.\n"
        "3. The due date (format: MM/DD/YYYY)\n\n"
        "Return the information in this format:\n"
        "Amount: $XXX.XX\n"
        "Bill Month: XXX XXXX\n"
        "Due Date: MM/DD/YYYY\n\n"
        "If you cannot find any of these, use 'N/A' for that field."
    )
    try:
        vision_result = call_ollama_vision(screenshot_path, vision_prompt)
        logger.info(f"Vision model result: {vision_result}")
        match = re.search(r'\$[\d,]{1,7}(?:\.\d{2})?', vision_result)
        if match and not _is_placeholder(match.group(0)):
            logger.info(f"Using vision model result as bill amount: {match.group(0)}")
            amount = match.group(0)
        else:
            logger.info("Vision model did not return a valid amount, falling back to text extraction.")
            amount = "N/A"
    except Exception as e:
        logger.error(f"Vision model call failed: {e}")
        amount = "N/A"
    
    # Fallback: text/regex extraction if vision fails
    if amount in ("N/A", "", None) or _is_placeholder(amount):
        try:
            visible_text = await page.locator('body').text_content()
            # logger.info("Page visible text (first 500 chars): {}", visible_text[:500] if visible_text else "No text found")
            if visible_text:
                amount_match = re.search(r'\$([\d,]+(?:\.\d{2})?)', visible_text)
                if amount_match:
                    amount_raw = amount_match.group(1).replace(',', '')
                    amount = f"${amount_raw}"
                    if not _is_placeholder(amount):
                        logger.info("Found amount in visible text: %s", amount)
        except Exception as e:
            logger.debug(f"Error getting visible text: {e}")
    
    # Due date extraction (text-based)
    due_date = "N/A"
    try:
        visible_text = await page.locator('body').text_content()
        if visible_text:
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})', visible_text)
            if date_match:
                due_date = date_match.group(1)
                logger.info(f"Found due date: {due_date}")
    except Exception as e:
        logger.debug(f"Error extracting due date: {e}")
    
    return {
        "current_bill_amount": amount,
        "due_date": due_date,
        "url": page.url,
        "page_title": await page.title(),
        "screenshot_path": screenshot_path,
    }

async def navigate_to_bill(page: Page):
    """Navigate to billing/payment section (robust for both Flower Mound and CoServ)"""
    await page.wait_for_load_state("networkidle")
    billing_patterns = [
        # Most specific first
        'a:has-text("Utility Billing"):not([class*="disabled"]):not([class*="help"])',
        'a:has-text("Billing"):not([class*="disabled"]):not([class*="help"])',
        'a:has-text("Account"):not([class*="disabled"]):not([class*="help"])',
        'a:has-text("Payment"):not([class*="disabled"]):not([class*="help"])',
        'a:has-text("Dashboard"):not([class*="disabled"]):not([class*="help"])',
        'button:has-text("Utility Billing"):not([disabled])',
        'button:has-text("Billing"):not([disabled])',
        'button:has-text("Account"):not([disabled])',
        'button:has-text("Payment"):not([disabled])',
        'button:has-text("Dashboard"):not([disabled])',
        'li a:has-text("Utility Billing")',
        'li a:has-text("Billing")',
        'li a:has-text("Account")',
        'li a:has-text("Payment")',
        'li a:has-text("Dashboard")',
        'nav a:has-text("Utility Billing")',
        'nav a:has-text("Billing")',
        'nav a:has-text("Account")',
        'nav a:has-text("Payment")',
        'nav a:has-text("Dashboard")',
    ]
    for pattern in billing_patterns:
        try:
            link = page.locator(pattern).first
            if await link.count() > 0:
                is_visible = await link.is_visible()
                is_enabled = not await link.get_attribute('disabled')
                has_disabled_class = await link.get_attribute('class')
                if is_visible and is_enabled and 'disabled' not in str(has_disabled_class):
                    logger.info("Clicking billing link: %s", pattern)
                    await link.click()
                    await page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
                    await asyncio.sleep(2)  # Wait for navigation
                    return
                else:
                    logger.debug("Skipping disabled link: %s (visible=%s, enabled=%s, class=%s)", pattern, is_visible, is_enabled, has_disabled_class)
        except Exception as e:
            logger.debug("Error checking pattern %s: %s", pattern, e)
            continue
    logger.info("No active billing link found, staying on current page")

# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

async def run(url: str, username: str, password: str):
    logger.info("=== STARTING BILL EXTRACTION ===")
    logger.info(f"URL: {url}")
    logger.info(f"Username: {username}")
    
    async with async_playwright() as p:
        logger.info("Launching browser...")
        browser = await p.chromium.launch(headless=True)  # Keep non-headless for debugging
        context = await browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            # Increase timeouts for complex sites
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Set longer timeouts for page operations
        page.set_default_timeout(PAGE_TIMEOUT)
        page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
        logger.info(f"Set page timeout to {PAGE_TIMEOUT}ms, navigation timeout to {NAVIGATION_TIMEOUT}ms")
        
        try:
            # Phase 1: Analyze page
            logger.info("=== PHASE 1: Loading page ===")
            logger.info("Starting bill extraction for URL: %s", url)
            await page.goto(url, timeout=PAGE_TIMEOUT)
            logger.info("Page loaded successfully")
            await page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
            logger.info("Page network idle")
            
            logger.info("=== PHASE 2: Analyzing login elements ===")
            selectors = await analyze_page_for_login(page, url)
            if not selectors:
                logger.error("No login elements found")
                return {"success": False, "error": "No login elements found"}
            
            # Phase 2: Login
            logger.info("=== PHASE 3: Attempting login ===")
            logger.info("Attempting login with discovered selectors")
            login_success = await perform_login(page, selectors, username, password)
            if not login_success:
                logger.error("Login failed")
                return {"success": False, "error": "Login failed"}
            
            # Phase 3: Check for billing data on current page first
            logger.info("=== PHASE 4: Checking for billing data ===")
            logger.info("Login successful! Checking for billing data on current page...")
            
            # Wait for page to fully load after login
            logger.info("Waiting for page to fully load after login...")
            try:
                await page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
                logger.info("Page network idle after login")
            except Exception as e:
                # Some portals keep long-polling or firing analytics requests – "networkidle" may never be reached.
                logger.warning("Network idle state not reached within %sms (reason: %s). Continuing with extraction anyway.", NAVIGATION_TIMEOUT, e)
            
            # Give the SPA a moment to render dynamic content even if networkidle didn't fire.
            await asyncio.sleep(3)
            logger.info("Extra wait completed")
            
            # Try to extract billing data from current page
            logger.info("Extracting billing data from current page...")
            bill_data = await extract_bill(page)
            
            # Check if we found a valid bill amount
            if bill_data["current_bill_amount"] not in ("N/A", "", None) and not _is_placeholder(bill_data["current_bill_amount"]):
                logger.info("Bill found on current page: %s", bill_data["current_bill_amount"])
                return {"success": True, "bill": bill_data, "source": "current_page"}
            
            # Phase 4: If no billing data found, navigate to billing section
            logger.info("=== PHASE 5: Navigating to billing section ===")
            logger.info("No billing data found on current page, navigating to billing section...")
            
            # Look for billing navigation links
            billing_links = [
                'a:has-text("Utility Billing")',
                'a:has-text("Billing")',
                'a:has-text("Account")',
                'a:has-text("Payment")',
                'a:has-text("Pay Bill")',
                'a:has-text("View Bills")',
                'button:has-text("Utility Billing")',
                'button:has-text("Billing")',
                'button:has-text("Account")',
                'button:has-text("Payment")',
                'a[href*="billing"]',
                'a[href*="payment"]',
                'a[href*="account"]',
            ]
            
            navigation_success = False
            for link_selector in billing_links:
                try:
                    link = page.locator(link_selector).first
                    if await link.count() > 0 and await link.is_visible():
                        logger.info("Found billing link: %s", link_selector)
                        await link.click()
                        await page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
                        await asyncio.sleep(2)  # Wait for navigation
                        navigation_success = True
                        logger.info("Successfully navigated to billing section")
                        break
                except Exception as e:
                    logger.debug("Could not click %s: %s", link_selector, e)
                    continue
            
            if not navigation_success:
                logger.warning("Could not find or click any billing navigation links")
            
            # Phase 5: Extract billing data after navigation
            logger.info("=== PHASE 6: Extracting billing data after navigation ===")
            logger.info("Extracting billing data after navigation...")
            bill_data_nav = await extract_bill(page)
            
            if bill_data_nav["current_bill_amount"] not in ("N/A", "", None) and not _is_placeholder(bill_data_nav["current_bill_amount"]):
                logger.info("Bill found after navigation: %s", bill_data_nav["current_bill_amount"])
                return {"success": True, "bill": bill_data_nav, "source": "after_navigation"}
            
            # If still not found, return the best we have
            logger.warning("No bill found after navigation. Returning best available data.")
            return {"success": False, "bill": bill_data_nav, "error": "No bill found after navigation"}
        
        except Exception as e:
            logger.error("Error during bill extraction: %s", str(e))
            return {"success": False, "error": f"Extraction failed: {str(e)}"}
        finally:
            logger.info("Closing browser...")
            await browser.close()
            logger.info("=== BILL EXTRACTION COMPLETED ===")

# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------

# if __name__ == "__main__":
#     # Clear cache for debugging - remove this line once working
#     clear_cache()
    
#     t0 = time.time()
#     result = asyncio.run(run(URL, USERNAME, PASSWORD))
#     logger.info(result)
#     logger.info("elapsed: %ss", round(time.time()-t0, 1)) 