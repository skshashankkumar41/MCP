#!/usr/bin/env python3
"""
Test script to demonstrate MCP client functionality with dummy server
"""

import requests
import json
import time
import threading
from datetime import datetime
import uuid

class MCPClientTester:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session_id = f"test_session_{int(time.time())}"
        
    def test_health_check(self):
        """Test server health"""
        print("🔍 Testing health check...")
        try:
            response = requests.get(f"{self.base_url}/health")
            print(f"✅ Health check: {response.json()}")
            return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def add_dummy_server(self):
        """Add the dummy MCP server"""
        print("🔧 Adding dummy MCP server...")
        server_config = {
            "name": "dummy",
            "command": "python3",
            "args": ["dummy_mcp_server.py"],
            "env": {}
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/servers",
                json=server_config,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print("✅ Dummy server added successfully")
                return True
            else:
                print(f"❌ Failed to add server: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error adding server: {e}")
            return False
    
    def list_servers(self):
        """List all connected servers"""
        print("📋 Listing servers...")
        try:
            response = requests.get(f"{self.base_url}/servers")
            servers = response.json()
            print("✅ Connected servers:")
            for name, info in servers.get('servers', {}).items():
                print(f"  📡 {name}: {'🟢 Connected' if info['is_connected'] else '🔴 Disconnected'}")
                print(f"     Tools: {len(info['tools'])}")
                for tool in info['tools']:
                    print(f"       - {tool['name']}: {tool['description']}")
            return True
        except Exception as e:
            print(f"❌ Error listing servers: {e}")
            return False
    
    def test_direct_tool_call(self):
        """Test direct tool calling"""
        print("🔧 Testing direct tool call...")
        
        # Test calculator tool
        tool_request = {
            "server": "dummy",
            "tool": "calculator",
            "arguments": {
                "operation": "add",
                "a": 15,
                "b": 27
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/tools/call",
                json=tool_request,
                headers={"Content-Type": "application/json"}
            )
            
            result = response.json()
            if result.get('success'):
                print("✅ Direct tool call successful:")
                print(f"   Result: {result}")
            else:
                print(f"❌ Tool call failed: {result.get('error')}")
            return result.get('success', False)
        except Exception as e:
            print(f"❌ Error in tool call: {e}")
            return False
    
    def test_query_processing(self):
        """Test query processing with LLM integration"""
        print("🤖 Testing query processing...")
        
        # Mock LLM configuration (you'll need to replace with real LLM API)
        query_request = {
            "query": "What's 25 multiplied by 4?",
            "session_id": self.session_id,
            "llm_api_url": "https://api.openai.com/v1/chat/completions",  # Replace with your LLM API
            "llm_headers": {
                "Authorization": "Bearer YOUR_API_KEY",  # Replace with your API key
                "Content-Type": "application/json"
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/query",
                json=query_request,
                headers={"Content-Type": "application/json"}
            )
            
            result = response.json()
            if result.get('success'):
                print("✅ Query processing successful:")
                print(f"   Response: {result.get('response')}")
                if result.get('tool_used'):
                    print(f"   Tool used: {result['tool_used']['tool']} on {result['tool_used']['server']}")
            else:
                print(f"❌ Query processing failed: {result.get('error')}")
                # This might fail if you don't have a real LLM API configured
                print("   (This is expected if you haven't configured a real LLM API)")
            
            return result.get('success', False)
        except Exception as e:
            print(f"❌ Error in query processing: {e}")
            return False
    
    def test_session_management(self):
        """Test session management"""
        print("💾 Testing session management...")
        
        try:
            # Get conversation history
            response = requests.get(f"{self.base_url}/sessions/{self.session_id}/history")
            history = response.json()
            print(f"✅ Session history: {len(history.get('history', []))} messages")
            
            # List all sessions
            response = requests.get(f"{self.base_url}/sessions")
            sessions = response.json()
            print(f"✅ Active sessions: {len(sessions.get('sessions', {}))}")
            
            return True
        except Exception as e:
            print(f"❌ Error in session management: {e}")
            return False
    
    def test_multiple_tools(self):
        """Test multiple tool calls"""
        print("🔧 Testing multiple tools...")
        
        test_cases = [
            {
                "name": "Current Time",
                "tool": "get_current_time",
                "arguments": {}
            },
            {
                "name": "Store Data",
                "tool": "store_data",
                "arguments": {
                    "key": "test_key",
                    "value": "Hello from test!"
                }
            },
            {
                "name": "Retrieve Data",
                "tool": "retrieve_data",
                "arguments": {
                    "key": "test_key"
                }
            },
            {
                "name": "Random Number",
                "tool": "generate_random_number",
                "arguments": {
                    "min_val": 1,
                    "max_val": 10
                }
            },
            {
                "name": "Word Count",
                "tool": "count_words",
                "arguments": {
                    "text": "This is a test sentence for word counting."
                }
            }
        ]
        
        success_count = 0
        for test_case in test_cases:
            print(f"  🔧 Testing {test_case['name']}...")
            
            tool_request = {
                "server": "dummy",
                "tool": test_case["tool"],
                "arguments": test_case["arguments"]
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/tools/call",
                    json=tool_request,
                    headers={"Content-Type": "application/json"}
                )
                
                result = response.json()
                if result.get('success'):
                    print(f"    ✅ {test_case['name']}: Success")
                    if result.get('content'):
                        for content in result['content']:
                            if content.get('type') == 'text':
                                print(f"       📝 {content['text'][:100]}...")
                    success_count += 1
                else:
                    print(f"    ❌ {test_case['name']}: {result.get('error')}")
            except Exception as e:
                print(f"    ❌ {test_case['name']}: {e}")
        
        print(f"✅ Tool tests completed: {success_count}/{len(test_cases)} successful")
        return success_count == len(test_cases)

def run_sse_test(base_url, session_id):
    """Test Server-Sent Events in a separate thread"""
    import urllib3
    
    try:
        print("📡 Starting SSE test...")
        # Note: This is a simplified SSE test
        # In a real scenario, you'd use a proper SSE client
        response = requests.get(f"{base_url}/events/{session_id}", stream=True)
        
        print("✅ SSE connection established")
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                        print(f"📡 SSE Event: {data.get('type')} - {data.get('message')}")
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        print(f"❌ SSE test error: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting MCP Client Tests")
    print("=" * 50)
    
    tester = MCPClientTester()
    
    # Test sequence
    tests = [
        ("Health Check", tester.test_health_check),
        ("Add Dummy Server", tester.add_dummy_server),
        ("List Servers", tester.list_servers),
        ("Direct Tool Call", tester.test_direct_tool_call),
        ("Multiple Tools", tester.test_multiple_tools),
        ("Session Management", tester.test_session_management),
        ("Query Processing", tester.test_query_processing),  # May fail without real LLM API
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
            time.sleep(1)  # Small delay between tests
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Start SSE test in background (optional)
    print(f"\n{'='*20} SSE Test {'='*20}")
    sse_thread = threading.Thread(
        target=run_sse_test, 
        args=(tester.base_url, tester.session_id),
        daemon=True
    )
    sse_thread.start()
    
    # Summary
    print(f"\n{'='*20} Test Summary {'='*20}")
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your MCP client is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the configuration and try again.")
        print("\nCommon issues:")
        print("- Make sure the MCP client Flask app is running on port 5000")
        print("- Ensure dummy_mcp_server.py is in the same directory")
        print("- Query processing may fail without a real LLM API configured")

if __name__ == "__main__":
    main()
