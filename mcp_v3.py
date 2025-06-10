import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from flask import Flask, request, jsonify
from threading import Thread
import time
from datetime import datetime, timedelta

# MCP SDK imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CallToolRequest,
    ListToolsRequest,
    GetPromptRequest,
    ListPromptsRequest,
    ListResourcesRequest,
    ReadResourceRequest,
    CreateMessageRequest,
    Tool,
    Prompt,
    Resource,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None

@dataclass
class ConversationMessage:
    """Represents a message in a conversation"""
    role: str
    content: str
    timestamp: datetime
    tool_calls: Optional[List[Dict]] = None

class ConversationSession:
    """Manages conversation state for a session"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[ConversationMessage] = []
        self.last_activity = datetime.now()
        self.context: Dict[str, Any] = {}
    
    def add_message(self, role: str, content: str, tool_calls: Optional[List[Dict]] = None):
        """Add a message to the conversation"""
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            tool_calls=tool_calls
        )
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_context(self) -> List[Dict]:
        """Get conversation context for LLM"""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in self.messages
        ]
    
    def clear_context(self):
        """Clear conversation context"""
        self.messages.clear()
        self.context.clear()

class MCPServerConnection:
    """Manages connection to a single MCP server"""
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.session: Optional[ClientSession] = None
        self.is_connected = False
        self.tools: List[Tool] = []
        self.prompts: List[Prompt] = []
        self.resources: List[Resource] = []
        self.last_sync = None
    
    async def connect(self):
        """Connect to the MCP server"""
        try:
            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env or {}
            )
            
            self.session = await stdio_client(server_params).__aenter__()
            self.is_connected = True
            
            # Initialize server capabilities
            await self.sync_capabilities()
            
            logger.info(f"Connected to MCP server: {self.config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.config.name}: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error disconnecting from {self.config.name}: {e}")
            finally:
                self.session = None
                self.is_connected = False
    
    async def sync_capabilities(self):
        """Sync server capabilities (tools, prompts, resources)"""
        if not self.session:
            return
        
        try:
            # List tools
            tools_response = await self.session.list_tools(ListToolsRequest())
            self.tools = tools_response.tools
            
            # List prompts
            try:
                prompts_response = await self.session.list_prompts(ListPromptsRequest())
                self.prompts = prompts_response.prompts
            except Exception:
                self.prompts = []  # Server might not support prompts
            
            # List resources
            try:
                resources_response = await self.session.list_resources(ListResourcesRequest())
                self.resources = resources_response.resources
            except Exception:
                self.resources = []  # Server might not support resources
            
            self.last_sync = datetime.now()
            logger.info(f"Synced capabilities for {self.config.name}: "
                       f"{len(self.tools)} tools, {len(self.prompts)} prompts, "
                       f"{len(self.resources)} resources")
            
        except Exception as e:
            logger.error(f"Failed to sync capabilities for {self.config.name}: {e}")
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Call a tool on this server"""
        if not self.session or not self.is_connected:
            raise Exception(f"Not connected to server {self.config.name}")
        
        try:
            request = CallToolRequest(name=tool_name, arguments=arguments)
            response = await self.session.call_tool(request)
            return {
                "success": True,
                "content": response.content,
                "server": self.config.name
            }
        except Exception as e:
            logger.error(f"Tool call failed on {self.config.name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "server": self.config.name
            }

class MCPClientManager:
    """Manages multiple MCP server connections and sessions"""
    def __init__(self):
        self.servers: Dict[str, MCPServerConnection] = {}
        self.sessions: Dict[str, ConversationSession] = {}
        self.loop = None
        self.background_thread = None
        self.running = False
        
        # Session cleanup settings
        self.session_timeout = timedelta(hours=2)
        self.cleanup_interval = 300  # 5 minutes
    
    def start_background_loop(self):
        """Start the background asyncio loop"""
        if self.background_thread and self.background_thread.is_alive():
            return
        
        self.running = True
        self.background_thread = Thread(target=self._run_background_loop, daemon=True)
        self.background_thread.start()
        
        # Wait for loop to be ready
        while self.loop is None:
            time.sleep(0.1)
    
    def _run_background_loop(self):
        """Run the background asyncio loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Schedule periodic cleanup
        self.loop.create_task(self._periodic_cleanup())
        
        self.loop.run_forever()
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of expired sessions"""
        while self.running:
            await asyncio.sleep(self.cleanup_interval)
            await self._cleanup_expired_sessions()
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if now - session.last_activity > self.session_timeout
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")
    
    def run_async(self, coro):
        """Run an async function in the background loop"""
        if not self.loop:
            self.start_background_loop()
        
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=30)  # 30 second timeout
    
    def add_server(self, config: MCPServerConfig) -> bool:
        """Add and connect to an MCP server"""
        if config.name in self.servers:
            logger.warning(f"Server {config.name} already exists")
            return False
        
        connection = MCPServerConnection(config)
        success = self.run_async(connection.connect())
        
        if success:
            self.servers[config.name] = connection
            logger.info(f"Added MCP server: {config.name}")
            return True
        
        return False
    
    def remove_server(self, server_name: str) -> bool:
        """Remove and disconnect from an MCP server"""
        if server_name not in self.servers:
            return False
        
        connection = self.servers[server_name]
        self.run_async(connection.disconnect())
        del self.servers[server_name]
        
        logger.info(f"Removed MCP server: {server_name}")
        return True
    
    def get_session(self, session_id: str) -> ConversationSession:
        """Get or create a conversation session"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationSession(session_id)
        
        session = self.sessions[session_id]
        session.last_activity = datetime.now()
        return session
    
    def get_all_tools(self) -> Dict[str, List[Dict]]:
        """Get all available tools from all servers"""
        all_tools = {}
        for server_name, connection in self.servers.items():
            if connection.is_connected:
                all_tools[server_name] = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in connection.tools
                ]
        return all_tools
    
    def call_tool(self, tool_name: str, arguments: Dict, server_name: Optional[str] = None) -> Dict:
        """Call a tool on a specific server or find it automatically"""
        if server_name:
            # Call on specific server
            if server_name not in self.servers:
                return {"success": False, "error": f"Server {server_name} not found"}
            
            connection = self.servers[server_name]
            return self.run_async(connection.call_tool(tool_name, arguments))
        
        # Find tool across all servers
        for server_name, connection in self.servers.items():
            if connection.is_connected:
                tool_names = [tool.name for tool in connection.tools]
                if tool_name in tool_names:
                    return self.run_async(connection.call_tool(tool_name, arguments))
        
        return {"success": False, "error": f"Tool {tool_name} not found on any server"}
    
    def get_server_status(self) -> Dict[str, Dict]:
        """Get status of all servers"""
        status = {}
        for server_name, connection in self.servers.items():
            status[server_name] = {
                "connected": connection.is_connected,
                "tools_count": len(connection.tools),
                "prompts_count": len(connection.prompts),
                "resources_count": len(connection.resources),
                "last_sync": connection.last_sync.isoformat() if connection.last_sync else None
            }
        return status

# Initialize the MCP client manager
mcp_manager = MCPClientManager()

# Flask application
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "servers": len(mcp_manager.servers),
        "active_sessions": len(mcp_manager.sessions)
    })

@app.route('/servers', methods=['GET'])
def list_servers():
    """List all MCP servers"""
    return jsonify(mcp_manager.get_server_status())

@app.route('/servers', methods=['POST'])
def add_server():
    """Add a new MCP server"""
    data = request.get_json()
    
    if not data or 'name' not in data or 'command' not in data:
        return jsonify({"error": "Missing required fields: name, command"}), 400
    
    config = MCPServerConfig(
        name=data['name'],
        command=data['command'],
        args=data.get('args', []),
        env=data.get('env')
    )
    
    success = mcp_manager.add_server(config)
    
    if success:
        return jsonify({"message": f"Server {config.name} added successfully"})
    else:
        return jsonify({"error": f"Failed to add server {config.name}"}), 500

@app.route('/servers/<server_name>', methods=['DELETE'])
def remove_server(server_name):
    """Remove an MCP server"""
    success = mcp_manager.remove_server(server_name)
    
    if success:
        return jsonify({"message": f"Server {server_name} removed successfully"})
    else:
        return jsonify({"error": f"Server {server_name} not found"}), 404

@app.route('/tools', methods=['GET'])
def list_tools():
    """List all available tools"""
    return jsonify(mcp_manager.get_all_tools())

@app.route('/tools/call', methods=['POST'])
def call_tool():
    """Call a tool"""
    data = request.get_json()
    
    if not data or 'tool_name' not in data:
        return jsonify({"error": "Missing required field: tool_name"}), 400
    
    tool_name = data['tool_name']
    arguments = data.get('arguments', {})
    server_name = data.get('server_name')
    session_id = data.get('session_id')
    
    # Call the tool
    result = mcp_manager.call_tool(tool_name, arguments, server_name)
    
    # If session_id provided, add to conversation context
    if session_id:
        session = mcp_manager.get_session(session_id)
        session.add_message(
            role="assistant",
            content=f"Called tool {tool_name}",
            tool_calls=[{
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result
            }]
        )
    
    return jsonify(result)

@app.route('/sessions/<session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """Get conversation messages for a session"""
    session = mcp_manager.get_session(session_id)
    return jsonify({
        "session_id": session_id,
        "messages": session.get_context()
    })

@app.route('/sessions/<session_id>/messages', methods=['POST'])
def add_session_message(session_id):
    """Add a message to a session"""
    data = request.get_json()
    
    if not data or 'role' not in data or 'content' not in data:
        return jsonify({"error": "Missing required fields: role, content"}), 400
    
    session = mcp_manager.get_session(session_id)
    session.add_message(
        role=data['role'],
        content=data['content'],
        tool_calls=data.get('tool_calls')
    )
    
    return jsonify({"message": "Message added successfully"})

@app.route('/sessions/<session_id>/clear', methods=['POST'])
def clear_session(session_id):
    """Clear a session's conversation context"""
    session = mcp_manager.get_session(session_id)
    session.clear_context()
    
    return jsonify({"message": "Session cleared successfully"})

@app.route('/sessions', methods=['GET'])
def list_sessions():
    """List all active sessions"""
    sessions_info = {}
    for session_id, session in mcp_manager.sessions.items():
        sessions_info[session_id] = {
            "message_count": len(session.messages),
            "last_activity": session.last_activity.isoformat()
        }
    
    return jsonify(sessions_info)

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint that handles conversation with tool calling"""
    data = request.get_json()
    
    if not data or 'message' not in data or 'session_id' not in data:
        return jsonify({"error": "Missing required fields: message, session_id"}), 400
    
    session_id = data['session_id']
    message = data['message']
    
    # Get session
    session = mcp_manager.get_session(session_id)
    
    # Add user message
    session.add_message(role="user", content=message)
    
    # Get conversation context
    context = session.get_context()
    
    # Get available tools
    available_tools = mcp_manager.get_all_tools()
    
    return jsonify({
        "session_id": session_id,
        "context": context,
        "available_tools": available_tools,
        "message": "Context updated. Use available tools and LLM to generate response."
    })

if __name__ == '__main__':
    # Example of adding servers on startup
    example_servers = [
        {
            "name": "filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        },
        {
            "name": "brave-search",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": "your-api-key-here"}
        }
    ]
    
    # Start the background loop
    mcp_manager.start_background_loop()
    
    # Add example servers
    for server_config in example_servers:
        config = MCPServerConfig(
            name=server_config["name"],
            command=server_config["command"],
            args=server_config["args"],
            env=server_config.get("env")
        )
        mcp_manager.add_server(config)
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
