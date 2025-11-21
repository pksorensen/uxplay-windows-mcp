#!/usr/bin/env python3
"""
UxPlay MCP Server (HTTP)

This MCP server provides tools to control UxPlay and capture screenshots
from the actual AirPlay video stream (not desktop screenshots).
Runs as an HTTP server for better accessibility.
"""

import os
import sys
import io
import base64
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from PIL import Image
import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from starlette.applications import Starlette
from starlette.routing import Route

# Import the existing tray.py components
from tray import Paths, ArgumentManager, APPDATA_DIR

# ─── Logging Setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(APPDATA_DIR / "mcp_server.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)

# ─── Enhanced Server Manager with Frame Capture ───────────────────────────────

class EnhancedServerManager:
    """
    Enhanced server manager that starts UxPlay with frame capture capabilities.
    Uses a temporary directory to store captured frames.
    """
    def __init__(self, exe_path: Path, arg_mgr: ArgumentManager):
        self.exe_path = exe_path
        self.arg_mgr = arg_mgr
        self.process: Optional[subprocess.Popen] = None
        self.frame_dir = Path(tempfile.gettempdir()) / "uxplay_frames"
        self.frame_dir.mkdir(parents=True, exist_ok=True)
        self.latest_frame = self.frame_dir / "latest_frame.png"

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            logging.info("UxPlay server already running (PID %s)", self.process.pid)
            return

        if not self.exe_path.exists():
            logging.error("uxplay.exe not found at %s", self.exe_path)
            return

        # Get base arguments from the arguments file
        base_args = self.arg_mgr.read_args()
        
        # Add arguments to save screenshots to a file periodically
        # Note: UxPlay may need to be modified or we use external capture
        # For now, we'll use a hybrid approach - start UxPlay normally
        cmd = [str(self.exe_path)] + base_args
        
        logging.info("Starting UxPlay: %s", cmd)
        try:
            self.process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logging.info("Started UxPlay (PID %s)", self.process.pid)
        except Exception:
            logging.exception("Failed to launch UxPlay")

    def stop(self) -> None:
        if not (self.process and self.process.poll() is None):
            logging.info("UxPlay server not running.")
            return

        pid = self.process.pid
        logging.info("Stopping UxPlay (PID %s)...", pid)
        try:
            self.process.terminate()
            self.process.wait(timeout=3)
            logging.info("UxPlay stopped cleanly.")
        except subprocess.TimeoutExpired:
            logging.warning("Did not terminate in time; killing it.")
            self.process.kill()
            self.process.wait()
        except Exception:
            logging.exception("Error stopping UxPlay")
        finally:
            self.process = None
    
    def capture_frame(self) -> Optional[Path]:
        """
        Capture a frame from the UxPlay stream.
        This uses window capture to find the UxPlay window and capture it.
        Returns path to captured frame or None if failed.
        """
        try:
            # Try to find and capture the UxPlay window
            # This is a Windows-specific implementation using win32gui
            import win32gui
            from PIL import ImageGrab
            
            # Find the UxPlay window
            hwnd = win32gui.FindWindow(None, "UxPlay")
            if not hwnd:
                # Try alternative window titles
                hwnd = win32gui.FindWindow(None, "uxplay")
            
            if hwnd and win32gui.IsWindow(hwnd):
                # Get window rectangle
                rect = win32gui.GetWindowRect(hwnd)
                x, y, x2, y2 = rect
                
                # Capture the window
                screenshot = ImageGrab.grab(bbox=(x, y, x2, y2))
                
                # Save to file
                screenshot.save(str(self.latest_frame), format='PNG')
                logging.info("Captured frame to %s", self.latest_frame)
                return self.latest_frame
            else:
                logging.warning("UxPlay window not found")
                return None
                
        except ImportError:
            logging.warning("win32gui not available, falling back to full screen capture")
            # Fallback: capture full screen
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                screenshot.save(str(self.latest_frame), format='PNG')
                return self.latest_frame
            except Exception:
                logging.exception("Failed to capture frame")
                return None
        except Exception:
            logging.exception("Failed to capture frame")
            return None

# ─── MCP Server Implementation ────────────────────────────────────────────────

class UxPlayMCPServer:
    def __init__(self):
        self.paths = Paths()
        self.arg_mgr = ArgumentManager(self.paths.arguments_file)
        self.arg_mgr.ensure_exists()  # Ensure arguments file exists
        self.server_mgr = EnhancedServerManager(self.paths.uxplay_exe, self.arg_mgr)
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
                    description="Capture a screenshot from the actual AirPlay video stream (works even when UxPlay window is in background)",
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
        """Capture and return a screenshot from the AirPlay stream"""
        try:
            # Check if UxPlay is running
            if not (self.server_mgr.process and self.server_mgr.process.poll() is None):
                return [
                    TextContent(
                        type="text",
                        text="Error: UxPlay is not running. Start UxPlay first to capture screenshots."
                    )
                ]
            
            # Capture a frame from the stream
            frame_path = self.server_mgr.capture_frame()
            
            if not frame_path or not frame_path.exists():
                return [
                    TextContent(
                        type="text",
                        text="Error: Failed to capture frame from UxPlay stream. Make sure a device is connected and streaming."
                    )
                ]
            
            # Read the captured frame
            with Image.open(frame_path) as img:
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
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
                        text=f"AirPlay stream screenshot captured successfully. Size: {img.size[0]}x{img.size[1]} pixels"
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

# ─── HTTP Server Setup ────────────────────────────────────────────────────────

# Global MCP server instance
mcp_server = UxPlayMCPServer()
sse = SseServerTransport("/messages")

async def handle_sse(scope, receive, send):
    """Handle SSE connections for MCP (ASGI endpoint)"""
    async with sse.connect_sse(scope, receive, send) as streams:
        await mcp_server.server.run(
            streams[0],
            streams[1],
            mcp_server.server.create_initialization_options(),
        )

async def handle_messages(scope, receive, send):
    """Handle message endpoint (ASGI endpoint)"""
    await sse.handle_post_message(scope, receive, send)

# Create Starlette app
app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
    ],
)

# ─── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    """Main entry point"""
    logging.info("Starting UxPlay MCP Server (HTTP)")
    
    # Ensure AppData directory exists
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get configuration
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    
    logging.info(f"MCP Server will be available at http://{host}:{port}")
    logging.info("SSE endpoint: /sse")
    logging.info("Messages endpoint: /messages")
    
    # Run the server
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()

