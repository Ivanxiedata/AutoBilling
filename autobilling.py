#!/usr/bin/env python3
"""
AutoBilling - Automated Utility Billing System
Automates the process of retrieving utility bills and sending billing emails to tenants.
"""

import json
import logging
import os
import smtplib
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from time import sleep

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests

# Google Sheets Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class AutoBilling:
    """Main class for the automated utility billing system."""

    def __init__(self, config_path="config.json", test_mode=False):
        """Initialize the system."""
        self.config = self._load_config(config_path)
        self.setup_logging()
        self.driver = None
        self.test_mode = test_mode
        self.DATE_FORMAT = "%Y-%m-%d"
        self.MONTH_YEAR_FORMAT = "%B %Y"
        self.google_sheet_id = self.config["google_sheet_id"]
        
    def _load_config(self, config_path):
        """Loads configuration from config.json."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Configuration file '{config_path}' not found.")
            raise
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from '{config_path}'.")
            raise
    
    def setup_logging(self):
        """Sets up logging for the application."""
        log_file = self.config.get("log_file", "autobilling.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self, use_user_agent=False):
        """Sets up a headless Chrome WebDriver."""
        self.logger.info("Setting up WebDriver...")
        options = webdriver.ChromeOptions()
        if self.config.get("headless", True):
            # Use the new, more stable headless mode
            options.add_argument("--headless=new")
        if use_user_agent:
            # Add a realistic User-Agent to avoid being blocked by WAFs
            self.logger.info("Using custom User-Agent for this session.")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
        
        # Add stability options
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Let Selenium manage the driver automatically, removing the need for webdriver-manager.
        service = ChromeService()
        self.driver = webdriver.Chrome(service=service, options=options)
    
    def get_water_bill(self):
        """Logs into Flower Mound Utilities and retrieves the latest bill amount and date."""
        self.logger.info("Retrieving water bill...")
        provider = self.config["providers"]["water"]
        
        if not provider.get("username") or not provider.get("password"):
            self.logger.error("Water bill username or password not provided in config.json. Skipping.")
            return None

        try:
            # Step 1: Navigate to the main page and log in
            self.logger.info("Navigating to https://flowermoundtx.municipalonlinepayments.com/flowermoundtx")
            self.driver.get("https://flowermoundtx.municipalonlinepayments.com/flowermoundtx")
            wait = WebDriverWait(self.driver, self.config["timeout"])
            
            self.logger.info("Clicking 'Sign In / Register' button...")
            wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Sign In / Register')]"))).click()

            self.logger.info("Attempting to log in...")
            wait.until(EC.presence_of_element_located((By.ID, "Email"))).send_keys(provider["username"])
            self.driver.find_element(By.ID, "Password").send_keys(provider["password"])
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='button'][value='login']"))).click()
            self.logger.info("Login successful.")

            # Add a pause to ensure the dashboard loads completely
            self.logger.info("Waiting for dashboard to load...")
            sleep(3)

            # Step 2: Navigate to the Utility Billing page
            self.logger.info("Using JavaScript to click 'Utility Billing' link.")
            utility_billing_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Utility Billing")))
            self.driver.execute_script("arguments[0].click();", utility_billing_link)

            self.logger.info("Navigated to the utilities page.")
            
            # Step 3: Navigate to Transactions and scrape the bill
            self.logger.info("Clicking 'Transactions' link...")
            # The element is difficult to locate, so we will use JavaScript to click it.
            transactions_link = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Transactions")))
            self.driver.execute_script("arguments[0].click();", transactions_link)
            
            self.logger.info("Searching for the latest bill in the transaction history table...")
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
            transaction_rows = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr")

            for row in transaction_rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 3 and "Bill" in cols[1].text:
                    amount_str = cols[2].text.replace("$", "").replace("(", "").replace(")", "").replace(",", "").strip()
                    date_str = cols[0].text.strip()  # First column contains the date
                    self.logger.info(f"Successfully retrieved water bill: ${amount_str} from {date_str}")
                    return {"amount": float(amount_str), "date": date_str}
            
            self.logger.warning("Could not find a 'Bill' in the transaction history table.")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve water bill. Check credentials and selectors. Error: {e}")
            if self.driver:
                self.driver.save_screenshot("water_bill_failure_screenshot.png")
                with open("water_bill_failure_page_source.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                self.logger.info("Saved screenshot and page source for debugging.")
            return None
    
    def get_electric_bill(self):
        """Logs into CoServ Electric (SmartHub) and retrieves the latest bill amount and date."""
        self.logger.info("Retrieving electric bill...")
        provider = self.config["providers"]["electric"]

        if not provider.get("username") or not provider.get("password"):
            self.logger.error("Electric bill username or password not provided in config.json. Skipping.")
            return None

        try:
            self.driver.get(provider["url"])
            wait = WebDriverWait(self.driver, self.config["timeout"])

            self.logger.info("Waiting for CoServ login page to load...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#mat-input-0")))

            self.logger.info("Attempting to log in to CoServ Electric (SmartHub)...")
            self.driver.find_element(By.CSS_SELECTOR, "input#mat-input-0").send_keys(provider["username"])
            self.driver.find_element(By.CSS_SELECTOR, "input#mat-input-1").send_keys(provider["password"])
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(normalize-space(), 'Sign In')]"))).click()
            self.logger.info("Login successful.")

            # Wait for the main dashboard to load by waiting for a known element.
            self.logger.info("Waiting for dashboard to load...")
            wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'BILL & PAY')]")))

            # Instead of clicking through menus, navigate directly to the billing history page.
            self.logger.info("Navigating directly to billing history page...")
            billing_history_url = "https://coserv.smarthub.coop/ui/#/billingHistory"
            self.driver.get(billing_history_url)

            self.logger.info("Waiting for billing history page to load...")
            # Wait for the table to be present
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "mat-table")))

            self.logger.info("Searching for the latest bill in the billing history...")
            
            bill_rows = self.driver.find_elements(By.TAG_NAME, "mat-row")

            if not bill_rows:
                self.logger.warning("No bill rows found on the billing history page.")
                return None
            
            # Assume the first row is the latest bill
            latest_bill_row = bill_rows[0]
            cells = latest_bill_row.find_elements(By.TAG_NAME, "mat-cell")
            
            if cells:
                # From the screenshot, the "Total Due" amount is in the last cell.
                amount_str = cells[-1].text.replace("$", "").replace(",", "").strip()

                # The date is not visible on the billing history page screenshot.
                # Using the current date as a fallback.
                bill_date = datetime.now().strftime("%m/%d/%Y")
                self.logger.info(f"Successfully retrieved electric bill: ${amount_str} from {bill_date} (used current date).")
                return {"amount": float(amount_str), "date": bill_date}

            self.logger.warning("Could not find cells in the latest bill row.")
            return None

        except Exception as e:
            self.logger.error(f"Failed to retrieve electric bill. Check credentials and selectors. Error: {e}")
            if self.driver:
                self.driver.save_screenshot("electric_bill_failure_screenshot.png")
                with open("electric_bill_failure_page_source.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                self.logger.info("Saved screenshot and page source for debugging.")
            return None
    
    def get_wifi_bill(self):
        """Logs into Frontier Communications and retrieves the latest bill amount and date."""
        self.logger.info("Retrieving WiFi bill...")
        provider = self.config["providers"]["wifi"]

        if not provider.get("username") or not provider.get("password"):
            self.logger.error("WiFi bill username or password not provided in config.json. Skipping.")
            return None

        try:
            self.driver.get(provider["url"])
            wait = WebDriverWait(self.driver, self.config["timeout"])

            self.logger.info("Checking for and dismissing cookie consent banner...")
            try:
                # Use a generic, case-insensitive XPath to find common cookie consent button text
                cookie_button_xpath = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow')]"
                cookie_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, cookie_button_xpath))
                )
                cookie_button.click()
                self.logger.info("Dismissed a cookie consent banner.")
                sleep(2)  # Give the banner time to disappear
            except Exception:
                self.logger.info("No cookie consent banner found or could not be clicked.")

            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            self.logger.info(f"Found {len(iframes)} iframe(s) on the page.")

            self.logger.info("Waiting for login form iframe and switching to it...")
            try:
                # This is the most robust way to wait for and switch to an iframe.
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))
                self.logger.info("Successfully switched to login iframe.")
            except Exception:
                self.logger.info("Could not find or switch to an iframe. Assuming login form is on the main page.")

            self.logger.info("Attempting to log in to Frontier...")
            # Wait not just for the element to be present, but for it to be visible.
            self.logger.info("Waiting for username field to be visible...")
            username_field = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#loginId")))
            username_field.click() # Click to focus
            username_field.send_keys(provider["username"])
            
            self.logger.info("Waiting for password field to be visible...")
            password_field = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#password")))
            password_field.click() # Click to focus
            password_field.send_keys(provider["password"])

            # Find and click the submit button
            submit_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            submit_button.click()
            self.logger.info("Login submitted.")
            
            # Switch back to the main document context
            self.driver.switch_to.default_content()

            # --- Scrape the bill amount from the page after login ---
            self.logger.info("Searching for WiFi bill amount on the dashboard...")
            
            # This is a guess and will likely need to be updated based on the screenshot.
            # Wait for a common dashboard element to appear after login.
            wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'My Account') or contains(text(), 'Dashboard')]")))
            
            self.logger.info("Attempting to find bill amount with a generic selector...")
            # This XPath looks for text like "Current Bill" or "Amount Due", goes up to a common ancestor, then finds a descendant span containing a dollar sign.
            amount_element = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Current Bill') or contains(text(), 'Amount Due')]/ancestor::div[1]//span[contains(text(), '$')]")
            amount_str = amount_element.text.replace("$", "").replace(",", "").strip()
            
            # Using the current date as a fallback.
            date_str = datetime.now().strftime("%m/%d/%Y")
            
            self.logger.info(f"Successfully retrieved WiFi bill: ${amount_str} from {date_str} (used current date).")
            return {"amount": float(amount_str), "date": date_str}
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve WiFi bill. Check credentials and selectors. Error: {e}")
            if self.driver:
                self.driver.save_screenshot("wifi_bill_failure_screenshot.png")
                with open("wifi_bill_failure_page_source.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                self.logger.info("Saved screenshot and page source for debugging.")
            return None
    
    def _get_google_sheets_service(self):
        """Authenticates with Google and returns a Sheets service object."""
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        
        try:
            service = build("sheets", "v4", credentials=creds)
            return service
        except HttpError as err:
            self.logger.error(f"Failed to create Google Sheets service: {err}")
            return None

    def update_google_sheet_and_get_costs(self, bills):
        """
        Updates the Google Sheet with new bill amounts and returns per-tenant costs.
        Creates a new yearly tab if it doesn't exist.
        """
        service = self._get_google_sheets_service()
        if not service:
            return None

        # Determine the target month for billing (previous month)
        today = date.today()
        first_day_of_current_month = today.replace(day=1)
        target_billing_date = first_day_of_current_month - timedelta(days=1)
        
        target_year = target_billing_date.year
        target_month_name = target_billing_date.strftime("%B")
        sheet_name = f"Utility Bills {target_year}"
        self.logger.info(f"Targeting billing month: {target_month_name} {target_year}")

        try:
            # Check if the yearly sheet exists
            spreadsheet_metadata = service.spreadsheets().get(spreadsheetId=self.google_sheet_id).execute()
            sheets = spreadsheet_metadata.get('sheets', '')
            sheet_exists = any(s['properties']['title'] == sheet_name for s in sheets)

            # Create the sheet if it doesn't exist
            if not sheet_exists:
                self.logger.info(f"Sheet '{sheet_name}' not found. Creating it...")
                body = {'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
                service.spreadsheets().batchUpdate(spreadsheetId=self.google_sheet_id, body=body).execute()
                
                # Add headers to the new sheet
                headers = [["Month", "Water", "Electricity", "Internet"]]
                header_body = {'values': headers}
                service.spreadsheets().values().update(
                    spreadsheetId=self.google_sheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption="RAW",
                    body=header_body
                ).execute()
                self.logger.info(f"Added headers to '{sheet_name}'.")

            # Get all data from the sheet
            result = service.spreadsheets().values().get(
                spreadsheetId=self.google_sheet_id,
                range=sheet_name
            ).execute()
            values = result.get('values', [])

            # If the sheet is brand new or empty, it won't have headers.
            if not values:
                self.logger.info(f"Sheet '{sheet_name}' is empty. Adding headers.")
                headers_to_add = [["Month", "Water", "Electricity", "Internet"]]
                header_body = {'values': headers_to_add}
                service.spreadsheets().values().update(
                    spreadsheetId=self.google_sheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption="RAW",
                    body=header_body
                ).execute()
                # After adding headers, the values should reflect this for the rest of the function
                values = headers_to_add

            header = values[0]
            # Filter out empty rows before processing
            month_col_data = [row[0] for row in values if row]

            # Find or create the row for the current month
            try:
                month_row_index = month_col_data.index(target_month_name) + 1
            except ValueError: # Month not found
                self.logger.info(f"Adding new row for month: '{target_month_name}'.")
                new_row_data = [[target_month_name]]
                append_body = {'values': new_row_data}
                service.spreadsheets().values().append(
                    spreadsheetId=self.google_sheet_id,
                    range=f"'{sheet_name}'!A:A",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body=append_body
                ).execute()
                month_row_index = len(values) + 1
            
            # Update the cells for the retrieved bills
            for bill in bills:
                bill_type = bill["Type"]
                if bill_type == "WiFi":
                    bill_type = "Internet"  # Map "WiFi" to the "Internet" column

                if bill_type in header:
                    col_index = header.index(bill_type)
                    col_letter = chr(ord('A') + col_index)
                    cell_to_update = f"'{sheet_name}'!{col_letter}{month_row_index}"
                    
                    update_body = {'values': [[bill["Amount"]]]}
                    service.spreadsheets().values().update(
                        spreadsheetId=self.google_sheet_id,
                        range=cell_to_update,
                        valueInputOption="RAW",
                        body=update_body
                    ).execute()
                    self.logger.info(f"Updated cell {cell_to_update} with amount {bill['Amount']}.")

            # Calculate tenant costs for emails
            self.logger.info("Calculating per-tenant costs...")
            num_tenants = len(self.config["tenants"])
            all_bills = {b['Type']: b['Amount'] for b in bills}
            per_tenant_costs = {
                "Water": all_bills.get("Water", 0) / num_tenants,
                "Electric": all_bills.get("Electricity", 0) / num_tenants,
                "WiFi": all_bills.get("WiFi", 0) / num_tenants,
            }
            total_per_tenant = sum(per_tenant_costs.values())

            month_data = []
            for tenant in self.config["tenants"]:
                record = {
                    "Month": target_billing_date.strftime(self.MONTH_YEAR_FORMAT), 
                    "Tenant": tenant["name"], 
                    **per_tenant_costs, 
                    "Total": total_per_tenant
                }
                month_data.append(record)
            
            self.logger.info("Successfully updated Google Sheet and calculated tenant costs.")
            return month_data

        except HttpError as err:
            self.logger.error(f"An error occurred with the Google Sheets API: {err}")
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while updating Google Sheets: {e}")
            return None

    def send_billing_emails(self, month_data, total_bills):
        """Sends itemized billing emails to each tenant."""
        self.logger.info("Sending billing emails...")
        email_config = self.config["email"]
        sender_email = email_config["sender_email"]
        sender_password = email_config["sender_password"]
        smtp_server = email_config["smtp_server"]
        smtp_port = email_config["smtp_port"]
        
        if not sender_email or not sender_password:
            self.logger.warning("Sender email or password not configured. Skipping email notifications.")
            return

        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)

            for record in month_data:
                tenant_name = record["Tenant"]
                tenant_email = next((t["email"] for t in self.config["tenants"] if t["name"] == tenant_name), None)
                
                if not tenant_email:
                    self.logger.warning(f"No email found for tenant: {tenant_name}. Skipping.")
                    continue

                subject = f"{record['Month']} Utility Bill – Your Share"
                body = f"""Hi roommates,

I hope you're doing well!

Your share of the utilities for {record['Month']} comes to ${record['Total']:.2f}.

Here's the breakdown of the total bills:
Water: ${total_bills.get('Water', 0):.2f}
Electricity: ${total_bills.get('Electricity', 0):.2f}
Internet: ${total_bills.get('WiFi', 0):.2f}

If you have any questions about the breakdown, feel free to reach out.

Thanks so much!

Best,
Ivan & Vy
"""
                
                msg = MIMEText(body, 'plain')
                msg['Subject'] = subject
                msg['From'] = sender_email
                msg['To'] = tenant_email

                server.sendmail(sender_email, [tenant_email], msg.as_string())
                self.logger.info(f"Successfully sent email to {tenant_name} at {tenant_email}")

            server.quit()
        except Exception as e:
            self.logger.error(f"Failed to send emails: {e}")

    def run(self):
        """Main execution flow for the billing automation."""
        self.logger.info("--- Starting Utility Billing Automation ---")
        
        retrieved_bills = []
        self.driver = None # Ensure driver is reset

        # --- Scrape Water and Electric Bills (Standard WebDriver) ---
        try:
            self.logger.info("Scraping with standard browser settings...")
            self.setup_driver()
            
            water_result = self.get_water_bill()
            if water_result:
                retrieved_bills.append({"Type": "Water", "Amount": water_result["amount"], "Date": water_result["date"]})
                
            electric_result = self.get_electric_bill()
            if electric_result:
                retrieved_bills.append({"Type": "Electricity", "Amount": electric_result["amount"], "Date": electric_result["date"]})
        finally:
            if self.driver:
                self.driver.quit()

        # --- Use a default value for WiFi and skip scraping ---
        self.logger.info("Using default value for WiFi bill and skipping scraping.")
        retrieved_bills.append({
            "Type": "WiFi", 
            "Amount": 60.41, 
            "Date": datetime.now().strftime("%m/%d/%Y")
        })

        if not retrieved_bills:
            self.logger.warning("No bills were retrieved. Exiting.")
        elif self.test_mode:
             self.logger.info("Test mode is ON. Skipping Excel update and email.")
        else:
            tenant_costs = self.update_google_sheet_and_get_costs(retrieved_bills)
            if tenant_costs:
                # Create a simple dictionary of the total bill amounts for the email
                total_bills = {bill['Type']: bill['Amount'] for bill in retrieved_bills}
                self.send_billing_emails(tenant_costs, total_bills)

        self.logger.info("--- Utility Billing Automation Finished ---")

if __name__ == "__main__":
    # To run a test of just the scraping functions, set test_mode=True
    # To run the full process, set test_mode=False
    billing_system = AutoBilling(test_mode=False)
    billing_system.run()

 