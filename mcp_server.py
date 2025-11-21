#!/usr/bin/env python3
"""
UxPlay MCP Server

This MCP server provides tools to control UxPlay and capture screenshots
of the mirrored screen from iOS/macOS devices.
"""

import os
import sys
import io
import base64
import asyncio
import logging
from pathlib import Path
from typing import Optional

from PIL import ImageGrab
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

# Import the existing tray.py components
from tray import Paths, ArgumentManager, ServerManager, APPDATA_DIR

# ─── Logging Setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(APPDATA_DIR / "mcp_server.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)

# ─── MCP Server Implementation ────────────────────────────────────────────────

class UxPlayMCPServer:
    def __init__(self):
        self.paths = Paths()
        self.arg_mgr = ArgumentManager(self.paths.arguments_file)
        self.server_mgr = ServerManager(self.paths.uxplay_exe, self.arg_mgr)
        self.server = Server("uxplay-mcp-server")
        
        # Register tool handlers
        self._register_handlers()
        
    def _register_handlers(self):
        """Register all MCP tool handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="get_screenshot",
                    description="Capture a screenshot of the current mirrored screen from the iOS/macOS device",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="start_uxplay",
                    description="Start the UxPlay AirPlay server to begin receiving screen mirroring",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="stop_uxplay",
                    description="Stop the UxPlay AirPlay server",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="get_uxplay_status",
                    description="Get the current status of the UxPlay server (running or stopped)",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool calls"""
            
            if name == "get_screenshot":
                return await self._handle_screenshot()
            elif name == "start_uxplay":
                return await self._handle_start_uxplay()
            elif name == "stop_uxplay":
                return await self._handle_stop_uxplay()
            elif name == "get_uxplay_status":
                return await self._handle_get_status()
            else:
                raise ValueError(f"Unknown tool: {name}")
    
    async def _handle_screenshot(self) -> list[TextContent | ImageContent]:
        """Capture and return a screenshot"""
        try:
            # Capture the screen
            screenshot = ImageGrab.grab()
            
            # Convert to PNG bytes
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format='PNG')
            img_bytes = img_buffer.getvalue()
            
            # Encode to base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            return [
                ImageContent(
                    type="image",
                    data=img_base64,
                    mimeType="image/png"
                ),
                TextContent(
                    type="text",
                    text=f"Screenshot captured successfully. Size: {screenshot.size[0]}x{screenshot.size[1]} pixels"
                )
            ]
        except Exception as e:
            logging.exception("Failed to capture screenshot")
            return [
                TextContent(
                    type="text",
                    text=f"Error capturing screenshot: {str(e)}"
                )
            ]
    
    async def _handle_start_uxplay(self) -> list[TextContent]:
        """Start UxPlay server"""
        try:
            self.server_mgr.start()
            
            # Give it a moment to start
            await asyncio.sleep(1)
            
            # Check if it's running
            if self.server_mgr.process and self.server_mgr.process.poll() is None:
                return [
                    TextContent(
                        type="text",
                        text=f"UxPlay server started successfully (PID: {self.server_mgr.process.pid})"
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text="UxPlay server start command was sent, but status could not be confirmed"
                    )
                ]
        except Exception as e:
            logging.exception("Failed to start UxPlay")
            return [
                TextContent(
                    type="text",
                    text=f"Error starting UxPlay: {str(e)}"
                )
            ]
    
    async def _handle_stop_uxplay(self) -> list[TextContent]:
        """Stop UxPlay server"""
        try:
            self.server_mgr.stop()
            return [
                TextContent(
                    type="text",
                    text="UxPlay server stopped successfully"
                )
            ]
        except Exception as e:
            logging.exception("Failed to stop UxPlay")
            return [
                TextContent(
                    type="text",
                    text=f"Error stopping UxPlay: {str(e)}"
                )
            ]
    
    async def _handle_get_status(self) -> list[TextContent]:
        """Get UxPlay server status"""
        try:
            is_running = self.server_mgr.process and self.server_mgr.process.poll() is None
            
            if is_running:
                status = f"Running (PID: {self.server_mgr.process.pid})"
            else:
                status = "Stopped"
            
            return [
                TextContent(
                    type="text",
                    text=f"UxPlay server status: {status}"
                )
            ]
        except Exception as e:
            logging.exception("Failed to get UxPlay status")
            return [
                TextContent(
                    type="text",
                    text=f"Error getting UxPlay status: {str(e)}"
                )
            ]
    
    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

# ─── Main Entry Point ─────────────────────────────────────────────────────────

async def main():
    """Main entry point"""
    logging.info("Starting UxPlay MCP Server")
    
    # Ensure AppData directory exists
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create and run the server
    server = UxPlayMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
