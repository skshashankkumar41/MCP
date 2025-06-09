# MCP Client for AI Sandbox - Documentation

## Table of Contents
1. [Overview](#overview)
2. [What is MCP?](#what-is-mcp)
3. [Architecture](#architecture)
4. [How It Works](#how-it-works)
5. [Implementation Details](#implementation-details)
6. [Setup and Installation](#setup-and-installation)
7. [Configuration](#configuration)
8. [Usage Examples](#usage-examples)
9. [Available MCP Servers](#available-mcp-servers)
10. [Troubleshooting](#troubleshooting)

## Overview

This project creates an **MCP (Model Context Protocol) client** that enhances your AI sandbox environment by connecting it to external tools and data sources. Instead of your AI being limited to its training data, it can now:

- Access file systems
- Query databases
- Search the web
- Interact with APIs
- Process documents
- And much more!

## What is MCP?

**Model Context Protocol (MCP)** is an open-source protocol developed by Anthropic that allows AI systems to securely connect to external data sources and tools. Think of it as a standardized way for AI to "reach out" and interact with the real world.

### Key Concepts:

- **MCP Server**: A service that provides tools or resources (like a file system server, database server, etc.)
- **MCP Client**: Your application that connects to and uses MCP servers
- **Tools**: Functions that the AI can call (e.g., "read_file", "search_web")
- **Resources**: Data sources the AI can access (e.g., files, database records)
- **Transport**: How client and server communicate (stdio, WebSocket, HTTP)

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Query    │───▶│   AI Sandbox    │───▶│   LLM API       │
└─────────────────┘    │                 │    │ (GPT/Claude)    │
                       │                 │    └─────────────────┘
                       │                 │              │
                       │  ┌───────────┐  │              │
                       │  │    MCP    │  │              │
                       │  │  Client   │  │              ▼
                       │  └───────────┘  │    ┌─────────────────┐
                       │        │        │    │Enhanced Response│
                       └─────────────────┘    │  with Tool      │
                                │             │   Results       │
                     ┌──────────▼──────────┐  └─────────────────┘
                     │    MCP Servers      │
                     ├─────────────────────┤
                     │ • Filesystem        │
                     │ • Database          │
                     │ • Web Search        │
                     │ • Git Repository    │
                     │ • Custom APIs       │
                     └─────────────────────┘
```

## How It Works

### Step-by-Step Process:

1. **Initialization**
   - Your AI sandbox starts up
   - MCP client connects to configured MCP servers
   - Available tools and resources are discovered

2. **User Interaction**
   - User asks: "What files are in my project directory?"
   - AI sandbox receives the query

3. **Tool Discovery**
   - MCP client provides available tools to the LLM
   - LLM context includes: "You have access to filesystem tools like list_files, read_file..."

4. **LLM Decision Making**
   - LLM analyzes the query
   - Decides it needs to use the "list_files" tool
   - Returns structured response: `{"action": "use_tool", "tool": "filesystem:list_files", "arguments": {"path": "."}}`

5. **Tool Execution**
   - MCP client calls the filesystem server
   - Server executes the tool and returns results
   - Results are formatted and sent back

6. **Final Response**
   - LLM receives tool results
   - Generates human-readable response
   - User gets: "Here are the files in your project directory: main.py, config.json, README.md..."

## Implementation Details

### Core Components

#### 1. AISandboxMCPClient
This is the main MCP client that handles:
- **Server Management**: Connecting to multiple MCP servers
- **Protocol Handling**: Using official MCP SDK for communication
- **Tool Discovery**: Finding available tools and resources
- **Tool Execution**: Calling tools with proper parameters

```python
class AISandboxMCPClient:
    def __init__(self):
        self.sessions = {}      # Active server connections
        self.tools = {}         # Available tools catalog
        self.resources = {}     # Available resources catalog
```

#### 2. EnhancedAISandbox
This integrates the MCP client with your LLM:
- **Query Processing**: Analyzes user queries
- **Context Enhancement**: Adds tool information to LLM prompts
- **Tool Orchestration**: Handles tool calls and result processing
- **Response Generation**: Creates final responses

```python
class EnhancedAISandbox:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.mcp_client = AISandboxMCPClient()
```

### Communication Flow

#### 1. Server Connection (Stdio)
```python
# For servers that communicate via stdin/stdout
server_params = StdioServerParameters(
    command="npx",
    args=["@modelcontextprotocol/server-filesystem", "/path"]
)
async with stdio_client(server_params) as (read, write):
    session = ClientSession(read, write)
```

#### 2. Tool Discovery
```python
# Discover what tools are available
tools_response = await session.list_tools(ListToolsRequest())
for tool in tools_response.tools:
    self.tools[f"{server_name}:{tool.name}"] = tool
```

#### 3. Tool Execution
```python
# Call a tool with parameters
request = CallToolRequest(name=tool_name, arguments=arguments)
response = await session.call_tool(request)
```

## Setup and Installation

### Prerequisites
- Python 3.8+
- Node.js (for npm-based MCP servers)
- Your preferred LLM API access (OpenAI, Anthropic, etc.)

### Installation Steps

1. **Install Python Dependencies**
```bash
pip install mcp asyncio-subprocess
pip install anthropic  # or openai, depending on your LLM
```

2. **Install MCP Servers**
```bash
# Install common MCP servers
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-sqlite
npm install -g @modelcontextprotocol/server-brave-search
```

3. **Clone and Setup**
```bash
git clone <your-repo>
cd ai-sandbox-mcp
pip install -r requirements.txt
```

## Configuration

### Server Configuration Format

```python
server_configs = [
    {
        "name": "filesystem",           # Unique identifier
        "command": "npx",              # Command to start server
        "args": [                      # Command arguments
            "@modelcontextprotocol/server-filesystem", 
            "/path/to/directory"
        ],
        "env": {                       # Environment variables
            "CUSTOM_VAR": "value"
        }
    },
    {
        "name": "web_search",
        "command": "npx",
        "args": ["@modelcontextprotocol/server-brave-search"],
        "env": {
            "BRAVE_API_KEY": "your-api-key-here"
        }
    }
]
```

### LLM Integration

You need to implement the `_call_llm` method for your specific LLM provider:

#### For OpenAI:
```python
async def _call_llm(self, prompt: str) -> str:
    response = await self.openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

#### For Anthropic Claude:
```python
async def _call_llm(self, prompt: str) -> str:
    response = await self.anthropic_client.messages.create(
        model="claude-3-sonnet-20240229",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## Usage Examples

### Basic Usage

```python
async def main():
    # Initialize the sandbox
    sandbox = EnhancedAISandbox(your_llm_client)
    
    # Configure MCP servers
    await sandbox.setup_mcp_servers([
        {
            "name": "filesystem",
            "command": "npx",
            "args": ["@modelcontextprotocol/server-filesystem", "./"]
        }
    ])
    
    # Process queries
    response = await sandbox.process_query_with_mcp(
        "What Python files are in my current directory?"
    )
    
    print(response)
    await sandbox.shutdown()
```

### Advanced Multi-Tool Usage

```python
# User asks: "Find all Python files and show me the imports in main.py"
# The AI will:
# 1. Use filesystem:list_files to find Python files
# 2. Use filesystem:read_file to read main.py
# 3. Analyze the content and provide a comprehensive response
```

## Available MCP Servers

### Official Servers

1. **Filesystem Server**
   - **Purpose**: File system operations
   - **Tools**: list_files, read_file, write_file, create_directory
   - **Setup**: `npm install -g @modelcontextprotocol/server-filesystem`

2. **SQLite Server**
   - **Purpose**: SQLite database operations
   - **Tools**: execute_query, list_tables, describe_table
   - **Setup**: `npm install -g @modelcontextprotocol/server-sqlite`

3. **Git Server**
   - **Purpose**: Git repository operations
   - **Tools**: git_log, git_diff, git_status, git_show
   - **Setup**: `npm install -g @modelcontextprotocol/server-git`

4. **Brave Search Server**
   - **Purpose**: Web search capabilities
   - **Tools**: brave_web_search
   - **Setup**: `npm install -g @modelcontextprotocol/server-brave-search`
   - **Requirements**: Brave Search API key

5. **PostgreSQL Server**
   - **Purpose**: PostgreSQL database operations
   - **Tools**: execute_query, list_tables, describe_table
   - **Setup**: `npm install -g @modelcontextprotocol/server-postgres`

### Custom Servers

You can also create custom MCP servers for your specific needs:

```javascript
// Simple custom server example
const server = new Server({
  name: "my-custom-server",
  version: "1.0.0"
});

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: "custom_tool",
    description: "Does something custom",
    inputSchema: {
      type: "object",
      properties: {
        input: { type: "string" }
      }
    }
  }]
}));
```

## Troubleshooting

### Common Issues

#### 1. Server Connection Failures
**Problem**: MCP server won't start or connect
```
ERROR: Failed to connect to stdio server filesystem: [Errno 2] No such file or directory
```

**Solutions**:
- Check that the server is installed: `npm list -g @modelcontextprotocol/server-filesystem`
- Verify the command path is correct
- Check environment variables are set
- Ensure the target directory exists

#### 2. Tool Discovery Issues
**Problem**: No tools are discovered from server
```
INFO: Connected to stdio MCP server: filesystem
INFO: No tools discovered for filesystem
```

**Solutions**:
- Check server logs for errors
- Verify server supports the tools/list method
- Check server permissions
- Try manually testing the server

#### 3. LLM Integration Issues
**Problem**: LLM doesn't use tools properly
```
LLM Response: I cannot access files directly.
```

**Solutions**:
- Improve prompt engineering
- Add more specific tool descriptions
- Check tool schema formatting
- Verify LLM model supports function calling

#### 4. Permission Errors
**Problem**: Server can't access requested resources
```
ERROR: Permission denied accessing /path/to/file
```

**Solutions**:
- Check file/directory permissions
- Run with appropriate user privileges
- Configure server with correct paths
- Check environment variable paths

### Debugging Tips

1. **Enable Verbose Logging**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Test Server Independently**
```bash
# Test filesystem server manually
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | npx @modelcontextprotocol/server-filesystem /path
```

3. **Validate Configuration**
```python
# Add validation in your config
def validate_server_config(config):
    required_fields = ['name', 'command']
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
```

### Performance Considerations

1. **Connection Pooling**: Reuse MCP sessions when possible
2. **Caching**: Cache tool results for repeated queries
3. **Timeouts**: Set appropriate timeouts for tool calls
4. **Resource Limits**: Monitor memory usage with many servers

## Security Considerations

1. **Sandboxing**: Run MCP servers in isolated environments
2. **Authentication**: Use API keys and tokens where available
3. **Input Validation**: Validate all tool parameters
4. **Access Control**: Limit server access to necessary directories/resources
5. **Logging**: Log all tool calls for audit purposes

## Next Steps

1. **Start Simple**: Begin with filesystem server only
2. **Add Gradually**: Add more servers as needed
3. **Custom Tools**: Create custom MCP servers for your specific use cases
4. **Monitor Performance**: Track tool usage and response times
5. **Enhance Prompts**: Improve LLM prompts for better tool usage

This MCP integration transforms your AI sandbox from a static question-answering system into a dynamic, tool-using agent capable of interacting with real-world systems and data.
