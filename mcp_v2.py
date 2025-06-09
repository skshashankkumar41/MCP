# requirements.txt
"""
mcp
asyncio-subprocess
anthropic  # or openai, depending on your LLM provider
aiofiles
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Official MCP Python SDK imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.types import (
    CallToolRequest,
    ListToolsRequest, 
    ListResourcesRequest,
    ReadResourceRequest,
    Tool,
    Resource
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    name: str
    command: str  # For stdio servers like ["python", "server.py"]
    args: List[str] = None
    env: Dict[str, str] = None
    # For SSE servers
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

class AISandboxMCPClient:
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, Tool] = {}
        self.resources: Dict[str, Resource] = {}
        self.server_configs: Dict[str, MCPServerConfig] = {}
    
    async def add_stdio_server(self, config: MCPServerConfig):
        """Add an MCP server that communicates via stdio"""
        try:
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args or [],
                env=config.env or {}
            )
            
            async with stdio_client(server_params) as (read, write):
                session = ClientSession(read, write)
                await session.initialize()
                
                self.sessions[config.name] = session
                self.server_configs[config.name] = config
                
                # Discover capabilities
                await self._discover_server_capabilities(config.name)
                
                logger.info(f"Connected to stdio MCP server: {config.name}")
                
        except Exception as e:
            logger.error(f"Failed to connect to stdio server {config.name}: {e}")
    
    async def add_sse_server(self, config: MCPServerConfig):
        """Add an MCP server that communicates via Server-Sent Events"""
        if not config.url:
            raise ValueError("SSE server requires URL")
            
        try:
            async with sse_client(config.url, headers=config.headers or {}) as (read, write):
                session = ClientSession(read, write)
                await session.initialize()
                
                self.sessions[config.name] = session
                self.server_configs[config.name] = config
                
                # Discover capabilities
                await self._discover_server_capabilities(config.name)
                
                logger.info(f"Connected to SSE MCP server: {config.name}")
                
        except Exception as e:
            logger.error(f"Failed to connect to SSE server {config.name}: {e}")
    
    async def _discover_server_capabilities(self, server_name: str):
        """Discover tools and resources from a server"""
        session = self.sessions[server_name]
        
        try:
            # List available tools
            tools_response = await session.list_tools(ListToolsRequest())
            for tool in tools_response.tools:
                tool_key = f"{server_name}:{tool.name}"
                self.tools[tool_key] = tool
                logger.info(f"Discovered tool: {tool.name} on {server_name}")
            
            # List available resources
            try:
                resources_response = await session.list_resources(ListResourcesRequest())
                for resource in resources_response.resources:
                    resource_key = f"{server_name}:{resource.uri}"
                    self.resources[resource_key] = resource
                    logger.info(f"Discovered resource: {resource.name} ({resource.uri}) on {server_name}")
            except Exception as e:
                logger.info(f"Server {server_name} doesn't support resources or error occurred: {e}")
                
        except Exception as e:
            logger.error(f"Failed to discover capabilities for {server_name}: {e}")
    
    async def call_tool(self, tool_key: str, arguments: Dict[str, Any]) -> Optional[Any]:
        """Call a tool on an MCP server"""
        if tool_key not in self.tools:
            logger.error(f"Tool {tool_key} not found")
            return None
        
        # Extract server name and tool name
        server_name, tool_name = tool_key.split(':', 1)
        
        if server_name not in self.sessions:
            logger.error(f"No session for server {server_name}")
            return None
        
        session = self.sessions[server_name]
        
        try:
            request = CallToolRequest(
                name=tool_name,
                arguments=arguments
            )
            
            response = await session.call_tool(request)
            logger.info(f"Successfully called tool {tool_name} on {server_name}")
            return response.content
            
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {server_name}: {e}")
            return None
    
    async def read_resource(self, resource_key: str) -> Optional[Any]:
        """Read a resource from an MCP server"""
        if resource_key not in self.resources:
            logger.error(f"Resource {resource_key} not found")
            return None
        
        # Extract server name
        server_name = resource_key.split(':', 1)[0]
        resource = self.resources[resource_key]
        
        if server_name not in self.sessions:
            logger.error(f"No session for server {server_name}")
            return None
        
        session = self.sessions[server_name]
        
        try:
            request = ReadResourceRequest(uri=resource.uri)
            response = await session.read_resource(request)
            logger.info(f"Successfully read resource {resource.uri} from {server_name}")
            return response.contents
            
        except Exception as e:
            logger.error(f"Failed to read resource {resource.uri} from {server_name}: {e}")
            return None
    
    def get_available_tools(self) -> Dict[str, Tool]:
        """Get all available tools"""
        return self.tools.copy()
    
    def get_available_resources(self) -> Dict[str, Resource]:
        """Get all available resources"""
        return self.resources.copy()
    
    async def close_all_sessions(self):
        """Close all MCP sessions"""
        for session in self.sessions.values():
            try:
                await session.close()
            except Exception as e:
                logger.error(f"Error closing session: {e}")
        
        self.sessions.clear()
        self.tools.clear()
        self.resources.clear()

class EnhancedAISandbox:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.mcp_client = AISandboxMCPClient()
        self.conversation_history = []
    
    async def setup_mcp_servers(self, server_configs: List[Dict[str, Any]]):
        """Setup MCP servers based on configuration"""
        for config_data in server_configs:
            config = MCPServerConfig(**config_data)
            
            if config.url:
                # SSE server
                await self.mcp_client.add_sse_server(config)
            else:
                # Stdio server
                await self.mcp_client.add_stdio_server(config)
    
    async def process_query_with_mcp(self, user_query: str) -> str:
        """Process user query with MCP tool integration"""
        
        # Get available tools context
        available_tools = self.mcp_client.get_available_tools()
        tools_description = self._format_tools_for_llm(available_tools)
        
        # Create enhanced prompt
        system_prompt = f"""
You are an AI assistant with access to external tools via MCP (Model Context Protocol).

Available tools:
{tools_description}

Instructions:
- If you need to use a tool to answer the user's question, respond with a JSON object containing:
  {{"action": "use_tool", "tool": "server:tool_name", "arguments": {{...}}}}
- If you can answer without tools, respond normally
- If you need multiple tools, specify them in sequence

User query: {user_query}
"""
        
        # Get LLM response
        llm_response = await self._call_llm(system_prompt)
        
        # Check if LLM wants to use tools
        if self._is_tool_call(llm_response):
            return await self._handle_tool_calls(llm_response, user_query)
        
        return llm_response
    
    def _format_tools_for_llm(self, tools: Dict[str, Tool]) -> str:
        """Format tools information for LLM context"""
        if not tools:
            return "No tools available."
        
        formatted = []
        for tool_key, tool in tools.items():
            formatted.append(f"- {tool_key}: {tool.description}")
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                schema = tool.inputSchema
                if 'properties' in schema:
                    params = ', '.join(schema['properties'].keys())
                    formatted.append(f"  Parameters: {params}")
        
        return '\n'.join(formatted)
    
    def _is_tool_call(self, response: str) -> bool:
        """Check if LLM response contains a tool call"""
        try:
            parsed = json.loads(response.strip())
            return isinstance(parsed, dict) and parsed.get('action') == 'use_tool'
        except (json.JSONDecodeError, AttributeError):
            return False
    
    async def _handle_tool_calls(self, llm_response: str, original_query: str) -> str:
        """Handle tool calls from LLM"""
        try:
            tool_request = json.loads(llm_response.strip())
            tool_key = tool_request['tool']
            arguments = tool_request.get('arguments', {})
            
            # Execute the tool
            tool_result = await self.mcp_client.call_tool(tool_key, arguments)
            
            # Get final response from LLM with tool results
            final_prompt = f"""
Original question: {original_query}

Tool used: {tool_key}
Tool result: {json.dumps(tool_result, indent=2)}

Please provide a comprehensive answer to the original question based on the tool results.
"""
            
            return await self._call_llm(final_prompt)
            
        except Exception as e:
            logger.error(f"Error handling tool calls: {e}")
            return f"I encountered an error while using the tools: {e}"
    
    async def _call_llm(self, prompt: str) -> str:
        """Call your LLM API - implement this based on your provider"""
        # Example for OpenAI/Anthropic - replace with your actual implementation
        if self.llm_client:
            # Assuming you have an async LLM client
            response = await self.llm_client.complete(prompt)
            return response
        else:
            # Placeholder response
            return f"LLM would respond to: {prompt[:100]}..."
    
    async def shutdown(self):
        """Clean shutdown"""
        await self.mcp_client.close_all_sessions()

# Example usage and server configurations
async def main():
    """Example usage of the MCP-enhanced AI sandbox"""
    
    # Example server configurations
    server_configs = [
        {
            "name": "filesystem",
            "command": "python",
            "args": ["-m", "mcp_server_filesystem", "/path/to/directory"],
        },
        {
            "name": "database", 
            "command": "node",
            "args": ["database-mcp-server.js"],
            "env": {"DB_CONNECTION": "sqlite:///data.db"}
        },
        {
            "name": "web_api",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer your-token"}
        }
    ]
    
    # Initialize the enhanced sandbox
    sandbox = EnhancedAISandbox()
    
    try:
        # Setup MCP servers
        await sandbox.setup_mcp_servers(server_configs)
        
        # Process queries
        response1 = await sandbox.process_query_with_mcp(
            "What files are in my current directory?"
        )
        print("Response 1:", response1)
        
        response2 = await sandbox.process_query_with_mcp(
            "Can you search for recent news about AI?"
        )
        print("Response 2:", response2)
        
    finally:
        await sandbox.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
