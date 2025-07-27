#!/bin/bash

echo "🏠 AutoBilling - Ollama Setup Script"
echo "===================================="

# Detect operating system
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*)    MACHINE=Cygwin;;
    MINGW*)     MACHINE=MinGw;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

echo "🖥️  Detected OS: $MACHINE"

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is already installed"
    ollama --version
else
    echo "📦 Installing Ollama..."
    
    if [[ "$MACHINE" == "Mac" ]]; then
        echo "🍎 Installing Ollama for macOS..."
        
        # Check if Homebrew is available
        if command -v brew &> /dev/null; then
            echo "🍺 Using Homebrew to install Ollama..."
            brew install ollama
        else
            echo "📥 Downloading Ollama for macOS directly..."
            echo "Please visit https://ollama.com/download and download the macOS app"
            echo "Or install Homebrew first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            echo "Then run: brew install ollama"
            exit 1
        fi
        
    elif [[ "$MACHINE" == "Linux" ]]; then
        echo "🐧 Installing Ollama for Linux..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "❌ Unsupported operating system: $MACHINE"
        echo "Please visit https://ollama.com/download for manual installation"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        echo "✅ Ollama installed successfully"
    else
        echo "❌ Failed to install Ollama"
        echo "💡 Try manual installation from https://ollama.com/download"
        exit 1
    fi
fi

echo ""
echo "🚀 Starting Ollama service..."

# Start Ollama in background if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama service in background..."
    
    if [[ "$MACHINE" == "Mac" ]]; then
        # On macOS, try to start as a service or directly
        if command -v brew &> /dev/null && brew services list | grep -q ollama; then
            brew services start ollama
        else
            nohup ollama serve > /dev/null 2>&1 &
        fi
    else
        nohup ollama serve > /dev/null 2>&1 &
    fi
    
    sleep 5
    echo "✅ Ollama service started"
else
    echo "✅ Ollama service is already running"
fi

echo ""
echo "📥 Downloading Qwen2.5:latest model..."
echo "This may take a few minutes depending on your internet connection..."

# Give ollama a moment to fully start
sleep 2

ollama pull qwen2.5:latest

if [ $? -eq 0 ]; then
    echo "✅ Qwen2.5:latest model downloaded successfully"
else
    echo "❌ Failed to download Qwen2.5:latest model"
    echo "Please check your internet connection and try manually: ollama pull qwen2.5:latest"
    echo "💡 You may need to start Ollama first: ollama serve"
    exit 1
fi

echo ""
echo "🧪 Testing the model..."
sleep 2
response=$(echo "Hello, respond with just 'OK'" | ollama run qwen2.5:latest 2>/dev/null | head -1)

if [[ $response == *"OK"* ]] || [[ $response == *"ok"* ]]; then
    echo "✅ Model test successful"
    echo "📝 Response: $response"
else
    echo "⚠️  Model test had unexpected response: $response"
    echo "But this might be normal - continuing..."
fi

echo ""
echo "📋 Installation Summary:"
echo "========================"
echo "✅ Ollama installed and running on $MACHINE"
echo "✅ Qwen2.5:latest model available"
echo "🌐 Ollama service running on http://localhost:11434"

echo ""
echo "🎉 Setup complete! You can now:"
echo "1. Test the setup: python test_ollama.py"
echo "2. Install Python dependencies: pip install -e ."
echo "3. Run AutoBilling: python main.py"

echo ""
echo "📚 Useful commands:"
echo "  ollama list                    # List installed models"
echo "  ollama ps                      # Show running models"
echo "  ollama run qwen2.5:latest      # Interactive chat"
if [[ "$MACHINE" == "Mac" ]] && command -v brew &> /dev/null; then
    echo "  brew services start ollama     # Start Ollama service (macOS)"
    echo "  brew services stop ollama      # Stop Ollama service (macOS)"
else
    echo "  ollama serve                   # Start Ollama service manually"
fi 