#!/usr/bin/env python3
"""
Manual extraction from transaction history HTML to prove the concept
"""

from bs4 import BeautifulSoup
import re
from main import BillInfo, display_billing_table

def extract_billing_manually():
    """Extract billing data manually from the saved transaction history page"""
    
    try:
        # Read the saved transaction history page
        with open('transaction_history_page.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print("📁 Reading transaction_history_page.html...")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all table cells with dollar amounts
        amounts = []
        
        # Look for table cells containing dollar amounts
        cells = soup.find_all(['td', 'span', 'div'], string=re.compile(r'\$[\d,]+\.?\d*'))
        
        print(f"🔍 Found {len(cells)} cells with dollar amounts")
        
        for cell in cells:
            text = cell.get_text(strip=True)
            # Extract dollar amounts
            dollar_matches = re.findall(r'\$[\d,]+\.?\d*', text)
            for match in dollar_matches:
                # Clean the amount
                clean_amount = float(match.replace('$', '').replace(',', ''))
                amounts.append(clean_amount)
                print(f"   💰 Found: {match} = ${clean_amount:.2f}")
        
        # Also look for amounts in parentheses (payments)
        payment_cells = soup.find_all(['td', 'span', 'div'], string=re.compile(r'\(\$[\d,]+\.?\d*\)'))
        
        print(f"🔍 Found {len(payment_cells)} payment cells")
        
        for cell in payment_cells:
            text = cell.get_text(strip=True)
            payment_matches = re.findall(r'\(\$[\d,]+\.?\d*\)', text)
            for match in payment_matches:
                # Extract amount without parentheses and make negative
                clean_amount = -float(match.replace('($', '').replace(')', '').replace(',', ''))
                amounts.append(clean_amount)
                print(f"   💸 Found payment: {match} = ${clean_amount:.2f}")
        
        # Filter for positive amounts (bills only)
        bills = [amount for amount in amounts if amount > 0]
        bills.sort(reverse=True)  # Most recent first
        
        print(f"\n📋 All bill amounts found: {bills}")
        
        if len(bills) >= 2:
            current_amount = bills[0]  # Most recent
            previous_amount = bills[1]  # Second most recent
            
            bill_info = BillInfo(
                previous_month="Previous Bill",
                previous_amount=previous_amount,
                current_month="Current Bill", 
                current_amount=current_amount,
                account_number="73-4220-02"
            )
            
            print("\n🎉 Successfully extracted billing data!")
            return bill_info
        else:
            print("❌ Insufficient bill data found")
            return BillInfo("No data", 0.0, "No data", 0.0)
            
    except FileNotFoundError:
        print("❌ transaction_history_page.html not found")
        print("Please run the direct transaction history test first")
        return BillInfo("File not found", 0.0, "File not found", 0.0)
    except Exception as e:
        print(f"❌ Error during manual extraction: {e}")
        return BillInfo("Error", 0.0, "Error", 0.0)

if __name__ == "__main__":
    print("🔧 Manual Billing Data Extraction")
    print("=" * 40)
    
    bill_info = extract_billing_manually()
    display_billing_table(bill_info) 