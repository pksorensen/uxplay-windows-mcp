"""
UxPlay MCP Server - User Guide

The UxPlay application now includes a built-in MCP (Model Context Protocol) server
that allows AI assistants and other MCP clients to control UxPlay and capture
screenshots from the AirPlay stream.

## Quick Start

1. **Install UxPlay**
   - Download and install from the releases page
   - No need to clone the repository or install Python packages
   - Everything is included in the application

2. **Start the MCP Server**
   - Right-click the UxPlay tray icon
   - Select "Start MCP Server"
   - The server will start on http://127.0.0.1:8000 by default

3. **Configure Your MCP Client**
   - Right-click the UxPlay tray icon
   - Select "MCP Settings"
   - Click "Copy to Clipboard" to copy the configuration
   - Paste into your MCP client configuration file

## MCP Settings Dialog

The settings dialog allows you to:

- **Change Host**: Default is 127.0.0.1 (localhost)
  - Use 0.0.0.0 to allow network access
  - Use specific IP for network binding

- **Change Port**: Default is 8000
  - Any port between 1-65535
  - Make sure the port is not in use

- **Copy Configuration**: One-click copy of the JSON configuration

## For Claude Desktop Users

Configuration file location:
- Windows: %APPDATA%\Claude\claude_desktop_config.json
- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json

Example configuration (shown in MCP Settings dialog):
```json
{
  "mcpServers": {
    "uxplay": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

Steps:
1. Open MCP Settings from UxPlay tray icon
2. Click "Copy to Clipboard"
3. Open Claude Desktop configuration file
4. Paste the configuration
5. Restart Claude Desktop

## Available Tools

Once connected, your MCP client can use these tools:

- **get_screenshot**: Capture a screenshot from the AirPlay video stream
  - Works even when UxPlay window is in background
  - Returns PNG image in base64 format
  - Requires an active AirPlay connection

- **start_uxplay**: Start the UxPlay AirPlay server
  - Allows devices to connect and mirror screens

- **stop_uxplay**: Stop the UxPlay AirPlay server
  - Disconnects any connected devices

- **get_uxplay_status**: Check if UxPlay is running
  - Returns current status and PID if running

## Example Usage in Claude

After configuration, you can ask Claude:
- "Can you start the UxPlay server?"
- "Take a screenshot of the AirPlay stream"
- "Is UxPlay running right now?"
- "Stop the AirPlay server"

## Network Access

To allow MCP clients on other computers to connect:

1. Open MCP Settings
2. Change Host to: 0.0.0.0
3. Note your computer's IP address (e.g., 192.168.1.100)
4. Update the URL in your MCP client:
   ```json
   {
     "mcpServers": {
       "uxplay": {
         "url": "http://192.168.1.100:8000/sse"
       }
     }
   }
   ```
5. Make sure Windows Firewall allows the connection

## Troubleshooting

**MCP Server won't start:**
- Check if the port is already in use
- Try changing the port in MCP Settings
- Check the log file: %APPDATA%\uxplay-windows\uxplay-windows.log

**MCP Client can't connect:**
- Verify the MCP Server is running (check tray menu)
- Verify the URL in your client configuration matches the MCP Settings
- Check Windows Firewall settings
- Try restarting both UxPlay and your MCP client

**Screenshot returns error:**
- Make sure UxPlay is running
- Make sure a device is connected and streaming
- Check if the UxPlay window is visible (even if minimized)

## Advanced Configuration

**Custom Port:**
If port 8000 is in use, change it in MCP Settings to any available port.

**Remote Access:**
For remote access, use host 0.0.0.0 and configure your router to forward
the port to your computer. Update firewall rules accordingly.

**Security Note:**
The MCP server has no authentication. Only expose it to trusted networks.
For localhost use (127.0.0.1), only applications on your computer can access it.
"""
