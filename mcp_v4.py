@dataclass
class ServerConfig:
    name: str
    transport_type: str  # 'stdio' or 'sse'
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None

@dataclass
class MCPConnection:
    name: str
    config: ServerConfig  # Store config instead of session
    tools: List[Tool]
    resources: List[Any]
    prompts: List[Any]
    is_connected: bool = False
    last_checked: datetime = None

async def add_server(self, config: ServerConfig) -> bool:
    """Add MCP server configuration and test connection"""
    try:
        # Test connection and get capabilities
        tools, resources, prompts = await self._test_connection_and_get_capabilities(config)
        
        # Store config and capabilities
        self.connections[config.name] = MCPConnection(
            name=config.name,
            config=config,
            tools=tools,
            resources=resources,
            prompts=prompts,
            is_connected=True,
            last_checked=datetime.now()
        )
        
        logger.info(f"Successfully added MCP server: {config.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add MCP server {config.name}: {str(e)}")
        return False

async def _test_connection_and_get_capabilities(self, config: ServerConfig):
    """Test connection and retrieve server capabilities"""
    async with self._create_session(config) as session:
        return await self._get_server_capabilities(session)

async def _create_session(self, config: ServerConfig):
    """Create a session based on transport type"""
    if config.transport_type.lower() == 'stdio':
        return self._create_stdio_session(config)
    elif config.transport_type.lower() == 'sse':
        return self._create_sse_session(config)
    else:
        raise ValueError(f"Unsupported transport type: {config.transport_type}")

@asynccontextmanager
async def _create_stdio_session(self, config: ServerConfig):
    """Create stdio session using the reference implementation"""
    from your_mcp_module import _create_stdio_session  # Import from your second file
    
    async with _create_stdio_session(
        command=config.command,
        args=config.args or [],
        env=config.env or {},
    ) as session:
        yield session

@asynccontextmanager
async def _create_sse_session(self, config: ServerConfig):
    """Create SSE session using the reference implementation"""
    from your_mcp_module import _create_sse_session  # Import from your second file
    
    async with _create_sse_session(
        url=config.url,
        headers=config.headers or {},
        timeout=config.timeout or 30.0,
    ) as session:
        yield session


async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool by creating a fresh session"""
    if server_name not in self.connections:
        raise ValueError(f"Server {server_name} not found")
    
    connection = self.connections[server_name]
    if not connection.is_connected:
        raise ValueError(f"Server {server_name} is not connected")
    
    try:
        # Create fresh session for this tool call
        async with self._create_session(connection.config) as session:
            request = CallToolRequest(
                name=tool_name,
                arguments=arguments
            )
            
            result = await session.call_tool(request)
            
            # Process result (keep existing logic)
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



@app.route('/servers', methods=['POST'])
def add_server():
    """Add a new MCP server"""
    try:
        data = request.json
        config = ServerConfig(
            name=data['name'],
            transport_type=data.get('transport_type', 'stdio'),
            command=data.get('command'),
            args=data.get('args', []),
            env=data.get('env'),
            url=data.get('url'),
            headers=data.get('headers'),
            timeout=data.get('timeout')
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



@dataclass
class ServerConfig:
    name: str
    transport_type: str  # 'stdio', 'sse', or 'streamable_http'
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None
    sse_read_timeout: Optional[float] = None
    terminate_on_close: Optional[bool] = True



pythonasync def _create_session(self, config: ServerConfig):
    """Create a session based on transport type"""
    if config.transport_type.lower() == 'stdio':
        return self._create_stdio_session(config)
    elif config.transport_type.lower() == 'sse':
        return self._create_sse_session(config)
    elif config.transport_type.lower() == 'streamable_http':
        return self._create_streamable_http_session(config)
    else:
        raise ValueError(f"Unsupported transport type: {config.transport_type}")



@asynccontextmanager
async def _create_streamable_http_session(self, config: ServerConfig):
    """Create Streamable HTTP session using the reference implementation"""
    from your_mcp_module import _create_streamable_http_session  # Import from your second file
    from datetime import timedelta
    
    # Convert float timeout to timedelta if needed
    timeout = timedelta(seconds=config.timeout) if config.timeout else timedelta(seconds=30.0)
    sse_read_timeout = timedelta(seconds=config.sse_read_timeout) if config.sse_read_timeout else timedelta(seconds=30.0)
    
    async with _create_streamable_http_session(
        url=config.url,
        headers=config.headers or {},
        timeout=timeout,
        sse_read_timeout=sse_read_timeout,
        terminate_on_close=config.terminate_on_close if config.terminate_on_close is not None else True,
    ) as session:
        yield session



@app.route('/servers', methods=['POST'])
def add_server():
    """Add a new MCP server"""
    try:
        data = request.json
        config = ServerConfig(
            name=data['name'],
            transport_type=data.get('transport_type', 'stdio'),
            command=data.get('command'),
            args=data.get('args', []),
            env=data.get('env'),
            url=data.get('url'),
            headers=data.get('headers'),
            timeout=data.get('timeout'),
            sse_read_timeout=data.get('sse_read_timeout'),
            terminate_on_close=data.get('terminate_on_close', True)
        )
        
        # Validate required fields based on transport type
        if config.transport_type.lower() == 'stdio':
            if not config.command:
                raise ValueError("Command is required for stdio transport")
        elif config.transport_type.lower() in ['sse', 'streamable_http']:
            if not config.url:
                raise ValueError(f"URL is required for {config.transport_type} transport")
        
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



if __name__ == '__main__':
    # Example server configurations
    example_servers = [
        {
            'name': 'filesystem',
            'transport_type': 'stdio',
            'command': 'mcp-server-filesystem',
            'args': ['--root', '/tmp']
        },
        {
            'name': 'git',
            'transport_type': 'stdio',
            'command': 'mcp-server-git',
            'args': []
        },
        {
            'name': 'web-service',
            'transport_type': 'sse',
            'url': 'https://api.example.com/mcp/sse',
            'headers': {'Authorization': 'Bearer token'},
            'timeout': 30.0
        },
        {
            'name': 'streamable-service',
            'transport_type': 'streamable_http',
            'url': 'https://api.example.com/mcp/stream',
            'headers': {'Authorization': 'Bearer token'},
            'timeout': 30.0,
            'sse_read_timeout': 60.0,
            'terminate_on_close': True
        }
    ]
    
    print("MCP Client Flask API starting...")
    print("Supported transport types: stdio, sse, streamable_http")
    # ... rest of the startup code
