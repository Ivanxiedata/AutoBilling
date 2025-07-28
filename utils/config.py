#!/usr/bin/env python3
"""
Configuration module for AutoBilling
All constants and settings in one place

🎛️ USER CONTROLS:
- SHOW_BROWSER: True = see browser window, False = hidden (headless)
- DEBUG_MODE: True = detailed output, False = minimal output
- VERBOSE_OUTPUT: True = more status messages
"""

# AI Model Configuration
OLLAMA_MODEL = "qwen2.5:latest"
VISION_MODEL = "qwen2.5vl:7b"

# Browser Configuration
BROWSER_WINDOW_SIZE = "1920,1080"  # Browser window size
HEADLESS_BROWSER = False  # Set to True to hide browser window
SHOW_BROWSER = True       # Set to False to run in headless mode (same as HEADLESS_BROWSER=True)
DEBUG_MODE = True         # Set to True to see detailed debugging output
VERBOSE_OUTPUT = True     # Set to True for more detailed status messages
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Timing Configuration
LOGIN_WAIT_TIME = 5
EXPLORATION_THRESHOLD = 70
MAX_EXPLORATION_TIME = 180  # 3 minutes
SPA_CONTENT_WAIT = 3
MAX_HTML_LENGTH = 15000

# Extraction Configuration
MAX_TOTAL_TRANSACTIONS = 50
MAX_CONTAINER_TRANSACTIONS = 20
MAX_BILLING_HISTORY_MONTHS = 24

# Amount Validation
MIN_UTILITY_AMOUNT = 1.0
MAX_UTILITY_AMOUNT = 5000.0

# Date Validation
MAX_YEARS_BACK = 15
MAX_YEARS_FORWARD = 2

# Delay Ranges (for human-like behavior)
PAGE_LOAD_DELAY = (1.0, 2.0)
HUMAN_DELAY = (0.5, 2.0)
TYPING_DELAY = (0.05, 0.15)

# CSS Selectors for SPA Detection
SPA_LOADING_SELECTORS = ".loading, .spinner, mat-spinner, .mat-progress-spinner, .loading-overlay"
SPA_CONTENT_SELECTORS = "mat-card, .mat-card, [role='main'], main, .content, nav, table"

# Billing Keywords
BILLING_KEYWORDS = [
    'payment', 'charge', 'bill', 'billing', 'invoice', 'statement', 'balance', 'due', 'amount',
    'transaction', 'history', 'payment history', 'billing history', 'statement history',
    'usage', 'consumption', 'meter', 'reading', 'service', 'utility', 'energy', 'electric',
    'previous', 'current', 'period', 'cycle', 'monthly', 'annual', 'recent',
    'account', 'summary', 'overview', 'dashboard', 'my account'
]

# Navigation Keywords  
HIGH_PRIORITY_NAV = [
    'billing history', 'transaction history', 'payment history', 'billing', 'transactions',
    'bill history', 'account history', 'statement history', 'utility billing',
    'my bills', 'view bills', 'past bills', 'previous bills', 'bill pay'
]
MEDIUM_PRIORITY_NAV = [
    'account', 'usage', 'dashboard', 'statements', 'bills', 'utilities',
    'my account', 'account details', 'service history', 'usage history',
    'water bills', 'electric bills', 'gas bills', 'utility services'
]
LOW_PRIORITY_NAV = ['overview', 'home', 'summary', 'welcome']

# Chrome Options for Anti-Detection (macOS compatible)
CHROME_OPTIONS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    f"--window-size={BROWSER_WINDOW_SIZE}",
    "--disable-blink-features=AutomationControlled",
    "--disable-extensions",
    "--disable-plugins-discovery",
    "--disable-web-security",
    "--allow-running-insecure-content",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-features=VizDisplayCompositor",
    "--start-maximized",
    "--disable-infobars",
    "--disable-notifications",
    "--disable-popup-blocking",
    # macOS specific options
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=TranslateUI",
    "--disable-ipc-flooding-protection",
    # Remove problematic options that might cause crashes on macOS
    "--disable-software-rasterizer",
    "--use-mock-keychain"  # Prevent keychain access issues on macOS
]

# Regular Expression Patterns
DATE_PATTERNS = [
    r'(\d{1,2}/\d{1,2}/\d{4})',          # MM/DD/YYYY
    r'(\d{4}-\d{2}-\d{2})',              # YYYY-MM-DD  
    r'(\d{1,2}-\d{1,2}-\d{4})',          # MM-DD-YYYY
    r'(\w{3}\s+\d{1,2},?\s+\d{4})',      # Jan 15, 2024
    r'(\d{1,2}/\d{1,2}/\d{2})',          # MM/DD/YY
    r'(\d{1,2}\s+\w{3}\s+\d{4})',        # 15 Jan 2024
    r'(\w{3}-\d{1,2}-\d{4})',            # Jan-15-2024
]

AMOUNT_PATTERNS = [
    r'\$(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',          # $1,234.56
    r'(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)\s*USD',      # 1234.56 USD
    r'Amount:\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)', # Amount: $123.45
    r'Total:\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',  # Total: $123.45
]

# Common Billing URL Patterns
COMMON_BILLING_PATTERNS = [
    '/#/billing-history',
    '/#/transaction-history', 
    '/#/payment-history',
    '/#/account-history',
    '/#/billing',
    '/#/transactions',
    '/#/statements',
    '/#/bills',
    '/#/usage-history',
    '/ui/#/billing-history',
    '/ui/#/transaction-history',
    '/ui/#/billing',
    '/ui/#/transactions'
] 