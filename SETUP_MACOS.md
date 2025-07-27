# macOS Setup Guide for AutoBilling

🍎 **Quick setup guide for macOS users**

## Option 1: Automated Setup (Recommended)

```bash
# Run the updated setup script
./setup_ollama.sh
```

## Option 2: Manual Installation

### Step 1: Install Ollama

Choose one of these methods:

#### Method A: Using Homebrew (Recommended)
```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Ollama
brew install ollama

# Start Ollama service
brew services start ollama
```

#### Method B: Direct Download
1. Visit https://ollama.com/download
2. Download the macOS app
3. Install and run the app
4. The app will start Ollama service automatically

### Step 2: Download the Model

```bash
# Pull the Qwen3 model
ollama pull qwen2.5:latest
```

### Step 3: Test Installation

```bash
# Test the model
ollama run qwen2.5:latest "Hello"

# Or run our test script
python test_ollama.py
```

### Step 4: Install Python Dependencies

```bash
# Install AutoBilling dependencies
pip install -e .
```

### Step 5: Run AutoBilling

```bash
python main.py
```

## Troubleshooting

### Issue: "ollama command not found"
- If using Homebrew: `brew install ollama`
- If using the app: Make sure the Ollama app is running

### Issue: "Connection refused"
- Start Ollama service: `brew services start ollama`
- Or run manually: `ollama serve`

### Issue: Model not found
- Pull the model: `ollama pull qwen2.5:latest`
- Check available models: `ollama list`

### Issue: Permission denied
- Make sure the setup script is executable: `chmod +x setup_ollama.sh`

## Useful Commands

```bash
# Check if Ollama is running
brew services list | grep ollama

# Start/stop Ollama service
brew services start ollama
brew services stop ollama

# List available models
ollama list

# Interactive chat with the model
ollama run qwen2.5:latest

# Check Ollama status
curl http://localhost:11434/api/version
```

## Next Steps

Once setup is complete:

1. **Test the system**: `python test_ollama.py`
2. **Try the example**: `python example_usage.py`  
3. **Run AutoBilling**: `python main.py`

🎉 **You're ready to scrape utility bills with AI!** 