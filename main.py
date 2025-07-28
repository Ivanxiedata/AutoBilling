#!/usr/bin/env python3
"""
AutoBilling - Simple Main Interface
Clean interface for utility bill scraping
"""

import time
import ollama
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from tabulate import tabulate

from utils import (
    BillInfo, LoginHandler, SmartExtractionOrchestrator,
    OLLAMA_MODEL, HEADLESS_BROWSER, SHOW_BROWSER, USER_AGENT, CHROME_OPTIONS, 
    PAGE_LOAD_DELAY, DEBUG_MODE, VERBOSE_OUTPUT, BROWSER_WINDOW_SIZE,
    human_like_delay, has_meaningful_billing_data
)
from agents import NavigationAgent


class UtilityBillScraper:
    """Simple AI-powered utility bill scraper"""

    def __init__(self):
        self.driver = None
        if DEBUG_MODE:
            print("🔍 Verifying Ollama connection...")
            import sys
            sys.stdout.flush()
        self._verify_ollama_connection()

    def _verify_ollama_connection(self):
        """Verify Ollama is available"""
        try:
            if DEBUG_MODE:
                print(f"   • Testing connection to {OLLAMA_MODEL}...")
                import sys
                sys.stdout.flush()
            
            # Faster test with shorter timeout
            import time
            start_time = time.time()
            
            ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": "hi"}],
                options={
                    "num_predict": 1,
                    "temperature": 0,
                    "top_p": 1,
                    "timeout": 10  # 10 second timeout
                }
            )
            
            end_time = time.time()
            print(f"✅ Connected to Ollama with model: {OLLAMA_MODEL} ({end_time - start_time:.1f}s)")
            
            if DEBUG_MODE:
                print("   • Ollama connection successful")
        except Exception as e:
            print(f"❌ Ollama connection failed: {e}")
            if DEBUG_MODE:
                import traceback
                print("🐛 Ollama connection traceback:")
                traceback.print_exc()
            raise ValueError(f"Cannot connect to Ollama: {e}\nPlease ensure Ollama is running and {OLLAMA_MODEL} is available")

    def scrape_utility_bill(self, url: str, username: str, password: str) -> BillInfo:
        """Main scraping method - coordinates all components"""
        try:
            # Setup browser
            self._setup_browser()

            # Navigate to login page
            print(f"🌐 Navigating to {url}")
            if DEBUG_MODE:
                print(f"   • Loading page...")
            self.driver.get(url)
            if DEBUG_MODE:
                print(f"   • Page loaded, current URL: {self.driver.current_url}")
                print(f"   • Page title: {self.driver.title}")
            
            # Wait for page to load and JavaScript to render
            human_like_delay(*PAGE_LOAD_DELAY)
            
            # Additional wait for JavaScript-rendered forms
            if DEBUG_MODE:
                print("   • Waiting for JavaScript content to render...")
            time.sleep(3)  # Wait for dynamic content
            
            # Check if page is still loading
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.by import By
                
                # Wait for page to be ready
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                if DEBUG_MODE:
                    print("   • Page ready state: complete")
                    
            except Exception as e:
                if DEBUG_MODE:
                    print(f"   • Page ready wait failed: {e}")
            
            # Final page source after all content loads
            if DEBUG_MODE:
                final_content_length = len(self.driver.page_source)
                print(f"   • Final page content length: {final_content_length} characters")

            # Handle login
            if not self._handle_login(username, password):
                return BillInfo("Login failed", 0.0, "Could not authenticate", 0.0)

            # Post-login exploration and extraction
            return self._explore_and_extract()

        except Exception as e:
            print(f"❌ Scraping error: {e}")
            return BillInfo("Error occurred", 0.0, str(e), 0.0)
        finally:
            self._cleanup()

    def _setup_browser(self):
        """Setup Chrome browser with anti-detection measures"""
        # Determine if browser should be headless
        run_headless = HEADLESS_BROWSER or not SHOW_BROWSER
        
        if DEBUG_MODE:
            print(f"🔧 Setting up browser...")
            print(f"   • Headless mode: {run_headless}")
            print(f"   • Window size: {BROWSER_WINDOW_SIZE}")
            print(f"   • Debug mode: {DEBUG_MODE}")
            import sys
            sys.stdout.flush()
        else:
            print("🔧 Setting up browser...")

        chrome_options = Options()

        if run_headless:
            chrome_options.add_argument("--headless")
            if VERBOSE_OUTPUT:
                print("   • Running in headless mode (browser hidden)")
        else:
            if VERBOSE_OUTPUT:
                print("   • Running in windowed mode (browser visible)")

        chrome_options.add_argument(f"--user-agent={USER_AGENT}")

        # Add all anti-detection options
        for option in CHROME_OPTIONS:
            chrome_options.add_argument(option)

        # Experimental options for anti-detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        if DEBUG_MODE:
            print(f"   • Chrome options: {len(CHROME_OPTIONS)} anti-detection measures")
            print("   • Setting up ChromeDriver...")
            import sys
            sys.stdout.flush()

        # ChromeDriver setup with debugging
        try:
            if DEBUG_MODE:
                print("   • Installing/updating ChromeDriver...")
                sys.stdout.flush()
            
            # Use ChromeDriverManager with simplified setup
            from webdriver_manager.chrome import ChromeDriverManager
            
            # Get ChromeDriver path
            driver_path = ChromeDriverManager().install()
            
            if DEBUG_MODE:
                print(f"   • ChromeDriver path: {driver_path}")
                print("   • Creating browser instance...")
                sys.stdout.flush()
            
            # Create service
            service = Service(driver_path)
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            if DEBUG_MODE:
                print("   • Chrome browser created successfully")
                sys.stdout.flush()
                
        except Exception as browser_error:
            print(f"❌ Browser setup failed: {browser_error}")
            if DEBUG_MODE:
                import traceback
                print("🐛 Browser setup traceback:")
                traceback.print_exc()
                
            # Try alternative ChromeDriver setup without webdriver-manager
            print("🔄 Trying system ChromeDriver (no webdriver-manager)...")
            try:
                # Simplified options for problematic systems
                simple_options = Options()
                if run_headless:
                    simple_options.add_argument("--headless")
                simple_options.add_argument("--no-sandbox")
                simple_options.add_argument("--disable-dev-shm-usage")
                simple_options.add_argument("--disable-gpu")
                
                # Try without specifying ChromeDriver path (uses system PATH)
                try:
                    self.driver = webdriver.Chrome(options=simple_options)
                    print("✅ Using system ChromeDriver from PATH")
                except Exception as system_error:
                    print(f"❌ System ChromeDriver failed: {system_error}")
                    
                    # Final attempt: Try common paths
                    common_paths = [
                        '/usr/local/bin/chromedriver',
                        '/opt/homebrew/bin/chromedriver',
                        '/usr/bin/chromedriver'
                    ]
                    
                    for path in common_paths:
                        try:
                            import os
                            if os.path.exists(path):
                                service = Service(path)
                                self.driver = webdriver.Chrome(service=service, options=simple_options)
                                print(f"✅ Using ChromeDriver at: {path}")
                                break
                        except:
                            continue
                    else:
                        # No ChromeDriver found anywhere
                        print("❌ ChromeDriver not found. Please install ChromeDriver manually:")
                        print("  brew install chromedriver")
                        print("  or download from: https://chromedriver.chromium.org/")
                        raise browser_error
                    
            except Exception as fallback_error:
                print(f"❌ All ChromeDriver methods failed: {fallback_error}")
                raise browser_error  # Raise original error

        # Remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        if DEBUG_MODE:
            print(f"   • Browser setup complete")
            try:
                window_size = self.driver.get_window_size()
                print(f"   • Window size: {window_size}")
                print(f"   • Current URL: {self.driver.current_url}")
            except Exception as e:
                print(f"   • Could not get browser details: {e}")
            import sys
            sys.stdout.flush()

    def _handle_login(self, username: str, password: str) -> bool:
        """Handle login using LoginHandler component"""
        if DEBUG_MODE:
            print("🔐 Starting login process...")
            print(f"   • Username: {username}")
            print(f"   • Password: {'*' * len(password)}")
            
        login_handler = LoginHandler(self.driver)
        html_content = self.driver.page_source
        
        if DEBUG_MODE:
            print(f"   • Page source length: {len(html_content)} characters")

        success = login_handler.find_and_fill_login(html_content, username, password)

        if success:
            print("✅ Login successful!")
            # Wait for post-login navigation
            print("⏳ Waiting for post-login navigation...")
            if DEBUG_MODE:
                print(f"   • Current URL before wait: {self.driver.current_url}")
            time.sleep(8)  # Allow SPA to navigate

            # Check if still on login page
            current_url = self.driver.current_url
            if DEBUG_MODE:
                print(f"   • Current URL after wait: {current_url}")
                
            if "login" in current_url.lower():
                print("🔄 Still on login page, waiting longer...")
                time.sleep(10)

                # Force refresh if needed
                if "login" in self.driver.current_url.lower():
                    print("🔄 Refreshing page...")
                    self.driver.refresh()
                    time.sleep(5)
                    if DEBUG_MODE:
                        print(f"   • URL after refresh: {self.driver.current_url}")
        else:
            if DEBUG_MODE:
                print("❌ Login failed - could not find or fill login form")

        return success

    def _explore_and_extract(self) -> BillInfo:
        """Coordinate navigation and extraction"""
        print("🧭 Starting intelligent exploration...")

        # Initialize components
        extraction_orchestrator = SmartExtractionOrchestrator()
        navigation_explorer = NavigationAgent(self.driver)

        # Use navigation explorer to find and extract billing data
        return navigation_explorer.explore_for_billing_data(extraction_orchestrator)

    def _cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            self.driver.quit()


def display_billing_table(bill_info: BillInfo):
    """Display billing information in a clean table format"""
    print("\n" + "="*50)
    print("💡 UTILITY BILLING HISTORY")
    print("="*50)
    
    # Check if comprehensive billing history is available
    if hasattr(bill_info, 'all_bills') and bill_info.all_bills and len(bill_info.all_bills) > 2:
        print(f"📊 Found {len(bill_info.all_bills)} billing records (latest per month)")
        print("="*50)
        
        # Create comprehensive billing table (latest per month only)
        data = []
        for bill in bill_info.all_bills:
            if isinstance(bill['date'], str):
                date_str = bill['date']
            else:
                date_str = bill['date'].strftime('%m/%d/%Y')
            data.append([date_str, f"${bill['amount']:.2f}"])

        print(tabulate(data, headers=["Date", "Amount"], tablefmt="grid"))

    else:
        # Simple display for basic data
        data = [
            [bill_info.previous_month, f"${bill_info.previous_amount:.2f}"],
            [bill_info.current_month, f"${bill_info.current_amount:.2f}"],
            ["Difference", f"${bill_info.current_amount - bill_info.previous_amount:.2f}"]
        ]

        print(tabulate(data, headers=["Date", "Amount"], tablefmt="grid"))

    print("="*50)


def scrape_utility_bills(url: str, username: str, password: str) -> BillInfo:
    """
    Simple function to scrape utility bills
    
    Args:
        url: Utility website URL
        username: Login username/email
        password: Login password
        
    Returns:
        BillInfo object with billing data
    """
    try:
        if DEBUG_MODE:
            print("🔧 Creating UtilityBillScraper instance...")
            import sys
            sys.stdout.flush()
        
        scraper = UtilityBillScraper()
        
        if DEBUG_MODE:
            print("✅ Scraper created, starting bill scraping...")
            sys.stdout.flush()
        
        return scraper.scrape_utility_bill(url, username, password)
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please ensure Ollama is running:")
        print("  ollama pull qwen2.5:latest")
        print("  ollama pull qwen2.5vl:7b  # For Vision AI")
        print("  uv add Pillow  # For Vision AI support")
        return BillInfo("Configuration error", 0.0, str(e), 0.0)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        if DEBUG_MODE:
            import traceback
            print("🐛 Full traceback:")
            traceback.print_exc()
        return BillInfo("Unexpected error", 0.0, str(e), 0.0)


def main():
    """Interactive main function"""
    print("🏠 AutoBilling - Universal AI-Powered Utility Bill Scraper")
    print("🤖 Clean, fast, and modular design!")
    print("=" * 60)
    
    if SHOW_BROWSER:
        print("👀 Browser window will be visible (you can see what's happening)")
    else:
        print("🕶️ Running in headless mode (browser hidden)")
    
    if DEBUG_MODE:
        print("🐛 Debug mode enabled (detailed output)")
    
    print("💡 To change browser visibility, edit SHOW_BROWSER in utils/config.py")
    print("=" * 60)

    try:
        # Get user input
        url = 'https://flowermoundtx.municipalonlinepayments.com/flowermoundtx/login'
        # url ='https://coserv.smarthub.coop/ui/#/login'
        username = 'vygemnguyen@gmail.com'
        password = 'Dancingapple42!'

        if not all([url, username, password]):
            print("❌ All fields are required!")
            return

        print("\n🧠 Starting optimized AI analysis...")
        print("✨ The system will automatically:")
        print("   • Detect and fill login forms using AI")
        print("   • Intelligently navigate to billing pages")
        print("   • Try multiple extraction strategies (API → HTML → Vision AI)")
        print("   • Extract comprehensive billing history")
        print("   • Display organized results")
        print()  # Add blank line before starting
        
        # Flush output to ensure everything appears immediately
        import sys
        sys.stdout.flush()

        # Run scraper
        bill_info = scrape_utility_bills(url, username, password)

        # Display results
        display_billing_table(bill_info)

    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")


def test_components():
    """Quick test function to identify which component is causing issues"""
    print("🧪 Testing individual components...")
    
    # Test 1: Ollama
    print("\n1️⃣ Testing Ollama connection...")
    try:
        import time
        start = time.time()
        ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": "test"}],
            options={"num_predict": 1, "timeout": 5}
        )
        print(f"   ✅ Ollama works ({time.time() - start:.1f}s)")
    except Exception as e:
        print(f"   ❌ Ollama failed: {e}")
        return
    
    # Test 2: ChromeDriver
    print("\n2️⃣ Testing ChromeDriver setup...")
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        start = time.time()
        driver_path = ChromeDriverManager().install()
        print(f"   ✅ ChromeDriver ready ({time.time() - start:.1f}s)")
        print(f"   📍 Driver path: {driver_path}")
    except Exception as e:
        print(f"   ❌ ChromeDriver failed: {e}")
        return
    
    # Test 3: Browser startup
    print("\n3️⃣ Testing browser startup...")
    try:
        start = time.time()
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Always headless for test
        chrome_options.add_argument("--no-sandbox")
        
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"   ✅ Browser started ({time.time() - start:.1f}s)")
        
        # Quick navigation test
        driver.get("https://httpbin.org/status/200")
        print(f"   ✅ Navigation test passed")
        
        driver.quit()
        print("   ✅ Browser cleanup successful")
        
    except Exception as e:
        print(f"   ❌ Browser failed: {e}")
        return
    
    print("\n🎉 All components working! The issue might be in the actual scraping logic.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_components()
    else:
        main() 