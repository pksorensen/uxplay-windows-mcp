"""
Example MCP Client Configuration

This file demonstrates how to configure an MCP client (like Claude Desktop) 
to use the UxPlay MCP Server.

The UxPlay MCP Server now runs as an HTTP server, making it more accessible
and easier to integrate with various MCP clients.

For Claude Desktop, add this to your configuration file:
- Windows: %APPDATA%\Claude\claude_desktop_config.json
- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json

Example configuration (HTTP/SSE based):
{
  "mcpServers": {
    "uxplay": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}

If you want to run the server on a different host/port:
1. Set environment variables before starting the server:
   - Windows:
     set MCP_HOST=0.0.0.0
     set MCP_PORT=8080
     python mcp_server.py
   
   - Linux/macOS:
     MCP_HOST=0.0.0.0 MCP_PORT=8080 python mcp_server.py

2. Update your MCP client configuration:
{
  "mcpServers": {
    "uxplay": {
      "url": "http://localhost:8080/sse"
    }
  }
}

Starting the Server:
1. Open a command prompt/terminal
2. Navigate to the uxplay-windows-mcp directory
3. Run: python mcp_server.py
4. The server will start and log its URL (default: http://127.0.0.1:8000)

After configuration:
1. Restart Claude Desktop (or your MCP client)
2. You should see the "uxplay" MCP server available in the tools menu
3. Available tools:
   - get_screenshot: Capture from the actual AirPlay video stream
   - start_uxplay: Start the AirPlay server
   - stop_uxplay: Stop the AirPlay server
   - get_uxplay_status: Check if UxPlay is running

Example usage in Claude:
- "Can you start the UxPlay server for me?"
- "Take a screenshot of the AirPlay stream"
- "Is UxPlay running?"
- "Stop the AirPlay server"

Key Differences from Previous Version:
- Now uses HTTP/SSE transport instead of stdio
- Captures from the actual AirPlay video stream (not desktop)
- Works even when UxPlay window is in the background
- Can be accessed over the network if configured with MCP_HOST=0.0.0.0
"""
