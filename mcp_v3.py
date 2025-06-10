import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
import time

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    Tool, 
    TextContent, 
    ImageContent, 
    EmbeddedResource,
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListResourcesRequest,
    ReadResourceRequest,
    GetPromptRequest,
    ListPromptsRequest
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None

@dataclass
class SessionData:
    session_id: str
    conversation_history: List[Dict[str, Any]]
    created_at: datetime
    last_activity: datetime

@dataclass
class MCPConnection:
    name: str
    session: ClientSession
    tools: List[Tool]
    resources: List[Any]
    prompts: List[Any]
    is_connected: bool = False

class MCPClientManager:
    def __init__(self):
        self.connections: Dict[str, MCPConnection] = {}
        self.sessions: Dict[str, SessionData] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.event_queues: Dict[str, List[Dict]] = {}
        
    async def add_server(self, config: ServerConfig) -> bool:
        """Add and connect to an MCP server"""
        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env or {}
            )
            
            # Create stdio client
            stdio_transport = stdio_client(server_params)
            
            # Create session
            async with stdio_transport as (read, write):
                session = ClientSession(read, write)
                
                # Initialize the session
                await session.initialize()
                
                # Get available tools
                tools_response = await session.call_tool(ListToolsRequest())
                tools = tools_response.tools if hasattr(tools_response, 'tools') else []
                
                # Get available resources
                try:
                    resources_response = await session.call_tool(ListResourcesRequest())
                    resources = resources_response.resources if hasattr(resources_response, 'resources') else []
                except:
                    resources = []
                
                # Get available prompts
                try:
                    prompts_response = await session.call_tool(ListPromptsRequest())
                    prompts = prompts_response.prompts if hasattr(prompts_response, 'prompts') else []
                except:
                    prompts = []
                
                # Store connection
                self.connections[config.name] = MCPConnection(
                    name=config.name,
                    session=session,
                    tools=tools,
                    resources=resources,
                    prompts=prompts,
                    is_connected=True
                )
                
                logger.info(f"Successfully connected to MCP server: {config.name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {config.name}: {str(e)}")
            return False
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific MCP server"""
        if server_name not in self.connections:
            raise ValueError(f"Server {server_name} not found")
        
        connection = self.connections[server_name]
        if not connection.is_connected:
            raise ValueError(f"Server {server_name} is not connected")
        
        try:
            # Create tool call request
            request = CallToolRequest(
                name=tool_name,
                arguments=arguments
            )
            
            # Call the tool
            result = await connection.session.call_tool(request)
            
            # Process result
            if hasattr(result, 'content'):
                return {
                    'success': True,
                    'content': [self._process_content(content) for content in result.content],
                    'is_error': getattr(result, 'isError', False)
                }
            else:
                return {
                    'success': True,
                    'result': str(result),
                    'is_error': False
                }
                
        except Exception as e:
            logger.error(f"Tool call failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'is_error': True
            }
    
    def _process_content(self, content) -> Dict[str, Any]:
        """Process content from MCP response"""
        if isinstance(content, TextContent):
            return {
                'type': 'text',
                'text': content.text
            }
        elif isinstance(content, ImageContent):
            return {
                'type': 'image',
                'data': content.data,
                'mimeType': content.mimeType
            }
        elif isinstance(content, EmbeddedResource):
            return {
                'type': 'resource',
                'resource': asdict(content)
            }
        else:
            return {
                'type': 'unknown',
                'data': str(content)
            }
    
    def get_session(self, session_id: str) -> SessionData:
        """Get or create a session"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionData(
                session_id=session_id,
                conversation_history=[],
                created_at=datetime.now(),
                last_activity=datetime.now()
            )
        else:
            self.sessions[session_id].last_activity = datetime.now()
        
        return self.sessions[session_id]
    
    def add_to_conversation(self, session_id: str, message: Dict[str, Any]):
        """Add message to conversation history"""
        session = self.get_session(session_id)
        session.conversation_history.append({
            **message,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_event(self, session_id: str, event: Dict[str, Any]):
        """Add event to session queue for SSE"""
        if session_id not in self.event_queues:
            self.event_queues[session_id] = []
        
        self.event_queues[session_id].append({
            **event,
            'timestamp': datetime.now().isoformat(),
            'id': str(uuid.uuid4())
        })
    
    def get_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get and clear events for session"""
        events = self.event_queues.get(session_id, [])
        self.event_queues[session_id] = []
        return events
    
    async def process_query(self, session_id: str, query: str, llm_api_url: str, llm_headers: Dict[str, str]) -> Dict[str, Any]:
        """Process a query using available tools and LLM"""
        
        # Add user query to conversation
        self.add_to_conversation(session_id, {
            'role': 'user',
            'content': query
        })
        
        # Send event that we're processing
        self.add_event(session_id, {
            'type': 'processing',
            'message': 'Processing your query...'
        })
        
        # Get available tools from all servers
        available_tools = []
        for server_name, connection in self.connections.items():
            if connection.is_connected:
                for tool in connection.tools:
                    available_tools.append({
                        'server': server_name,
                        'name': tool.name,
                        'description': tool.description,
                        'inputSchema': tool.inputSchema
                    })
        
        # Get conversation history
        session = self.get_session(session_id)
        conversation_history = session.conversation_history[-10:]  # Last 10 messages
        
        # Prepare LLM request with tools
        llm_request = {
            'model': 'gpt-4',  # Adjust based on your LLM
            'messages': [
                {
                    'role': 'system',
                    'content': f"""You are an AI assistant with access to MCP tools. 
                    Available tools: {json.dumps(available_tools, indent=2)}
                    
                    When you need to use a tool, respond with a JSON object in this format:
                    {{
                        "action": "tool_call",
                        "server": "server_name",
                        "tool": "tool_name",
                        "arguments": {{...}}
                    }}
                    
                    Otherwise, respond normally to answer the user's query."""
                }
            ] + [
                {'role': msg['role'], 'content': msg['content']} 
                for msg in conversation_history
            ],
            'temperature': 0.7,
            'max_tokens': 1000
        }
        
        try:
            # Call LLM
            self.add_event(session_id, {
                'type': 'llm_call',
                'message': 'Calling LLM to analyze query...'
            })
            
            llm_response = requests.post(
                llm_api_url,
                headers=llm_headers,
                json=llm_request,
                timeout=30
            )
            
            if llm_response.status_code != 200:
                raise Exception(f"LLM API error: {llm_response.status_code}")
            
            llm_result = llm_response.json()
            assistant_message = llm_result['choices'][0]['message']['content']
            
            # Check if LLM wants to call a tool
            try:
                tool_call = json.loads(assistant_message)
                if tool_call.get('action') == 'tool_call':
                    # Execute tool call
                    self.add_event(session_id, {
                        'type': 'tool_call',
                        'message': f'Calling tool: {tool_call["tool"]} on server: {tool_call["server"]}'
                    })
                    
                    tool_result = await self.call_tool(
                        tool_call['server'],
                        tool_call['tool'],
                        tool_call['arguments']
                    )
                    
                    self.add_event(session_id, {
                        'type': 'tool_result',
                        'message': 'Tool execution completed'
                    })
                    
                    # Add tool result to conversation and get final response
                    tool_context = f"Tool call result: {json.dumps(tool_result, indent=2)}"
                    
                    # Get final response from LLM
                    final_request = {
                        'model': 'gpt-4',
                        'messages': llm_request['messages'] + [
                            {'role': 'assistant', 'content': f'I need to call tool: {tool_call["tool"]}'},
                            {'role': 'system', 'content': tool_context},
                            {'role': 'user', 'content': 'Based on this tool result, please provide a comprehensive answer to my original query.'}
                        ],
                        'temperature': 0.7,
                        'max_tokens': 1000
                    }
                    
                    final_response = requests.post(
                        llm_api_url,
                        headers=llm_headers,
                        json=final_request,
                        timeout=30
                    )
                    
                    if final_response.status_code == 200:
                        final_result = final_response.json()
                        assistant_message = final_result['choices'][0]['message']['content']
                    
                    # Add tool call info to response
                    response_data = {
                        'response': assistant_message,
                        'tool_used': {
                            'server': tool_call['server'],
                            'tool': tool_call['tool'],
                            'arguments': tool_call['arguments'],
                            'result': tool_result
                        }
                    }
                else:
                    response_data = {'response': assistant_message}
            except json.JSONDecodeError:
                # Normal text response
                response_data = {'response': assistant_message}
            
            # Add assistant response to conversation
            self.add_to_conversation(session_id, {
                'role': 'assistant',
                'content': assistant_message
            })
            
            self.add_event(session_id, {
                'type': 'response_ready',
                'message': 'Response generated successfully'
            })
            
            return {
                'success': True,
                'session_id': session_id,
                **response_data
            }
            
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            logger.error(error_msg)
            
            self.add_event(session_id, {
                'type': 'error',
                'message': error_msg
            })
            
            return {
                'success': False,
                'error': error_msg,
                'session_id': session_id
            }

# Initialize MCP client manager
mcp_manager = MCPClientManager()

# Create Flask app
app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'servers': {
            name: conn.is_connected 
            for name, conn in mcp_manager.connections.items()
        }
    })

@app.route('/servers', methods=['POST'])
def add_server():
    """Add a new MCP server"""
    try:
        data = request.json
        config = ServerConfig(
            name=data['name'],
            command=data['command'],
            args=data.get('args', []),
            env=data.get('env')
        )
        
        # Run in executor to avoid blocking
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(mcp_manager.add_server(config))
        loop.close()
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Server {config.name} added successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to connect to server {config.name}'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/servers', methods=['GET'])
def list_servers():
    """List all connected servers and their capabilities"""
    servers = {}
    for name, conn in mcp_manager.connections.items():
        servers[name] = {
            'is_connected': conn.is_connected,
            'tools': [
                {
                    'name': tool.name,
                    'description': tool.description,
                    'inputSchema': tool.inputSchema
                }
                for tool in conn.tools
            ],
            'resources': len(conn.resources),
            'prompts': len(conn.prompts)
        }
    
    return jsonify({'servers': servers})

@app.route('/query', methods=['POST'])
def process_query():
    """Process a query using MCP tools and LLM"""
    try:
        data = request.json
        query = data.get('query', '')
        session_id = data.get('session_id', str(uuid.uuid4()))
        llm_api_url = data.get('llm_api_url', 'https://api.openai.com/v1/chat/completions')
        llm_headers = data.get('llm_headers', {})
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query is required'
            }), 400
        
        # Process query asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            mcp_manager.process_query(session_id, query, llm_api_url, llm_headers)
        )
        loop.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/events/<session_id>')
def stream_events(session_id):
    """Server-Sent Events endpoint for real-time updates"""
    def event_stream():
        while True:
            events = mcp_manager.get_events(session_id)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            time.sleep(0.5)  # Poll every 500ms
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )

@app.route('/sessions/<session_id>/history', methods=['GET'])
def get_conversation_history(session_id):
    """Get conversation history for a session"""
    session = mcp_manager.get_session(session_id)
    return jsonify({
        'session_id': session_id,
        'history': session.conversation_history,
        'created_at': session.created_at.isoformat(),
        'last_activity': session.last_activity.isoformat()
    })

@app.route('/sessions', methods=['GET'])
def list_sessions():
    """List all active sessions"""
    sessions = {}
    for session_id, session in mcp_manager.sessions.items():
        sessions[session_id] = {
            'created_at': session.created_at.isoformat(),
            'last_activity': session.last_activity.isoformat(),
            'message_count': len(session.conversation_history)
        }
    
    return jsonify({'sessions': sessions})

@app.route('/tools/call', methods=['POST'])
def call_tool_direct():
    """Direct tool call endpoint"""
    try:
        data = request.json
        server_name = data.get('server')
        tool_name = data.get('tool')
        arguments = data.get('arguments', {})
        
        if not server_name or not tool_name:
            return jsonify({
                'success': False,
                'error': 'Server and tool name are required'
            }), 400
        
        # Call tool
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            mcp_manager.call_tool(server_name, tool_name, arguments)
        )
        loop.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

if __name__ == '__main__':
    # Example server configurations
    example_servers = [
        {
            'name': 'filesystem',
            'command': 'mcp-server-filesystem',
            'args': ['--root', '/tmp']
        },
        {
            'name': 'git',
            'command': 'mcp-server-git',
            'args': []
        }
    ]
    
    print("MCP Client Flask API starting...")
    print("Available endpoints:")
    print("  POST /servers - Add MCP server")
    print("  GET /servers - List servers")
    print("  POST /query - Process query with tools")
    print("  GET /events/<session_id> - SSE stream")
    print("  GET /sessions/<session_id>/history - Get conversation history")
    print("  POST /tools/call - Direct tool call")
    print("  GET /health - Health check")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
