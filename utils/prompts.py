#!/usr/bin/env python3
"""
Prompt Library for AutoBilling
Centralized collection of AI prompts used throughout the system
"""

class PromptLibrary:
    """Collection of AI prompts for various AutoBilling tasks"""
    
    # Login Detection Prompts
    LOGIN_FORM_DETECTION = """
    You are a login form detection expert. Analyze this HTML and return ONLY valid JSON.

    HTML:
    {html_content}

    Find these elements:
    1. Username/email input field  
    2. Password input field
    3. Submit button

    CRITICAL: Return ONLY the JSON below with no explanations or extra text:

    {{
        "found": true/false,
        "username_field": "CSS selector or null",
        "password_field": "CSS selector or null", 
        "submit_button": "CSS selector or null",
        "confidence": 0-100
    }}
    """
    
    # Navigation and Link Discovery Prompts
    BILLING_LINK_RANKING = """
    Rank these utility billing links by relevance to billing history/transactions:
    
    {links_data}
    
    Rank from highest to lowest priority for utility billing data.
    
    High Priority (90-100): Transaction history, billing history, payment history
    Medium Priority (70-89): Account info, statements, usage data  
    Low Priority (50-69): General dashboard, overview pages
    
    Return JSON:
    {{
        "ranked_links": [
            {{
                "url": "full_url",
                "score": 0-100,
                "reasoning": "why ranked this way"
            }}
        ]
    }}
    """
    
    EXPLORATION_STRATEGY = """
    You are a municipal utility website expert. Analyze this page and decide exploration strategy.

    CURRENT PAGE: {current_url}
    PAGE TITLE: {page_title}
    AVAILABLE LINKS: {discovered_links}

    GOAL: Find billing transaction history with specific dates and dollar amounts.

    CRITICAL PRIORITY AREAS TO EXPLORE:
    1. **SIDEBAR NAVIGATION** (HIGHEST PRIORITY):
       - "Transactions", "Transaction History", "Billing History"
       - "Account Detail", "Account History", "My Account"  
       - "Bills", "Statements", "Payment History"
       - Navigation menus on left/right side of page

    2. **MAIN CONTENT LINKS**:
       - "View Bills", "Payment History", "Statement History"
       - "Bill Pay", "Past Bills", "Account Summary"

    3. **SECONDARY NAVIGATION**:
       - Header menus, dropdown menus, footer links
       - Links containing: /account, /billing, /history, /statements, /transactions

    EXPLORATION STRATEGY:
    - Prioritize sidebar navigation elements FIRST (score 9-10)
    - Look for navigation patterns typical of utility websites
    - Focus on links that lead to historical data, not just current bills
    - Avoid general pages like "Home", "Contact", "Help", "Settings"

    CRITICAL: Return ONLY this JSON format:
    {{
        "current_page_has_billing": true/false,
        "exploration_needed": true/false,
        "next_links": [
            {{
                "url": "full_url",
                "text": "link_text", 
                "reason": "why this link is promising (mention if it's sidebar navigation)",
                "priority": 1-10,
                "location": "sidebar/main/header/footer"
            }}
        ],
        "strategy": "one sentence exploration plan emphasizing sidebar navigation"
    }}
    """
    
    BILLING_DATA_EVALUATION = """
    You are a utility billing data analyst. Analyze this page content to determine if it contains sufficient billing history.

    PAGE CONTENT:
    {page_content}

    EVALUATION CRITERIA:
    1. Look for billing transactions with SPECIFIC dates and dollar amounts
    2. Count how many months of billing data are visible
    3. Look for patterns like: "$123.45 - 06/15/2024", "Bill Date: May 2024", "Amount Due: $89.12"
    4. Tables, lists, or sections showing multiple billing periods

    REQUIREMENTS FOR "SUFFICIENT DATA":
    - At least 4 different months of billing data
    - Each entry must have both a date and dollar amount
    - Must be actual billing/transaction history (not just account info)

    EXAMPLES OF SUFFICIENT DATA:
    ✅ Table showing: Jan 2024 $120.50, Feb 2024 $135.20, Mar 2024 $98.75, Apr 2024 $110.25
    ✅ List of transactions spanning 4+ months with amounts
    ✅ Billing history page with dates and payment amounts

    EXAMPLES OF INSUFFICIENT DATA:
    ❌ Only current balance: "Current Amount Due: $125.50"
    ❌ Account overview without transaction history
    ❌ Only 1-2 recent bills visible
    ❌ General account information without billing details

    CRITICAL: Return ONLY this JSON format:
    {{
        "has_sufficient_billing_data": true/false,
        "months_of_data_found": 0-12,
        "data_quality": "detailed/partial/minimal/none",
        "billing_entries_found": [
            {{
                "date": "MM/YYYY or specific date found",
                "amount": "dollar amount found",
                "description": "bill description if any"
            }}
        ],
        "evaluation_reason": "specific explanation of what was found or missing"
    }}
    """
    
    URL_RANKING_COMPREHENSIVE = """
    You are an expert at identifying UTILITY BILLING HISTORY pages. Rank these URLs by their likelihood of containing comprehensive billing/transaction history.

    DISCOVERED URLS:
    {links_summary}

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
    
    # Page Analysis Prompts
    BILLING_HISTORY_PAGE_DETECTION = """
    You are analyzing a web page to determine if it contains UTILITY BILLING HISTORY or TRANSACTION HISTORY.

    PAGE CONTENT SAMPLE (first 2000 characters):
    {page_text}

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
    
    PAGE_CONTENT_ANALYSIS = """
    You are an expert at analyzing UTILITY COMPANY web pages to determine billing/transaction data relevance.
    
    CURRENT PAGE CONTENT ANALYSIS:
    {content_summary}
    
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
    
    # Data Extraction Prompts
    HTML_EXTRACTION = """
    You are a utility billing data extraction expert. Analyze this HTML and extract billing data.

    HTML:
    {html_content}

    CRITICAL REQUIREMENTS:
    1. ONLY extract the LATEST date from each month
    2. If multiple entries exist for same month (e.g., 07/24/2025 and 07/21/2025), only extract 07/24/2025
    3. Look for billing amounts with dates in ANY format: tables, divs, spans, text
    4. Handle Single Page Applications (SPA) - data might be in various elements
    5. Extract ALL visible months but only the latest date from each

    EXAMPLES OF WHAT TO EXTRACT:
    ✅ Current Bill Amount: $199.00 → Extract as latest bill
    ✅ Last Payment: $199.00 on July 17, 2025 → Extract with date
    ✅ Table rows with dates and amounts
    ✅ Dashboard billing summaries

    CRITICAL: Return ONLY valid JSON. No explanations, no extra text, no markdown.

    {{
        "bills": [
            {{
                "date": "07/17/2025", 
                "amount": 199.00,
                "description": "Latest bill for the month",
                "type": "bill"
            }}
        ],
        "account_info": {{
            "account_number": "if visible"
        }}
    }}

    If no billing data found, return: {{"bills": [], "account_info": {{}}}}

    RETURN ONLY JSON - NO OTHER TEXT.
    """
    
    VISION_AI_COMPREHENSIVE = """You are analyzing a screenshot of a utility billing website. Extract billing data with LATEST DATE PER MONTH rule.

CRITICAL RULE: For each month, only extract the LATEST date entry.

LOOK FOR:
- Current bill amounts (like $199.00, $150.46, etc.)
- Last payment amounts with dates (like "PAID on July 17, 2025")
- Bill dates in any format (07/24/2025, July 2025, etc.) 
- Dashboard billing summaries
- Account balance information
- Transaction tables or billing history
- Usage charts with billing periods

SPA/DASHBOARD EXTRACTION:
- Extract "Current Bill Amount" as latest bill
- Extract "Last Payment Amount" with its date
- Look for any visible dollar amounts with associated dates

ONLY extract the latest date from each month. Skip earlier dates in the same month.

CRITICAL: Return ONLY valid JSON. No explanations, no extra text.

{{
    "bills": [
        {{
            "date": "07/17/2025", 
            "amount": 199.00,
            "description": "Latest utility bill for the month",
            "type": "bill"
        }}
    ],
    "account_info": {{
        "account_number": "if visible"
    }}
}}

If no billing data visible, return: {{"bills": [], "account_info": {{}}}}

RETURN ONLY JSON - NO OTHER TEXT."""

    @classmethod
    def get_prompt(cls, prompt_name: str, **kwargs) -> str:
        """Get a formatted prompt by name with variables substituted"""
        if not hasattr(cls, prompt_name.upper()):
            raise ValueError(f"Prompt '{prompt_name}' not found")
        
        prompt_template = getattr(cls, prompt_name.upper())
        return prompt_template.format(**kwargs)
    
    @classmethod
    def list_prompts(cls) -> list:
        """List all available prompt names"""
        return [attr for attr in dir(cls) if attr.isupper() and not attr.startswith('_')] 