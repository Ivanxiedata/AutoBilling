# AutoBilling - AI-Powered Utility Bill Scraper

🏠 An intelligent Python tool that can automatically log into utility company websites and extract billing information using AI-powered page analysis with Ollama and Qwen3.

## Features

- 🤖 **AI-Powered**: Uses Qwen3 via Ollama to understand different utility website layouts
- 🔐 **Automatic Login**: Intelligently finds and fills login forms
- 📊 **Data Extraction**: Extracts current and previous month billing data
- 📋 **Clean Display**: Shows results in a formatted table
- 🌐 **Universal**: Works with various utility company websites
- 🔍 **Smart Navigation**: Automatically finds billing pages after login
- 🏠 **Local AI**: Uses Ollama for privacy-focused local AI processing

## Setup

1. **Install Ollama**:
   ```bash
   # Install Ollama (if not already installed)
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull the Qwen3 model
   ollama pull qwen2.5:latest
   
   # Start Ollama service (if not running)
   ollama serve
   ```

2. **Install Dependencies**:
   ```bash
   pip install -e .
   ```

3. **Chrome Driver**:
   - The script automatically downloads and manages ChromeDriver
   - Ensure you have Chrome browser installed

## Usage

### Command Line Interface
```bash
python main.py
```

### Programmatic Usage
```python
from main import UtilityBillScraper, display_billing_table

scraper = UtilityBillScraper()
bill_info = scraper.scrape_utility_bill(
    url="https://your-utility-company.com",
    username="your_username",
    password="your_password"
)

display_billing_table(bill_info)
```

## How It Works

1. **Local AI Analysis**: Qwen3 model via Ollama analyzes HTML to understand website structure
2. **Login Detection**: Finds username, password fields and submit buttons
3. **Authentication**: Automatically logs in with provided credentials
4. **Navigation**: Locates billing/account pages if not on the main page
5. **Data Extraction**: Uses AI to identify and extract billing amounts
6. **Formatting**: Displays results in a clean, readable table

## Configuration

Edit `config.py` to customize settings:

```python
# Ollama Configuration
OLLAMA_BASE_URL = "http://localhost:11434"  # Default Ollama URL
OLLAMA_MODEL = "qwen2.5:latest"  # Qwen3 latest model
OLLAMA_TIMEOUT = 120  # Timeout for requests

# Browser Configuration
HEADLESS_BROWSER = True  # Set to False to see browser
BROWSER_TIMEOUT = 30     # Page load timeout

# Other settings...
```

## Supported Data

The scraper extracts:
- Previous month name and bill amount
- Current month name and bill amount
- Account number (if available)
- Due date (if available)
- Bill difference calculation

## Example Output

```
==================================================
💡 UTILITY BILL SUMMARY
==================================================
┌─────────────────┬────────────┬──────────┐
│ Period          │ Month      │ Amount   │
├─────────────────┼────────────┼──────────┤
│ Previous Month  │ November   │ $125.45  │
│ Current Month   │ December   │ $142.30  │
│ Difference      │            │ $16.85   │
│ Account Number  │ 12345678   │          │
│ Due Date        │ Jan 15     │          │
└─────────────────┴────────────┴──────────┘
==================================================
```

## Troubleshooting

### Common Issues

1. **Ollama Connection Failed**: 
   - Ensure Ollama is running: `ollama serve`
   - Check if the model is available: `ollama list`
   - Pull the model if missing: `ollama pull qwen2.5:latest`

2. **Login Failed**: 
   - Verify credentials are correct
   - Check if the website requires additional verification (2FA, CAPTCHA)
   - Some sites may block automated access

3. **Data Not Found**:
   - The AI might need more context about the specific utility website
   - Try manually navigating to ensure the billing data is visible
   - Check Ollama logs for any processing errors

### Ollama Setup

Make sure Ollama is properly set up:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/version

# List available models
ollama list

# Pull Qwen3 if not available
ollama pull qwen2.5:latest

# Test the model
ollama run qwen2.5:latest "Hello"
```

### Browser Issues

- Set `HEADLESS_BROWSER = False` in `config.py` to see the browser in action
- The script includes user-agent headers to appear more like a real browser
- Some sites may require additional anti-detection measures

## Privacy Benefits

- **Local Processing**: All AI analysis happens locally via Ollama
- **No Cloud APIs**: No data sent to external AI services
- **Privacy-First**: Your utility credentials and bill data stay on your machine
- **Offline Capable**: Works without internet connection (except for website access)

## Security Notes

- Credentials are only used during the session and not stored
- All AI processing happens locally - no data sent to external services
- Use environment variables for sensitive information
- Consider using application-specific passwords where available
- Be aware of your utility company's terms of service regarding automated access

## Contributing

Feel free to submit issues and enhancement requests. This tool can be extended to support:
- More utility companies
- Additional data points (usage graphs, payment history)
- Export to different formats (CSV, JSON, PDF)
- Scheduled automatic runs
- Different Ollama models for various languages

## Disclaimer

This tool is for personal use only. Always respect website terms of service and rate limits. Use responsibly and ensure you have permission to access the accounts you're scraping.
