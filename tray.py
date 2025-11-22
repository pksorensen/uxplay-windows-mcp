from __future__ import annotations

import os
import sys
import logging
import shlex
import subprocess
import threading
import time
import winreg
import webbrowser
import json
import io
import base64
import tempfile
import asyncio
from pathlib import Path
from typing import List, Optional

import pystray
from PIL import Image

# MCP-related imports with error handling
MCP_AVAILABLE = False
try:
    import uvicorn
    from mcp.server import Server
    from mcp.server.sse import SseServerTransport
    from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
    from starlette.applications import Starlette
    from starlette.routing import Route
    MCP_AVAILABLE = True
except ImportError as e:
    logging.warning("MCP dependencies not available: %s. MCP server functionality will be disabled.", e)

# ─── Constants ────────────────────────────────────────────────────────────────

APP_NAME = "uxplay-windows"
APPDATA_DIR = Path(os.environ["APPDATA"]) / "uxplay-windows"
LOG_FILE = APPDATA_DIR / f"{APP_NAME}.log"

# ensure the AppData folder exists up front:
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── Logging Setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# ─── Path Discovery ───────────────────────────────────────────────────────────

class Paths:
    """
    Find where our bundled resources live:
      • if PyInstaller one-file: sys._MEIPASS
      • else if one-dir: same folder as the exe
      • else (running from .py): the script's folder
    Then, if there is an `_internal` subfolder, use that.
    """
    def __init__(self):
        if getattr(sys, "frozen", False):
            # one-file mode unpacks to _MEIPASS
            if hasattr(sys, "_MEIPASS"):
                cand = Path(sys._MEIPASS)
            else:
                # one-dir mode: resources sit beside the exe
                cand = Path(sys.executable).parent
        else:
            cand = Path(__file__).resolve().parent

        # if there's an _internal subfolder, that's where our .ico + bin live
        internal = cand / "_internal"
        self.resource_dir = internal if internal.is_dir() else cand

        # icon is directly in resource_dir
        self.icon_file = self.resource_dir / "icon.ico"

        # first look for bin/uxplay.exe, else uxplay.exe at top level
        ux1 = self.resource_dir / "bin" / "uxplay.exe"
        ux2 = self.resource_dir / "uxplay.exe"
        self.uxplay_exe = ux1 if ux1.exists() else ux2

        # AppData paths
        self.appdata_dir = APPDATA_DIR
        self.arguments_file = self.appdata_dir / "arguments.txt"

# ─── Argument File Manager ────────────────────────────────────────────────────

class ArgumentManager:
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def ensure_exists(self) -> None:
        logging.info("Ensuring arguments file at '%s'", self.file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("", encoding="utf-8")
            logging.info("Created empty arguments.txt")

    def read_args(self) -> List[str]:
        if not self.file_path.exists():
            logging.warning("arguments.txt missing → no custom args")
            return []
        text = self.file_path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        try:
            return shlex.split(text)
        except ValueError as e:
            logging.error("Could not parse arguments.txt: %s", e)
            return []

# ─── MCP Configuration Manager ────────────────────────────────────────────────

class MCPConfigManager:
    """Manages MCP server configuration (host and port)"""
    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.default_host = "127.0.0.1"
        self.default_port = 8000
        
    def ensure_exists(self) -> None:
        """Ensure config file exists with defaults"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            self.save_config(self.default_host, self.default_port)
            
    def load_config(self) -> tuple[str, int]:
        """Load host and port from config file"""
        try:
            if self.config_file.exists():
                config = json.loads(self.config_file.read_text(encoding="utf-8"))
                host = config.get("host", self.default_host)
                port = config.get("port", self.default_port)
                return host, port
        except Exception as e:
            logging.error("Failed to load MCP config: %s", e)
        return self.default_host, self.default_port
    
    def save_config(self, host: str, port: int) -> None:
        """Save host and port to config file"""
        try:
            config = {"host": host, "port": port}
            self.config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
            logging.info("Saved MCP config: %s:%s", host, port)
        except Exception as e:
            logging.error("Failed to save MCP config: %s", e)

# ─── Server Process Manager ──────────────────────────────────────────────────

class ServerManager:
    def __init__(self, exe_path: Path, arg_mgr: ArgumentManager):
        self.exe_path = exe_path
        self.arg_mgr = arg_mgr
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            logging.info("UxPlay server already running (PID %s)", self.process.pid)
            return

        if not self.exe_path.exists():
            logging.error("uxplay.exe not found at %s", self.exe_path)
            return

        cmd = [str(self.exe_path)] + self.arg_mgr.read_args()
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

# ─── Enhanced Server Manager with Frame Capture ───────────────────────────────

class EnhancedServerManager(ServerManager):
    """
    Enhanced server manager with screenshot capabilities.
    Extends ServerManager to add frame capture from UxPlay window.
    """
    def __init__(self, exe_path: Path, arg_mgr: ArgumentManager):
        super().__init__(exe_path, arg_mgr)
        self.frame_dir = Path(tempfile.gettempdir()) / "uxplay_frames"
        self.frame_dir.mkdir(parents=True, exist_ok=True)
        self.latest_frame = self.frame_dir / "latest_frame.png"

    def capture_frame(self) -> Optional[Path]:
        """
        Capture a frame from the UxPlay window.
        Returns path to captured frame or None if failed.
        """
        try:
            from PIL import ImageGrab
            import win32gui
            
            # Find the UxPlay window
            hwnd = win32gui.FindWindow(None, "UxPlay")
            if not hwnd:
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
                
        except ImportError as e:
            logging.warning("Required packages not available (%s), falling back to full screen capture", e)
            # Fallback: capture full screen
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                screenshot.save(str(self.latest_frame), format='PNG')
                return self.latest_frame
            except ImportError:
                logging.error("PIL not available, cannot capture screenshot")
                return None
            except Exception:
                logging.exception("Failed to capture frame")
                return None
        except Exception:
            logging.exception("Failed to capture frame")
            return None

# ─── Auto-Start Manager ───────────────────────────────────────────────────────

class AutoStartManager:
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def __init__(self, app_name: str, exe_cmd: str):
        self.app_name = app_name
        self.exe_cmd = exe_cmd

    def is_enabled(self) -> bool:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.RUN_KEY,
                0,
                winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, self.app_name)
                return self.exe_cmd in val
        except FileNotFoundError:
            return False
        except Exception:
            logging.exception("Error checking Autostart")
            return False

    def enable(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.RUN_KEY,
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(
                    key,
                    self.app_name,
                    0,
                    winreg.REG_SZ,
                    self.exe_cmd
                )
            logging.info("Autostart enabled")
        except Exception:
            logging.exception("Failed to enable Autostart")

    def disable(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.RUN_KEY,
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, self.app_name)
            logging.info("Autostart disabled")
        except FileNotFoundError:
            logging.info("No Autostart entry to delete")
        except Exception:
            logging.exception("Failed to disable Autostart")

    def toggle(self) -> None:
        if self.is_enabled():
            self.disable()
        else:
            self.enable()

# ─── MCP Server Manager ───────────────────────────────────────────────────────

class MCPServerManager:
    """Manages the MCP HTTP server lifecycle"""
    def __init__(self, server_mgr: EnhancedServerManager, mcp_config: MCPConfigManager):
        if not MCP_AVAILABLE:
            logging.warning("MCP dependencies not available, MCP server disabled")
        self.server_mgr = server_mgr
        self.mcp_config = mcp_config
        self.mcp_server_instance = None
        self.sse = None
        self.app = None
        self.server_thread: Optional[threading.Thread] = None
        self.uvicorn_server = None
        
    def _create_mcp_server(self):
        """Create the MCP server instance with tools"""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP dependencies not available")
        
        mcp_server = Server("uxplay-mcp-server")
        
        @mcp_server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="get_screenshot",
                    description="Capture a screenshot from the actual AirPlay video stream",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                ),
                Tool(
                    name="start_uxplay",
                    description="Start the UxPlay AirPlay server",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                ),
                Tool(
                    name="stop_uxplay",
                    description="Stop the UxPlay AirPlay server",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                ),
                Tool(
                    name="get_uxplay_status",
                    description="Get the current status of the UxPlay server",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                )
            ]
        
        @mcp_server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
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
        
        return mcp_server
    
    async def _handle_screenshot(self) -> list[TextContent | ImageContent]:
        """Capture screenshot from AirPlay stream"""
        try:
            if not (self.server_mgr.process and self.server_mgr.process.poll() is None):
                return [TextContent(type="text", text="Error: UxPlay is not running.")]
            
            frame_path = self.server_mgr.capture_frame()
            if not frame_path or not frame_path.exists():
                return [TextContent(type="text", text="Error: Failed to capture frame from UxPlay stream.")]
            
            with Image.open(frame_path) as img:
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_bytes = img_buffer.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                return [
                    ImageContent(type="image", data=img_base64, mimeType="image/png"),
                    TextContent(type="text", text=f"AirPlay screenshot captured. Size: {img.size[0]}x{img.size[1]} pixels")
                ]
        except Exception as e:
            logging.exception("Failed to capture screenshot")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _handle_start_uxplay(self) -> list[TextContent]:
        """Start UxPlay server"""
        try:
            self.server_mgr.start()
            await asyncio.sleep(1)
            if self.server_mgr.process and self.server_mgr.process.poll() is None:
                return [TextContent(type="text", text=f"UxPlay started (PID: {self.server_mgr.process.pid})")]
            return [TextContent(type="text", text="UxPlay start command sent")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _handle_stop_uxplay(self) -> list[TextContent]:
        """Stop UxPlay server"""
        try:
            self.server_mgr.stop()
            return [TextContent(type="text", text="UxPlay stopped")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _handle_get_status(self) -> list[TextContent]:
        """Get UxPlay server status"""
        try:
            is_running = self.server_mgr.process and self.server_mgr.process.poll() is None
            status = f"Running (PID: {self.server_mgr.process.pid})" if is_running else "Stopped"
            return [TextContent(type="text", text=f"UxPlay status: {status}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    def start(self) -> None:
        """Start the MCP HTTP server"""
        if not MCP_AVAILABLE:
            logging.error("Cannot start MCP server: dependencies not available")
            return
            
        if self.server_thread and self.server_thread.is_alive():
            logging.info("MCP server already running")
            return
        
        host, port = self.mcp_config.load_config()
        
        # Create MCP server and app
        self.mcp_server_instance = self._create_mcp_server()
        self.sse = SseServerTransport("/messages")
        
        async def handle_sse(scope, receive, send):
            async with self.sse.connect_sse(scope, receive, send) as streams:
                await self.mcp_server_instance.run(
                    streams[0], streams[1],
                    self.mcp_server_instance.create_initialization_options()
                )
        
        async def handle_messages(scope, receive, send):
            await self.sse.handle_post_message(scope, receive, send)
        
        self.app = Starlette(
            debug=False,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )
        
        # Run server in thread with proper event loop handling
        def run_server():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                config = uvicorn.Config(self.app, host=host, port=port, log_level="warning")
                self.uvicorn_server = uvicorn.Server(config)
                loop.run_until_complete(self.uvicorn_server.serve())
            finally:
                loop.close()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        logging.info("MCP server started on http://%s:%s", host, port)
    
    def stop(self) -> None:
        """Stop the MCP HTTP server"""
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True
            # Give server time to cleanup
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=2.0)
            logging.info("MCP server stopped")
    
    def is_running(self) -> bool:
        """Check if MCP server is running"""
        return self.server_thread and self.server_thread.is_alive()
    
    def get_url(self) -> str:
        """Get the MCP server URL"""
        host, port = self.mcp_config.load_config()
        return f"http://{host}:{port}/sse"
    
    def get_config_json(self) -> str:
        """Get the MCP client configuration JSON"""
        url = self.get_url()
        config = {
            "mcpServers": {
                "uxplay": {
                    "url": url
                }
            }
        }
        return json.dumps(config, indent=2)

# ─── System Tray Icon UI ─────────────────────────────────────────────────────

class TrayIcon:
    def __init__(
        self,
        icon_path: Path,
        server_mgr: EnhancedServerManager,
        arg_mgr: ArgumentManager,
        auto_mgr: AutoStartManager,
        mcp_mgr: MCPServerManager
    ):
        self.server_mgr = server_mgr
        self.arg_mgr = arg_mgr
        self.auto_mgr = auto_mgr
        self.mcp_mgr = mcp_mgr

        # Build menu items
        menu_items = [
            pystray.MenuItem("Start UxPlay", lambda _: server_mgr.start()),
            pystray.MenuItem("Stop UxPlay",  lambda _: server_mgr.stop()),
            pystray.MenuItem("Restart UxPlay", lambda _: self._restart()),
        ]
        
        # Add MCP menu items if MCP is available
        if MCP_AVAILABLE:
            menu_items.extend([
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Start MCP Server", lambda _: self._start_mcp()),
                pystray.MenuItem("Stop MCP Server", lambda _: self._stop_mcp()),
                pystray.MenuItem("MCP Settings", lambda _: self._show_mcp_settings()),
            ])
        
        # Add remaining menu items
        menu_items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Autostart with Windows",
                lambda _: auto_mgr.toggle(),
                checked=lambda _: auto_mgr.is_enabled()
            ),
            pystray.MenuItem(
                "Edit UxPlay Arguments",
                lambda _: self._open_args()
            ),
            pystray.MenuItem(
                "License",
                lambda _: webbrowser.open(
                    "https://github.com/leapbtw/uxplay-windows/blob/"
                    "main/LICENSE.md"
                )
            ),
            pystray.MenuItem("Exit", lambda _: self._exit())
        ])

        menu = pystray.Menu(*menu_items)

        self.icon = pystray.Icon(
            name=f"{APP_NAME}\nRight-click to configure.",
            icon=Image.open(icon_path),
            title=APP_NAME,
            menu=menu
        )

    def _restart(self):
        logging.info("Restarting UxPlay")
        self.server_mgr.stop()
        self.server_mgr.start()
    
    def _start_mcp(self):
        logging.info("Starting MCP server")
        self.mcp_mgr.start()
    
    def _stop_mcp(self):
        logging.info("Stopping MCP server")
        self.mcp_mgr.stop()
    
    def _show_mcp_settings(self):
        """Show MCP settings dialog"""
        try:
            import tkinter as tk
            from tkinter import messagebox, scrolledtext
        except ImportError:
            logging.error("tkinter not available, cannot show MCP settings dialog")
            # Try to show error using Windows message box
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "tkinter is not available. MCP settings dialog cannot be opened.\n\n"
                    "MCP configuration is stored in:\n"
                    f"{self.mcp_mgr.mcp_config.config_file}\n\n"
                    "Edit this file manually to configure host and port.",
                    "MCP Settings - Error",
                    0x10  # MB_ICONERROR
                )
            except Exception:
                logging.exception("Failed to show error dialog")
            return
        
        try:
            # Create settings window
            window = tk.Tk()
            window.title("MCP Server Settings")
            window.geometry("500x400")
            window.resizable(False, False)
            
            # Load current config
            host, port = self.mcp_mgr.mcp_config.load_config()
            
            # Host setting
            tk.Label(window, text="MCP Server Host:", font=("Arial", 10, "bold")).pack(pady=(10, 5))
            host_var = tk.StringVar(value=host)
            host_entry = tk.Entry(window, textvariable=host_var, width=40)
            host_entry.pack(pady=5)
            
            # Port setting
            tk.Label(window, text="MCP Server Port:", font=("Arial", 10, "bold")).pack(pady=(10, 5))
            port_var = tk.StringVar(value=str(port))
            port_entry = tk.Entry(window, textvariable=port_var, width=40)
            port_entry.pack(pady=5)
            
            # Save button
            def save_settings():
                try:
                    new_host = host_var.get().strip()
                    new_port = int(port_var.get().strip())
                    
                    if not new_host:
                        messagebox.showerror("Error", "Host cannot be empty")
                        return
                    if new_port < 1 or new_port > 65535:
                        messagebox.showerror("Error", "Port must be between 1 and 65535")
                        return
                    
                    self.mcp_mgr.mcp_config.save_config(new_host, new_port)
                    
                    # Update JSON display
                    json_text.delete(1.0, tk.END)
                    json_text.insert(1.0, self.mcp_mgr.get_config_json())
                    
                    messagebox.showinfo("Success", "Settings saved! Restart MCP server for changes to take effect.")
                except ValueError:
                    messagebox.showerror("Error", "Port must be a valid number")
            
            tk.Button(window, text="Save Settings", command=save_settings, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(pady=10)
            
            # Configuration JSON display
            tk.Label(window, text="MCP Client Configuration (copy this to your MCP client):", font=("Arial", 10, "bold")).pack(pady=(10, 5))
            json_text = scrolledtext.ScrolledText(window, width=55, height=8, font=("Courier", 9))
            json_text.pack(pady=5, padx=10)
            json_text.insert(1.0, self.mcp_mgr.get_config_json())
            
            # Copy button
            def copy_to_clipboard():
                window.clipboard_clear()
                window.clipboard_append(json_text.get(1.0, tk.END).strip())
                messagebox.showinfo("Copied", "Configuration copied to clipboard!")
            
            tk.Button(window, text="Copy to Clipboard", command=copy_to_clipboard, bg="#2196F3", fg="white").pack(pady=5)
            
            window.mainloop()
            
        except Exception as e:
            logging.exception("Failed to show MCP settings")

    def _open_args(self):
        self.arg_mgr.ensure_exists()
        try:
            os.startfile(str(self.arg_mgr.file_path))
            logging.info("Opened arguments.txt")
        except Exception:
            logging.exception("Failed to open arguments.txt")

    def _exit(self):
        logging.info("Exiting tray")
        self.mcp_mgr.stop()
        self.server_mgr.stop()
        self.icon.stop()

    def run(self):
        self.icon.run()

# ─── Application Orchestration ───────────────────────────────────────────────

class Application:
    def __init__(self):
        self.paths = Paths()
        self.arg_mgr = ArgumentManager(self.paths.arguments_file)
        self.mcp_config = MCPConfigManager(APPDATA_DIR / "mcp_config.json")

        # Build the exact command string for registry
        script = Path(__file__).resolve()
        if getattr(sys, "frozen", False):
            exe_cmd = f'"{sys.executable}"'
        else:
            exe_cmd = f'"{sys.executable}" "{script}"'

        self.auto_mgr = AutoStartManager(APP_NAME, exe_cmd)
        self.server_mgr = EnhancedServerManager(self.paths.uxplay_exe, self.arg_mgr)
        self.mcp_mgr = MCPServerManager(self.server_mgr, self.mcp_config)
        self.tray = TrayIcon(
            self.paths.icon_file,
            self.server_mgr,
            self.arg_mgr,
            self.auto_mgr,
            self.mcp_mgr
        )

    def run(self):
        self.arg_mgr.ensure_exists()
        self.mcp_config.ensure_exists()

        # delay server start so the tray icon appears immediately
        threading.Thread(target=self._delayed_start, daemon=True).start()

        logging.info("Launching tray icon")
        self.tray.run()
        logging.info("Tray exited – shutting down")

    def _delayed_start(self):
        time.sleep(3)
        self.server_mgr.start()
        # Optionally auto-start MCP server
        # self.mcp_mgr.start()

if __name__ == "__main__":
    Application().run()
