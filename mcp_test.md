# MCP Client Setup and Testing Guide

## Quick Start

### 1. Requirements

Create a `requirements.txt` file:

```txt
flask==2.3.3
flask-cors==4.0.0
mcp==1.0.0
requests==2.31.0
asyncio-throttle==1.0.2
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. File Structure

```
mcp-client-test/
├── mcp_client.py          # Main MCP client Flask app
├── dummy_mcp_server.py    # Dummy MCP server for testing
├── test_mcp_flow.py       # Test script
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

### 3. Running the System

#### Step 1: Start the MCP Client Flask App
```bash
python mcp_client.py
```

This starts the Flask server on `http://localhost:5000`

#### Step 2: Run the Test Script
In another terminal:
```bash
python test_mcp_flow.py
```

### 4. Manual Testing

#### Add the Dummy Server
```bash
curl -X POST http://localhost:5000/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "dummy",
    "command": "python3",
    "args": ["dummy_mcp_server.py"],
    "env": {}
  }'
```

#### List Available Servers and Tools
```bash
curl http://localhost:5000/servers
```

#### Test Direct Tool Call
```bash
curl -X POST http://localhost:5000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server": "dummy",
    "tool": "calculator",
    "arguments": {
      "operation": "add",
      "a": 15,
      "b": 27
    }
  }'
```

#### Test Query Processing (requires LLM API)
```bash
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is 25 times 4?",
    "session_id": "test123",
    "llm_api_url": "https://api.openai.com/v1/chat/completions",
    "llm_headers": {
      "Authorization": "Bearer YOUR_API_KEY",
      "Content-Type": "application/json"
    }
  }'
```

## Available Dummy Server Tools

The dummy MCP server provides these tools for testing:

### 1. **calculator**
- **Purpose**: Perform basic math operations
- **Arguments**: 
  - `operation`: "add", "subtract", "multiply", "divide"
  - `a`: First number
  - `b`: Second number
- **Example**: `{"operation": "multiply", "a": 25, "b": 4}`

### 2. **get_current_time**
- **Purpose**: Get current date and time
- **Arguments**: None
- **Example**: `{}`

### 3. **store_data**
- **Purpose**: Store key-value data in memory
- **Arguments**:
  - `key`: Storage key
  - `value`: Value to store
- **Example**: `{"key": "user_name", "value": "John Doe"}`

### 4. **retrieve_data**
- **Purpose**: Retrieve stored data
- **Arguments**:
  - `key`: Key to retrieve
- **Example**: `{"key": "user_name"}`

### 5. **list_stored_keys**
- **Purpose**: List all stored keys
- **Arguments**: None
- **Example**: `{}`

### 6. **generate_random_number**
- **Purpose**: Generate random number in range
- **Arguments**:
  - `min_val`: Minimum value (default: 1)
  - `max_val`: Maximum value (default: 100)
- **Example**: `{"min_val": 1, "max_val": 10}`

### 7. **count_words**
- **Purpose**: Analyze text (word count, character count)
- **Arguments**:
  - `text`: Text to analyze
- **Example**: `{"text": "Hello world, this is a test."}`

### 8. **echo_message**
- **Purpose**: Echo message with repetition
- **Arguments**:
  - `message`: Message to echo
  - `repeat`: Number of repetitions (1-10)
- **Example**: `{"message": "Hello!", "repeat": 3}`

### 9. **system_info**
- **Purpose**: Get server system information
- **Arguments**: None
- **Example**: `{}`

## Testing Server-Sent Events (SSE)

### JavaScript Example
```html
<!DOCTYPE html>
<html>
<head>
    <title>MCP Client Test</title>
</head>
<body>
    <div id="events"></div>
    <button onclick="testQuery()">Test Query</button>

    <script>
        const sessionId = 'test_' + Date.now();
        
        // Setup SSE
        const eventSource = new EventSource(`http://localhost:5000/events/${sessionId}`);
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const eventsDiv = document.getElementById('events');
            eventsDiv.innerHTML += `<p>${data.type}: ${data.message}</p>`;
        };
        
        async function testQuery() {
            const response = await fetch('http://localhost:5000/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: 'What is 15 + 27?',
                    session_id: sessionId,
                    llm_api_url: 'YOUR_LLM_API_URL',
                    llm_headers: { 'Authorization': 'Bearer YOUR_API_KEY' }
                })
            });
            
            const result = await response.json();
            console.log('Result:', result);
        }
    </script>
</body>
</html>
```

## Troubleshooting

### Common Issues

1. **"Server connection failed"**
   - Make sure Flask app is running on port 5000
   - Check that dummy_mcp_server.py is in the same directory

2. **"Tool call failed"**
   - Verify the dummy server is properly connected
   - Check tool arguments match the expected schema

3. **"Query processing failed"**
   - This is expected without a real LLM API
   - Configure your LLM API URL and headers for full testing

4. **SSE not working**
   - Check CORS settings
   - Ensure browser supports EventSource
   - Verify session ID matches

### Logs and Debugging

The Flask app provides detailed logging. Check the console output for:
- Server connection status
- Tool call details
- Error messages
- SSE event publishing

### Testing Without LLM

You can test most functionality without configuring an LLM API:
- Direct tool calls work independently
- Server management works
- Session management works
- SSE works

Only the `/query` endpoint requires LLM integration for intelligent tool selection.

## Next Steps

Once you've verified the dummy server works:

1. **Replace with Real MCP Servers**: Add actual MCP servers for your use case
2. **Configure LLM API**: Set up your preferred LLM for query processing
3. **Add Authentication**: Implement proper auth for production
4. **Scale**: Add connection pooling, caching, and error handling
5. **Monitor**: Add logging and metrics

## Production Considerations

- Use a proper WSGI server (gunicorn, uwsgi)
- Implement authentication and authorization
- Add rate limiting
- Configure proper logging
- Add health checks and monitoring
- Use persistent storage instead of in-memory data
- Implement proper error handling and retries
