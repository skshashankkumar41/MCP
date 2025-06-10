#!/usr/bin/env python3
"""
Simple Dummy MCP Server for Testing
This server provides basic tools for testing the MCP client functionality.
"""

import asyncio
import json
import sys
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import random
import os

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool, 
    TextContent, 
    CallToolRequest, 
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    GetPromptRequest,
    GetPromptResult,
    ListPromptsRequest,
    ListPromptsResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    UserMessage
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DummyMCPServer:
    """A simple dummy MCP server with basic tools for testing"""
    
    def __init__(self):
        self.server = Server("dummy-server")
        self.data_store = {}  # Simple in-memory data store
        self.counter = 0
        self.setup_tools()
        self.setup_prompts()
    
    def setup_tools(self):
        """Setup available tools"""
        
        @self.server.call_tool()
        async def calculator(operation: str, a: float, b: float) -> List[TextContent]:
            """
            Perform basic mathematical operations
            
            Args:
                operation: The operation to perform (add, subtract, multiply, divide)
                a: First number
                b: Second number
            """
            try:
                if operation == "add":
                    result = a + b
                elif operation == "subtract":
                    result = a - b
                elif operation == "multiply":
                    result = a * b
                elif operation == "divide":
                    if b == 0:
                        return [TextContent(
                            type="text",
                            text="Error: Division by zero is not allowed"
                        )]
                    result = a / b
                else:
                    return [TextContent(
                        type="text",
                        text=f"Error: Unknown operation '{operation}'. Supported: add, subtract, multiply, divide"
                    )]
                
                return [TextContent(
                    type="text",
                    text=f"Result: {a} {operation} {b} = {result}"
                )]
                
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"Error performing calculation: {str(e)}"
                )]
        
        @self.server.call_tool()
        async def get_current_time() -> List[TextContent]:
            """Get the current date and time"""
            current_time = datetime.now()
            return [TextContent(
                type="text",
                text=f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )]
        
        @self.server.call_tool()
        async def store_data(key: str, value: str) -> List[TextContent]:
            """
            Store data in the server's memory
            
            Args:
                key: The key to store the data under
                value: The value to store
            """
            self.data_store[key] = {
                'value': value,
                'timestamp': datetime.now().isoformat(),
                'access_count': 0
            }
            
            return [TextContent(
                type="text",
                text=f"Successfully stored data with key '{key}'"
            )]
        
        @self.server.call_tool()
        async def retrieve_data(key: str) -> List[TextContent]:
            """
            Retrieve data from the server's memory
            
            Args:
                key: The key to retrieve data for
            """
            if key in self.data_store:
                data = self.data_store[key]
                data['access_count'] += 1
                
                return [TextContent(
                    type="text",
                    text=f"Key: {key}\nValue: {data['value']}\nStored: {data['timestamp']}\nAccessed: {data['access_count']} times"
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"No data found for key '{key}'"
                )]
        
        @self.server.call_tool()
        async def list_stored_keys() -> List[TextContent]:
            """List all keys in the data store"""
            if not self.data_store:
                return [TextContent(
                    type="text",
                    text="No data stored yet"
                )]
            
            keys_info = []
            for key, data in self.data_store.items():
                keys_info.append(f"- {key} (stored: {data['timestamp']}, accessed: {data['access_count']} times)")
            
            return [TextContent(
                type="text",
                text="Stored keys:\n" + "\n".join(keys_info)
            )]
        
        @self.server.call_tool()
        async def generate_random_number(min_val: int = 1, max_val: int = 100) -> List[TextContent]:
            """
            Generate a random number within a range
            
            Args:
                min_val: Minimum value (default: 1)
                max_val: Maximum value (default: 100)
            """
            if min_val >= max_val:
                return [TextContent(
                    type="text",
                    text="Error: min_val must be less than max_val"
                )]
            
            random_num = random.randint(min_val, max_val)
            return [TextContent(
                type="text",
                text=f"Random number between {min_val} and {max_val}: {random_num}"
            )]
        
        @self.server.call_tool()
        async def count_words(text: str) -> List[TextContent]:
            """
            Count words and characters in text
            
            Args:
                text: The text to analyze
            """
            word_count = len(text.split())
            char_count = len(text)
            char_count_no_spaces = len(text.replace(' ', ''))
            
            return [TextContent(
                type="text",
                text=f"Text analysis:\n- Words: {word_count}\n- Characters (with spaces): {char_count}\n- Characters (without spaces): {char_count_no_spaces}"
            )]
        
        @self.server.call_tool()
        async def echo_message(message: str, repeat: int = 1) -> List[TextContent]:
            """
            Echo a message with optional repetition
            
            Args:
                message: The message to echo
                repeat: Number of times to repeat (default: 1)
            """
            if repeat < 1 or repeat > 10:
                return [TextContent(
                    type="text",
                    text="Error: repeat must be between 1 and 10"
                )]
            
            result = []
            for i in range(repeat):
                result.append(f"{i+1}. {message}")
            
            return [TextContent(
                type="text",
                text="\n".join(result)
            )]
        
        @self.server.call_tool()
        async def system_info() -> List[TextContent]:
            """Get basic system information"""
            info = {
                "server_name": "Dummy MCP Server",
                "version": "1.0.0",
                "uptime": datetime.now().isoformat(),
                "tools_available": 8,
                "data_store_items": len(self.data_store),
                "python_version": sys.version.split()[0],
                "platform": sys.platform
            }
            
            info_text = "System Information:\n"
            for key, value in info.items():
                info_text += f"- {key.replace('_', ' ').title()}: {value}\n"
            
            return [TextContent(
                type="text",
                text=info_text.strip()
            )]
    
    def setup_prompts(self):
        """Setup available prompts"""
        
        @self.server.get_prompt()
        async def greeting_prompt(name: str = "User") -> GetPromptResult:
            """Generate a personalized greeting"""
            return GetPromptResult(
                description=f"A personalized greeting for {name}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Hello {name}! Welcome to the Dummy MCP Server. How can I help you today?"
                        )
                    )
                ]
            )
        
        @self.server.get_prompt()
        async def help_prompt() -> GetPromptResult:
            """Get help information"""
            help_text = """
Available Tools:
1. calculator - Perform basic math operations
2. get_current_time - Get current date and time
3. store_data - Store key-value data
4. retrieve_data - Retrieve stored data
5. list_stored_keys - List all stored keys
6. generate_random_number - Generate random numbers
7. count_words - Analyze text
8. echo_message - Echo messages with repetition
9. system_info - Get server information

Example queries:
- "What's 15 + 27?"
- "Store my name as John"
- "What time is it?"
- "Generate a random number between 1 and 50"
- "Count words in 'Hello world'"
            """
            
            return GetPromptResult(
                description="Help information for using the dummy server",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=help_text.strip()
                        )
                    )
                ]
            )

async def main():
    """Main server function"""
    server_instance = DummyMCPServer()
    
    # Create and run the stdio server
    async with stdio_server() as (read_stream, write_stream):
        await server_instance.server.run(
            read_stream,
            write_stream,
            server_instance.server.create_initialization_options()
        )

if __name__ == "__main__":
    logger.info("Starting Dummy MCP Server...")
    asyncio.run(main())




