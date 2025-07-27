"""
Configuration file for AutoBilling
Set your Ollama configuration here
"""

import os

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')  # Default Ollama URL
OLLAMA_MODEL = "qwen2.5:latest"  # Qwen3 latest model
OLLAMA_TIMEOUT = 120  # Timeout for Ollama requests in seconds

# Browser Configuration
HEADLESS_BROWSER = False  # Set to False to see the browser in action
BROWSER_TIMEOUT = 30     # Seconds to wait for page loads

# Scraping Configuration
MAX_HTML_LENGTH = 8000   # Maximum HTML length to send to AI (to manage tokens)
LOGIN_WAIT_TIME = 3      # Seconds to wait after login attempt
PAGE_LOAD_WAIT = 5       # Seconds to wait for pages to load after navigation

# User Agent String (to appear more like a real browser)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" 