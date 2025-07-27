#!/usr/bin/env python3
"""
Example usage of AutoBilling with Ollama and Qwen3
This demonstrates how to use the scraper programmatically
"""

from main import UtilityBillScraper, display_billing_table, BillInfo

def example_utility_scraping():
    """Example function showing how to use AutoBilling"""
    
    print("🏠 AutoBilling Example Usage")
    print("=" * 40)
    
    # Example utility company URLs (replace with real ones)
    examples = [
        {
            "name": "Example Electric Company",
            "url": "https://example-electric.com/login",
            "note": "Common electric utility login page"
        },
        {
            "name": "Sample Gas Company", 
            "url": "https://sample-gas.com/account",
            "note": "Gas utility with account page"
        },
        {
            "name": "Water Department",
            "url": "https://city-water.gov/billing",
            "note": "Municipal water billing system"
        }
    ]
    
    print("📋 Example utility websites that AutoBilling can handle:")
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example['name']}")
        print(f"   URL: {example['url']}")
        print(f"   Note: {example['note']}")
        print()
    
    # Get user input
    url = input("🌐 Enter your utility website URL: ").strip()
    if not url:
        print("❌ URL is required!")
        return
    
    username = input("👤 Enter your username/email: ").strip()
    if not username:
        print("❌ Username is required!")
        return
        
    password = input("🔒 Enter your password: ").strip()
    if not password:
        print("❌ Password is required!")
        return
    
    try:
        # Create the scraper
        print("\n🤖 Initializing AI-powered scraper...")
        scraper = UtilityBillScraper()
        
        # Scrape the utility bill
        print("🔍 Starting utility bill analysis...")
        bill_info = scraper.scrape_utility_bill(url, username, password)
        
        # Display results
        print("\n📊 Results:")
        display_billing_table(bill_info)
        
        # Additional analysis
        if bill_info.current_amount > 0 and bill_info.previous_amount > 0:
            difference = bill_info.current_amount - bill_info.previous_amount
            percentage_change = (difference / bill_info.previous_amount) * 100
            
            print(f"\n📈 Bill Analysis:")
            print(f"💰 Monthly Change: ${difference:.2f}")
            print(f"📊 Percentage Change: {percentage_change:.1f}%")
            
            if difference > 0:
                print(f"📈 Your bill increased this month")
            elif difference < 0:
                print(f"📉 Your bill decreased this month")
            else:
                print(f"➡️  Your bill stayed the same")
        
        return bill_info
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure Ollama is running and qwen2.5:latest is available")
        return None

def test_with_sample_data():
    """Test display with sample data"""
    print("\n🧪 Testing with sample data...")
    
    sample_bill = BillInfo(
        previous_month="November 2024",
        previous_amount=125.45,
        current_month="December 2024", 
        current_amount=142.30,
        account_number="ACC123456789",
        due_date="January 15, 2025"
    )
    
    display_billing_table(sample_bill)

def main():
    """Main function"""
    print("🏠 AutoBilling - Example Usage Script")
    print("=" * 50)
    
    choice = input("""
Choose an option:
1. 🌐 Test with real utility website
2. 🧪 Show sample output
3. ❓ Show help

Enter choice (1-3): """).strip()
    
    if choice == "1":
        example_utility_scraping()
    elif choice == "2":
        test_with_sample_data()
    elif choice == "3":
        print("""
🏠 AutoBilling Help
================

AutoBilling is an AI-powered utility bill scraper that can:

✅ Automatically log into utility websites
✅ Find and extract billing information  
✅ Display results in a clean table format
✅ Work with various utility company layouts
✅ Use local AI (Ollama + Qwen3) for privacy

📋 Requirements:
- Ollama installed and running
- qwen2.5:latest model available
- Chrome browser installed
- Valid utility account credentials

🚀 Quick Start:
1. Run: ./setup_ollama.sh
2. Run: python test_ollama.py  
3. Run: python main.py

💡 Tips:
- Set HEADLESS_BROWSER = False in config.py to see the browser
- Some websites may require manual CAPTCHA solving
- Use application-specific passwords when available
        """)
    else:
        print("❌ Invalid choice!")

if __name__ == "__main__":
    main() 