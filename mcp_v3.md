# MCP Client with Flask API - Usage Guide

## Overview

This MCP client provides a Flask-based REST API that can connect to multiple MCP servers simultaneously and manage multi-session conversations. Each MCP client instance can connect to multiple MCP servers, and the system handles session management with in-memory caching.

## Key Features

- **Multiple Server Connections**: Connect to multiple MCP servers simultaneously
- **Session Management**: Handle multiple conversations with session isolation
- **In-Memory Caching**: Store conversation history and context per session
- **RESTful API**: Clean Flask-based API for integration
- **Automatic Cleanup**: Expired sessions are automatically cleaned up
- **Tool Discovery**: Automatically discover and list tools from all connected servers

## Architecture

- **MCPClientManager**: Main orchestrator managing servers and sessions
- **MCPServerConnection**: Individual connection to each MCP server
- **ConversationSession**: Session-specific conversation state
- **Flask API**: REST endpoints for external integration

## Installation

```bash
pip install -r requirements.txt
```

## Starting the Server

```python
python mcp_client.py
```

The server will start on `http://localhost:5000`

## API Endpoints

### Server Management

#### Add MCP Server
```bash
POST /servers
Content-Type: application/json

{
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"],
    "env": {
        "SOME_ENV_VAR": "value"
    }
}
```

#### List Servers
```bash
GET /servers
```

#### Remove Server
```bash
DELETE /servers/{server_name}
```

### Tool Management

#### List All Tools
```bash
GET /tools
```

#### Call a Tool
```bash
POST /tools/call
Content-Type: application/json

{
    "tool_name": "read_file",
    "arguments": {
        "path": "/tmp/example.txt"
    },
    "server_name": "filesystem",  // optional - auto-discover if not provided
    "session_id": "user123"       // optional - for conversation tracking
}
```

### Session Management

#### Get Session Messages
```bash
GET /sessions/{session_id}/messages
```

#### Add Message to Session
```bash
POST /sessions/{session_id}/messages
Content-Type: application/json

{
    "role": "user",
    "content": "Hello, can you help me read a file?",
    "tool_calls": []  // optional
}
```

#### Clear Session
```bash
POST /sessions/{session_id}/clear
```

#### List All Sessions
```bash
GET /sessions
```

### Chat Interface

#### Main Chat Endpoint
```bash
POST /chat
Content-Type: application/json

{
    "session_id": "user123",
    "message": "Can you list the files in /tmp directory?"
}
```

Response includes conversation context and available tools for your LLM to use.

## Integration with Your AI Sandbox

### Step 1: Setup MCP Servers

```python
import requests

# Add filesystem server
requests.post('http://localhost:5000/servers', json={
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
})

# Add web search server
requests.post('http://localhost:5000/servers', json={
    "name": "brave-search",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": {"BRAVE_API_KEY": "your-api-key"}
})
```

### Step 2: Chat Flow

```python
def handle_user_query(session_id, user_message):
    # Send user message to chat endpoint
    response = requests.post('http://localhost:5000/chat', json={
        "session_id": session_id,
        "message": user_message
    })
    
    chat_data = response.json()
    
    # Get conversation context and available tools
    context = chat_data['context']
    available_tools = chat_data['available_tools']
    
    # Send to your LLM with tools
    llm_response = your_llm_api_call(
        messages=context,
        tools=available_tools
    )
    
    # If LLM wants to call tools
    if llm_response.get('tool_calls'):
        for tool_call in llm_response['tool_calls']:
            tool_result = requests.post('http://localhost:5000/tools/call', json={
                "tool_name": tool_call['name'],
                "arguments": tool_call['arguments'],
                "session_id": session_id
            })
            
            # Add tool result to session
            requests.post(f'http://localhost:5000/sessions/{session_id}/messages', json={
                "role": "assistant",
                "content": f"Used tool {tool_call['name']}",
                "tool_calls": [tool_result.json()]
            })
    
    # Add final response to session
    requests.post(f'http://localhost:5000/sessions/{session_id}/messages', json={
        "role": "assistant",
        "content": llm_response['content']
    })
    
    return llm_response['content']
```

## Configuration Examples

### Common MCP Servers

#### Filesystem Server
```json
{
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
}
```

#### Brave Search Server
```json
{
    "name": "brave-search",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": {"BRAVE_API_KEY": "your-api-key"}
}
```

#### Git Server
```json
{
    "name": "git",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-git", "/path/to/repo"]
}
```

#### SQLite Server
```json
{
    "name": "sqlite",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-sqlite", "/path/to/database.db"]
}
```

## Session Management

- **Automatic Cleanup**: Sessions older than 2 hours are automatically cleaned up
- **In-Memory Storage**: All conversation data is stored in memory (not persistent)
- **Session Isolation**: Each session maintains separate conversation context
- **Thread-Safe**: Concurrent sessions are handled safely

## Error Handling

The API provides comprehensive error handling:

- Server connection failures are logged and reported
- Tool call failures return structured error responses
- Session timeouts are handled gracefully
- Invalid requests return appropriate HTTP status codes

## Monitoring

### Health Check
```bash
GET /health
```

Returns system status including active servers and sessions.

## Best Practices

1. **Session IDs**: Use unique, meaningful session IDs (user IDs, conversation IDs)
2. **Tool Discovery**: Let the system auto-discover tools when possible
3. **Error Handling**: Always check tool call responses for errors
4. **Session Cleanup**: Clear sessions when conversations end
5. **Server Management**: Add servers at startup or dynamically as needed

## Scaling Considerations

- **Memory Usage**: Sessions are stored in memory - monitor for large deployments
- **Connection Limits**: Each MCP server connection uses resources
- **Concurrent Requests**: Flask development server - use production WSGI for scale
- **Session Limits**: Consider implementing session limits for resource management

## Troubleshooting

### Common Issues

1. **Server Connection Failed**: Check MCP server command and arguments
2. **Tool Not Found**: Verify server is connected and tool exists
3. **Session Timeout**: Sessions expire after 2 hours of inactivity
4. **Port Already in Use**: Change the Flask port in the startup code
