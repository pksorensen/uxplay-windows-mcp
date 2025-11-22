# FREE AirPlay to your Windows PC
Free as both in "freedom" and "free beer"!

## Installation

Download the latest version of uxplay-windows from [**releases**](https://github.com/leapbtw/uxplay-windows/releases/latest).

After installing, control uxplay-windows from its [tray icon](https://www.odu.edu/sites/default/files/documents/win10-system-tray.pdf)! Right-click it to:
- Start/Stop AirPlay server
- **Start/Stop MCP Server** (for AI assistant integration)
- **Configure MCP Settings** (host, port, and client configuration)
- Set to run automatically when your PC starts

## MCP Server Integration

This application includes a built-in MCP (Model Context Protocol) server that allows AI assistants and other MCP clients to control UxPlay and capture screenshots directly from the AirPlay video stream.

### Using the MCP Server

1. **Install the application** as normal from the releases page
2. **Right-click the tray icon** and select "Start MCP Server"
3. **Open MCP Settings** from the tray menu to:
   - Configure the server host and port (default: 127.0.0.1:8000)
   - Copy the MCP client configuration JSON
4. **Paste the configuration** into your MCP client (e.g., Claude Desktop)

### MCP Features

- **HTTP-based server** - Works over network, no Python scripts needed
- **Screenshot from AirPlay stream** - Captures actual mirrored content, not desktop
- **Background operation** - Works even when UxPlay window is minimized
- **Easy configuration** - Settings UI with copy-paste JSON for MCP clients

### Available MCP Tools

- `get_screenshot` - Capture a screenshot from the AirPlay video stream
- `start_uxplay` - Start the UxPlay AirPlay server
- `stop_uxplay` - Stop the UxPlay AirPlay server
- `get_uxplay_status` - Check if UxPlay is running

### Configuration Example

The MCP Settings dialog will show you the configuration to copy into your MCP client:

```json
{
  "mcpServers": {
    "uxplay": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

## FAQ — Please Read!
> [!NOTE]
> *What is uxplay-windows?*
> 
> [UxPlay](https://github.com/FDH2/UxPlay/) allows you to screen share from your Apple devices to non-Apple ones using AirPlay.
> 
> [uxplay-windows](.) (this project) wraps binaries of UxPlay into a fully featured App for Windows 10/11 users, making it easier for those who may find compiling UxPlay challenging. Most other software achieving the same functionality as `uxplay-windows` is usually paid and non-free.


> [!TIP]
> *My \<apple device\> can't connect to my PC!!!*
> 1. Check if the `uxplay.exe` is running: right-click the tray icon and restart it.
> 2. Toggle Wi-Fi OFF on your iPhone/iPad/Mac, wait a couple of seconds and reconnect. It might take a few attempts.
> 3. As last resort, close uxplay-windows, open Task Manager and restart `Bonjour Service` from the Services tab. Then reopen uxplay-windows and try again

> [!IMPORTANT]
> *Why is Windows Defender complaining during installation?*
> 
> ![alt text](https://raw.githubusercontent.com/leapbtw/uxplay-windows/refs/heads/main/stuff/defender.png "defender")
>
> Just click on `More info` and it will let you install. It complains because the executable is not signed. If you don't trust this software you can always build it yourself! See below.
>
> If prompted by Windows Firewall, please **allow** uxplay-windows to ensure it functions properly.


> [!NOTE]
>  *How do I build this software myself?*
> 
> Please see [BUILDING.md](./BUILDING.md)
<br>

## TODO
- make colored icon to show if uxplay is running or not
- make an update checker

## Known Issues
- uxplay bugs out when waking PC from Sleep
  - you can fix this by killing uxplay.exe and restarting Bonjour Service, and restarting uxplay.exe. Also restarting your PC might fix this.

## Reporting Issues
Please report issues related to the build system created with GitHub Actions in this repository. For issues related to other parts of this software, report them in their respective repositories.

## License
Please take a look at the [LICENSE](./LICENSE).
