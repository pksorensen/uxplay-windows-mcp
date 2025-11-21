"""
Example MCP Client Configuration

This file demonstrates how to configure an MCP client (like Claude Desktop) 
to use the UxPlay MCP Server.

For Claude Desktop, add this to your configuration file:
- Windows: %APPDATA%\Claude\claude_desktop_config.json
- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json

Example configuration:
{
  "mcpServers": {
    "uxplay": {
      "command": "python",
      "args": ["C:\\path\\to\\uxplay-windows-mcp\\mcp_server.py"]
    }
  }
}

Or if you have Python installed in a virtual environment:
{
  "mcpServers": {
    "uxplay": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\uxplay-windows-mcp\\mcp_server.py"]
    }
  }
}

After configuration:
1. Restart Claude Desktop
2. You should see the "uxplay" MCP server available in the tools menu
3. Available tools:
   - get_screenshot: Capture the desktop (including mirrored AirPlay content)
   - start_uxplay: Start the AirPlay server
   - stop_uxplay: Stop the AirPlay server
   - get_uxplay_status: Check if UxPlay is running

Example usage in Claude:
- "Can you start the UxPlay server for me?"
- "Take a screenshot of my current screen"
- "Is UxPlay running?"
- "Stop the AirPlay server"
"""
