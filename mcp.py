import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import aiohttp
import websockets
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPTransportType(Enum):
    HTTP = "http"
    WEBSOCKET = "websocket"
    STDIO = "stdio"

@dataclass
class MCPServer:
    name: str
    url: str
    transport_type: MCPTransportType
    auth_token: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

@dataclass
class MCPTool:
    name: str
    description: str
    parameters: Dict[str, Any]
    server_name: str

@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: Optional[str] = None
    server_name: str = ""

class MCPClient:
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.connections: Dict[str, Any] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        
        # Close all connections
        for connection in self.connections.values():
            if hasattr(connection, 'close'):
                await connection.close()
    
    def add_server(self, server: MCPServer):
        """Add an MCP server configuration"""
        self.servers[server.name] = server
        logger.info(f"Added MCP server: {server.name} ({server.url})")
    
    async def connect_to_server(self, server_name: str) -> bool:
        """Connect to a specific MCP server"""
        if server_name not in self.servers:
            logger.error(f"Server {server_name} not found")
            return False
        
        server = self.servers[server_name]
        
        try:
            if server.transport_type == MCPTransportType.HTTP:
                await self._connect_http(server)
            elif server.transport_type == MCPTransportType.WEBSOCKET:
                await self._connect_websocket(server)
            else:
                logger.error(f"Transport type {server.transport_type} not implemented")
                return False
            
            # Discover tools and resources
            await self._discover_capabilities(server_name)
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {server_name}: {e}")
            return False
    
    async def _connect_http(self, server: MCPServer):
        """Establish HTTP connection to MCP server"""
        headers = server.headers or {}
        if server.auth_token:
            headers['Authorization'] = f'Bearer {server.auth_token}'
        
        # Test connection with a ping/health check
        async with self.session.get(f"{server.url}/health", headers=headers) as response:
            if response.status == 200:
                self.connections[server.name] = {
                    'type': 'http',
                    'base_url': server.url,
                    'headers': headers
                }
                logger.info(f"HTTP connection established to {server.name}")
            else:
                raise Exception(f"Health check failed: {response.status}")
    
    async def _connect_websocket(self, server: MCPServer):
        """Establish WebSocket connection to MCP server"""
        headers = {}
        if server.auth_token:
            headers['Authorization'] = f'Bearer {server.auth_token}'
        
        websocket = await websockets.connect(server.url, extra_headers=headers)
        self.connections[server.name] = {
            'type': 'websocket',
            'websocket': websocket
        }
        logger.info(f"WebSocket connection established to {server.name}")
    
    async def _discover_capabilities(self, server_name: str):
        """Discover tools and resources available on the server"""
        try:
            # Discover tools
            tools_response = await self._send_request(server_name, {
                "jsonrpc": "2.0",
                "id": "discover_tools",
                "method": "tools/list"
            })
            
            if tools_response and 'result' in tools_response:
                for tool_data in tools_response['result'].get('tools', []):
                    tool = MCPTool(
                        name=tool_data['name'],
                        description=tool_data.get('description', ''),
                        parameters=tool_data.get('inputSchema', {}),
                        server_name=server_name
                    )
                    self.tools[f"{server_name}:{tool.name}"] = tool
                    logger.info(f"Discovered tool: {tool.name} on {server_name}")
            
            # Discover resources
            resources_response = await self._send_request(server_name, {
                "jsonrpc": "2.0",
                "id": "discover_resources",
                "method": "resources/list"
            })
            
            if resources_response and 'result' in resources_response:
                for resource_data in resources_response['result'].get('resources', []):
                    resource = MCPResource(
                        uri=resource_data['uri'],
                        name=resource_data.get('name', ''),
                        description=resource_data.get('description', ''),
                        mime_type=resource_data.get('mimeType'),
                        server_name=server_name
                    )
                    self.resources[resource.uri] = resource
                    logger.info(f"Discovered resource: {resource.name} ({resource.uri}) on {server_name}")
                    
        except Exception as e:
            logger.error(f"Failed to discover capabilities for {server_name}: {e}")
    
    async def _send_request(self, server_name: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request to the server"""
        if server_name not in self.connections:
            logger.error(f"No connection to server {server_name}")
            return None
        
        connection = self.connections[server_name]
        
        try:
            if connection['type'] == 'http':
                return await self._send_http_request(connection, request)
            elif connection['type'] == 'websocket':
                return await self._send_websocket_request(connection, request)
        except Exception as e:
            logger.error(f"Failed to send request to {server_name}: {e}")
            return None
    
    async def _send_http_request(self, connection: Dict[str, Any], request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send HTTP request"""
        async with self.session.post(
            f"{connection['base_url']}/rpc",
            json=request,
            headers=connection['headers']
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"HTTP request failed: {response.status}")
                return None
    
    async def _send_websocket_request(self, connection: Dict[str, Any], request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send WebSocket request"""
        websocket = connection['websocket']
        await websocket.send(json.dumps(request))
        response = await websocket.recv()
        return json.loads(response)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call a tool on an MCP server"""
        if tool_name not in self.tools:
            logger.error(f"Tool {tool_name} not found")
            return None
        
        tool = self.tools[tool_name]
        server_name = tool.server_name
        
        request = {
            "jsonrpc": "2.0",
            "id": f"call_{tool_name}",
            "method": "tools/call",
            "params": {
                "name": tool.name,
                "arguments": arguments
            }
        }
        
        response = await self._send_request(server_name, request)
        
        if response and 'result' in response:
            logger.info(f"Tool {tool_name} executed successfully")
            return response['result']
        else:
            logger.error(f"Tool {tool_name} execution failed")
            return None
    
    async def read_resource(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """Read a resource from an MCP server"""
        if resource_uri not in self.resources:
            logger.error(f"Resource {resource_uri} not found")
            return None
        
        resource = self.resources[resource_uri]
        server_name = resource.server_name
        
        request = {
            "jsonrpc": "2.0",
            "id": f"read_{resource_uri}",
            "method": "resources/read",
            "params": {
                "uri": resource_uri
            }
        }
        
        response = await self._send_request(server_name, request)
        
        if response and 'result' in response:
            logger.info(f"Resource {resource_uri} read successfully")
            return response['result']
        else:
            logger.error(f"Failed to read resource {resource_uri}")
            return None
    
    def list_tools(self) -> List[MCPTool]:
        """List all available tools"""
        return list(self.tools.values())
    
    def list_resources(self) -> List[MCPResource]:
        """List all available resources"""
        return list(self.resources.values())
    
    def get_tool_info(self, tool_name: str) -> Optional[MCPTool]:
        """Get information about a specific tool"""
        return self.tools.get(tool_name)

# AI Sandbox Integration Class
class AISandboxMCPIntegration:
    def __init__(self, llm_api_client):
        self.llm_client = llm_api_client
        self.mcp_client = MCPClient()
        self.context_memory = []
    
    async def initialize(self, server_configs: List[Dict[str, Any]]):
        """Initialize the MCP client with server configurations"""
        async with self.mcp_client as client:
            # Add and connect to servers
            for config in server_configs:
                server = MCPServer(
                    name=config['name'],
                    url=config['url'],
                    transport_type=MCPTransportType(config.get('transport', 'http')),
                    auth_token=config.get('auth_token'),
                    headers=config.get('headers')
                )
                client.add_server(server)
                await client.connect_to_server(server.name)
            
            return client
    
    async def enhance_llm_with_mcp(self, user_query: str, server_configs: List[Dict[str, Any]]) -> str:
        """Enhance LLM response with MCP capabilities"""
        async with self.mcp_client as client:
            # Initialize MCP connections
            for config in server_configs:
                server = MCPServer(
                    name=config['name'],
                    url=config['url'],
                    transport_type=MCPTransportType(config.get('transport', 'http')),
                    auth_token=config.get('auth_token'),
                    headers=config.get('headers')
                )
                client.add_server(server)
                await client.connect_to_server(server.name)
            
            # Get available tools
            available_tools = client.list_tools()
            tools_context = "\n".join([
                f"- {tool.name}: {tool.description}" 
                for tool in available_tools
            ])
            
            # Enhance prompt with MCP context
            enhanced_prompt = f"""
            You have access to the following MCP tools:
            {tools_context}
            
            User query: {user_query}
            
            If you need to use any tools to answer this query, specify which tool to call and with what parameters.
            """
            
            # Get LLM response (placeholder - replace with your actual LLM API call)
            llm_response = await self._call_llm(enhanced_prompt)
            
            # Process tool calls if needed
            if "CALL_TOOL:" in llm_response:
                # Parse and execute tool calls
                # This is a simplified example - you'd want more sophisticated parsing
                tool_results = await self._execute_tool_calls(client, llm_response)
                
                # Get final response with tool results
                final_prompt = f"""
                Original query: {user_query}
                Tool results: {tool_results}
                
                Provide a comprehensive answer based on the tool results.
                """
                
                final_response = await self._call_llm(final_prompt)
                return final_response
            
            return llm_response
    
    async def _call_llm(self, prompt: str) -> str:
        """Placeholder for LLM API call - implement with your actual LLM client"""
        # Replace this with your actual LLM API integration
        return f"LLM Response to: {prompt}"
    
    async def _execute_tool_calls(self, client: MCPClient, llm_response: str) -> str:
        """Execute tool calls based on LLM response"""
        # This is a simplified parser - implement based on your LLM's output format
        results = []
        # Parse tool calls from LLM response and execute them
        # Return formatted results
        return "Tool execution results would go here"

# Example usage
async def main():
    # Example server configurations
    server_configs = [
        {
            'name': 'filesystem',
            'url': 'http://localhost:3001',
            'transport': 'http',
            'auth_token': None
        },
        {
            'name': 'web_search',
            'url': 'ws://localhost:3002',
            'transport': 'websocket',
            'auth_token': 'your-api-key'
        }
    ]
    
    # Initialize the AI Sandbox MCP Integration
    sandbox_integration = AISandboxMCPIntegration(llm_api_client=None)
    
    # Example usage
    response = await sandbox_integration.enhance_llm_with_mcp(
        "What files are in my current directory?",
        server_configs
    )
    
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
