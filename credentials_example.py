#!/usr/bin/env python3
"""
Example showing different ways to provide credentials to AutoBilling
"""

from main import UtilityBillScraper, display_billing_table
import json
import os
import time
from bs4 import BeautifulSoup

# Option 1: Direct in code (for testing only - not secure)
def example_direct_credentials():
    """Example with credentials directly in code (NOT RECOMMENDED for production)"""
    
    # Your utility information
    # url = "https://www.municipalonlinepayments.com/flowermoundtx"
    # username = "vygemnguyem@gmail.com"
    # password = "Dancingapple42!"

    url = "https://www.coserv.com/"
    username = "vygemnguyem@gmail.com"
    password = "Dancingapple42!"
    
    # Create and run scraper
    scraper = UtilityBillScraper()
    bill_info = scraper.scrape_utility_bill(url, username, password)
    display_billing_table(bill_info)

# Option 2: Using environment variables (RECOMMENDED)
def example_env_credentials():
    """Example using environment variables (more secure)"""
    
    # Set these in your terminal or .env file:
    # export UTILITY_URL="https://your-utility-site.com"
    # export UTILITY_USERNAME="your_username"
    # export UTILITY_PASSWORD="your_password"
    
    url = os.getenv('UTILITY_URL')
    username = os.getenv('UTILITY_USERNAME') 
    password = os.getenv('UTILITY_PASSWORD')
    
    if not all([url, username, password]):
        print("❌ Please set environment variables:")
        print("export UTILITY_URL='https://your-utility-site.com'")
        print("export UTILITY_USERNAME='your_username'")
        print("export UTILITY_PASSWORD='your_password'")
        return
    
    scraper = UtilityBillScraper()
    bill_info = scraper.scrape_utility_bill(url, username, password)
    display_billing_table(bill_info)

# Option 3: Reading from a config file
def example_config_file():
    """Example reading credentials from a config file"""
    
    try:
        # Create a file called 'credentials.json' with:
        # {
        #     "url": "https://your-utility-site.com",
        #     "username": "your_username", 
        #     "password": "your_password"
        # }
        
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
        
        scraper = UtilityBillScraper()
        bill_info = scraper.scrape_utility_bill(
            creds['url'], 
            creds['username'], 
            creds['password']
        )
        display_billing_table(bill_info)
        
    except FileNotFoundError:
        print("❌ credentials.json file not found")
        print("Create a file with your credentials:")
        print("""
{
    "url": "https://your-utility-site.com",
    "username": "your_username",
    "password": "your_password"
}
        """)

# Option 4: Interactive with defaults
def example_interactive_with_defaults():
    """Example with interactive input but default values"""
    
    # Default values (you can change these)
    default_url = "https://www.municipalonlinepayments.com/flowermoundtx"
    default_username = "vygemnguyem@gmail.com"
    
    url = input(f"🌐 URL [{default_url}]: ").strip() or default_url
    username = input(f"👤 Username [{default_username}]: ").strip() or default_username
    password = input("🔒 Password: ").strip()
    
    if not password:
        print("❌ Password is required!")
        return
    
    scraper = UtilityBillScraper()
    bill_info = scraper.scrape_utility_bill(url, username, password)
    display_billing_table(bill_info)

# Option 5: Direct transaction history test
def example_direct_transaction_history():
    """Example testing direct transaction history access after login."""
    
    try:
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
        
        print("🧪 This will login and directly navigate to transaction history...")
        
        scraper = UtilityBillScraper()
        
        # Setup driver
        scraper.setup_driver(headless=False)  # Show browser for debugging
        
        # Login first
        print("🔐 Logging in...")
        scraper.driver.get(creds['url'])
        time.sleep(3)
        
        html_content = scraper.driver.page_source
        login_data = scraper.find_login_elements(html_content)
        
        if login_data.get("found"):
            if scraper.perform_login(creds['username'], creds['password'], login_data):
                print("✅ Login successful! Now navigating to transaction history...")
                time.sleep(5)
                
                # Try to find transaction history or account detail URLs dynamically
                current_url = scraper.driver.current_url
                base_domain = '/'.join(current_url.split('/')[:3])
                site_path = current_url.split('/')[3] if len(current_url.split('/')) > 3 else ''
                
                print(f"🔍 Analyzing current page for account information...")
                
                # First navigate to utilities page to find account details
                utilities_url = f"{base_domain}/{site_path}/utilities"
                print(f"🏠 Navigating to utilities: {utilities_url}")
                scraper.driver.get(utilities_url)
                time.sleep(3)
                
                # Check utilities dashboard for current billing info FIRST
                print(f"🎯 Checking utilities dashboard for current billing information...")
                html_content = scraper.driver.page_source
                
                # Try to extract current billing from dashboard
                dashboard_billing = scraper.universal_billing_extraction(html_content)
                
                # If we found good current billing info on dashboard, use it!
                if dashboard_billing.current_amount > 0 and dashboard_billing.previous_amount > 0:
                    print(f"✅ Found current billing on dashboard! Current: ${dashboard_billing.current_amount:.2f}, Previous: ${dashboard_billing.previous_amount:.2f}")
                    
                    # Save the utilities dashboard page
                    with open('utilities_dashboard_page.html', 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    print("📁 Saved utilities dashboard to: utilities_dashboard_page.html")
                    
                    display_billing_table(dashboard_billing)
                    input("Press Enter to close browser...")
                    return
                
                print(f"⚠️  No current billing found on dashboard, checking transaction history...")
                
                # Look for account detail or transaction history links
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Look for links with account IDs or transaction history
                transaction_links = []
                account_detail_links = []
                
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    text = link.get_text(strip=True).lower()
                    
                    if 'transactionhistory' in href.lower() or 'transaction' in text:
                        transaction_links.append(href)
                        print(f"🔗 Found transaction link: {text} → {href}")
                    elif 'account' in href.lower() and 'detail' in href.lower():
                        account_detail_links.append(href)
                        print(f"🔗 Found account detail link: {text} → {href}")
                
                # Try transaction history links first
                target_url = None
                if transaction_links:
                    target_url = transaction_links[0]
                    if not target_url.startswith('http'):
                        target_url = base_domain + target_url
                    print(f"🎯 Using transaction history URL: {target_url}")
                elif account_detail_links:
                    target_url = account_detail_links[0]
                    if not target_url.startswith('http'):
                        target_url = base_domain + target_url
                    print(f"🎯 Using account detail URL: {target_url}")
                else:
                    # Fallback to hardcoded URL for this specific site
                    target_url = "https://flowermoundtx.municipalonlinepayments.com/flowermoundtx/utilities/accounts/transactionhistory/73-4220-02"
                    print(f"⚠️  No dynamic links found, using fallback URL: {target_url}")
                
                print(f"🚀 Navigating to: {target_url}")
                scraper.driver.get(target_url)
                time.sleep(5)
                
                current_url = scraper.driver.current_url
                title = scraper.driver.title
                
                print(f"📍 Final URL: {current_url}")
                print(f"📋 Page Title: {title}")
                
                # Try to extract billing info from transaction history
                html_content = scraper.driver.page_source
                
                # Save the transaction history page
                with open('transaction_history_page.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print("📁 Saved transaction history page to: transaction_history_page.html")
                
                bill_info = scraper.universal_billing_extraction(html_content)
                display_billing_table(bill_info)
                
                input("Press Enter to close browser...")
                
            else:
                print("❌ Login failed")
        else:
            print("❌ Login form not found")
            
        scraper.driver.quit()
        
    except FileNotFoundError:
        print("❌ credentials.json not found. Please copy credentials_template.json and edit it.")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Choose which method to use"""
    print("🔑 AutoBilling - Credential Input Examples")
    print("=" * 50)
    
    choice = input("""
Choose a method:
1. 💻 Direct in code (testing only)
2. 🔒 Environment variables (recommended)
3. 📁 Config file
4. 💳 Direct transaction history test
5. 🐛 Debug mode (troubleshoot login issues)

Enter choice (1-5): """)
    
    choice = choice.strip()
    
    if choice == "1":
        print("\n⚠️  WARNING: This method stores credentials in code!")
        print("Only use for testing. Edit the function to add your credentials.")
        example_direct_credentials()
    elif choice == "2":
        example_env_credentials()
    elif choice == "3":
        # Config file method - now using direct transaction history access
        print("📁 Using credentials from config file...")
        print("🎯 Will use direct transaction history access for accurate results...")
        try:
            with open('credentials.json', 'r') as f:
                creds = json.load(f)
            
            # Use the direct transaction history method for better accuracy
            example_direct_transaction_history()
            
        except FileNotFoundError:
            print("❌ credentials.json not found. Please copy credentials_template.json and edit it.")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    elif choice == "4":
        # Direct transaction history test already implemented above
        print("💳 Testing direct transaction history access after login...")
        example_direct_transaction_history()
            
    elif choice == "5":
        # Import and run debug tool
        from debug_scraper import debug_utility_site
        url = input("🌐 Enter URL to debug: ").strip()
        if url:
            debug_utility_site(url)
    else:
        print("❌ Invalid choice!")

if __name__ == "__main__":
    main() 