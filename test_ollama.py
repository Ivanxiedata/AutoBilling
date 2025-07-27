#!/usr/bin/env python3
"""
Test script to verify Ollama setup and connection
Run this before using the main AutoBilling script
"""

import ollama
import json
import config

def test_ollama_connection():
    """Test if Ollama is running and accessible"""
    print("🧪 Testing Ollama Connection...")
    
    try:
        # Test basic connection
        response = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": "Hello, can you respond with just 'OK'?"}],
            options={"num_predict": 10}
        )
        
        print(f"✅ Connected to Ollama successfully!")
        print(f"📦 Model: {config.OLLAMA_MODEL}")
        print(f"🌐 Base URL: {config.OLLAMA_BASE_URL}")
        print(f"💬 Test Response: {response['message']['content']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to connect to Ollama: {e}")
        print("\n🔧 Troubleshooting steps:")
        print("1. Check if Ollama is installed: ollama --version")
        print("2. Start Ollama service: ollama serve")
        print("3. Pull the model: ollama pull qwen2.5:latest")
        print("4. Test manually: ollama run qwen2.5:latest 'Hello'")
        return False

def test_json_parsing():
    """Test if the model can generate valid JSON"""
    print("\n🧪 Testing JSON Response Generation...")
    
    try:
        prompt = """
        Please respond with valid JSON only. No additional text.
        
        {
            "test": true,
            "message": "This is a test response",
            "numbers": [1, 2, 3]
        }
        """
        
        response = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0.1,
                "num_predict": 200
            }
        )
        
        response_content = response['message']['content']
        print(f"📝 Raw Response: {response_content}")
        
        # Try to parse JSON
        json_start = response_content.find('{')
        json_end = response_content.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_content = response_content[json_start:json_end]
            parsed = json.loads(json_content)
            print(f"✅ JSON Parsing: Success")
            print(f"📋 Parsed Content: {parsed}")
            return True
        else:
            print(f"❌ JSON Parsing: No valid JSON found in response")
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parsing Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during JSON test: {e}")
        return False

def test_html_analysis():
    """Test basic HTML analysis capability"""
    print("\n🧪 Testing HTML Analysis...")
    
    sample_html = """
    <html>
    <body>
        <form action="/login" method="post">
            <input type="text" name="username" placeholder="Username">
            <input type="password" name="password" placeholder="Password">
            <button type="submit">Login</button>
        </form>
        <div class="billing">
            <p>Current Bill: $125.50</p>
            <p>Previous Bill: $102.30</p>
        </div>
    </body>
    </html>
    """
    
    try:
        prompt = f"""
        Analyze this HTML and respond with JSON only:
        
        {sample_html}
        
        Format:
        {{
            "login_form": {{
                "found": true/false,
                "username_field": "field name",
                "password_field": "field name"
            }},
            "billing_data": {{
                "found": true/false,
                "current_amount": "amount",
                "previous_amount": "amount"
            }}
        }}
        """
        
        response = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0.1,
                "num_predict": 500
            }
        )
        
        response_content = response['message']['content']
        
        # Extract JSON
        json_start = response_content.find('{')
        json_end = response_content.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_content = response_content[json_start:json_end]
            parsed = json.loads(json_content)
            
            print(f"✅ HTML Analysis: Success")
            print(f"🔍 Found login form: {parsed.get('login_form', {}).get('found', False)}")
            print(f"💰 Found billing data: {parsed.get('billing_data', {}).get('found', False)}")
            
            return True
        else:
            print(f"❌ HTML Analysis: Could not parse JSON response")
            return False
            
    except Exception as e:
        print(f"❌ Error during HTML analysis test: {e}")
        return False

def main():
    """Run all tests"""
    print("🏠 AutoBilling Ollama Test Suite")
    print("=" * 50)
    
    # Test connection
    connection_ok = test_ollama_connection()
    
    if not connection_ok:
        print("\n❌ Cannot proceed with other tests - fix Ollama connection first")
        return
    
    # Test JSON parsing
    json_ok = test_json_parsing()
    
    # Test HTML analysis
    html_ok = test_html_analysis()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    print(f"🔗 Ollama Connection: {'✅ PASS' if connection_ok else '❌ FAIL'}")
    print(f"📋 JSON Generation: {'✅ PASS' if json_ok else '❌ FAIL'}")
    print(f"🔍 HTML Analysis: {'✅ PASS' if html_ok else '❌ FAIL'}")
    
    if all([connection_ok, json_ok, html_ok]):
        print("\n🎉 All tests passed! You're ready to use AutoBilling!")
    else:
        print("\n⚠️  Some tests failed. Please check your Ollama setup.")
        print("💡 Try running: ollama pull qwen2.5:latest")

if __name__ == "__main__":
    main() 