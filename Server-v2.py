import asyncio
from mcp.library import LibraryServer
from mcp.types import Tool, JsonSchema, CallToolRequest, CallToolResult, TextContent

# Define a basic "echo" tool that just returns the input text
class EchoTool(Tool):
    name = "echo"
    description = "Echoes the input text"
    inputSchema = JsonSchema(type="object", properties={
        "message": {"type": "string", "description": "Message to echo"}
    }, required=["message"])

    async def call(self, request: CallToolRequest) -> CallToolResult:
        message = request.arguments.get("message", "")
        return CallToolResult(content=[
            TextContent(text=f"Echo: {message}")
        ])

# Define another tool - square a number
class SquareTool(Tool):
    name = "square"
    description = "Squares an integer"
    inputSchema = JsonSchema(type="object", properties={
        "number": {"type": "integer", "description": "Number to square"}
    }, required=["number"])

    async def call(self, request: CallToolRequest) -> CallToolResult:
        number = request.arguments.get("number", 0)
        return CallToolResult(content=[
            TextContent(text=f"Result: {number * number}")
        ])

async def main():
    server = LibraryServer(tools=[EchoTool(), SquareTool()])
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
