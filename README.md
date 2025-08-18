# Harris LRC Router Control

A web-based control interface for Harris LRC systems. This application provides web interface for managing video routing, monitoring router status, and controlling destination locks on Harris LRC routers.

<img width="1572" height="772" alt="image" src="https://github.com/user-attachments/assets/e2fb6fbe-9569-47c6-b335-820acbcc071b" />


## Features

- **Real-time Router Control**: Direct communication with Harris LRC routers via TCP socket
- **Web-based Interface**: Works on all modern browsers
- **Live Status Monitoring**: Real-time monitoring of router connections and routing status
- **Destination Management**: Lock and unlock destinations to prevent accidental routing changes
- **Source/Destination Discovery**: Automatically queries the router for available sources and destinations
- **Categorized Display**: Organizes sources and destinations into logical categories for easy navigation
- **Self-contained**: Single Python file with embedded web interface - no external dependencies

## Requirements

- Python 3.12.3 or higher
- Harris LRC router with TCP/IP connectivity
- Network access to the router on port 52116 (default)

## Installation

1. Download the `Harris_LRC.py` file
2. Ensure Python 3.12.3+ is installed on your system
3. No additional dependencies required - uses only Python standard library

## Usage

### Basic Usage

```bash
python Harris_LRC.py --host <router_ip>
```

### Command Line Options

- `--host` (required): IP address of the Harris LRC router
- `--port` (optional): Router port (default: 52116)

### Examples

```bash
# Connect to router at 192.168.1.100
python Harris_LRC.py --host 192.168.1.100

# Connect with custom port
python Harris_LRC.py --host 192.168.1.100 --port 52116
```

### Web Interface

Once started, the web interface is available at:
```
http://localhost:5050
```

## Web Interface Features

### Main Dashboard
- **Source Selection**: Choose from categorized list of available sources
- **Destination Selection**: Select destination for routing
- **Route Button**: Execute routing commands
- **Status Display**: Shows current routing status and connection state

### Router Status
- Real-time connection status
- Current source-to-destination mappings
- Router response monitoring

### Destination Management
- **Lock Destinations**: Prevent accidental routing changes
- **Unlock Destinations**: Re-enable routing to locked destinations
- **Status Indicators**: Visual feedback for lock/unlock operations

## Router Communication

The application communicates with Harris LRC routers using the standard LRC protocol:

- **Status Queries**: `~STATUS?D${destination}\n`
- **Routing Commands**: `~XPOINT:S${source};D${destination}\n`
- **Lock Commands**: `LOCK:D${destination};V${ON/OFF};U#{20}\n`
- **Configuration Queries**: `~SRC?Q${NAME}\n` and `~DEST?Q${NAME}\n`

## Technical Details

- **Protocol**: Harris LRC over TCP/IP
- **Web Server**: Python standard library HTTP server
- **Port Configuration**: Router port configurable, web server fixed at 5050
- **Threading**: Asynchronous router communication to prevent UI blocking
- **Error Handling**: Retry logic and error reporting

## Development

The application is designed as a single, self-contained Python file for easy deployment and maintenance. All web assets are embedded within the Python code, eliminating the need for external files or complex deployment procedures.

### Architecture
- **harris_lrc Class**: Handles all router communication and protocol implementation
- **RouterHTTPRequestHandler**: Manages web requests and API endpoints
- **Embedded UI**: Complete web interface embedded within the application

## License

This software is provided as-is for controlling Harris LRC router systems. Please ensure compliance with your organization's network and equipment policies before deployment.

---

**Note**: This application is designed specifically for Harris LRC router systems. Compatibility with other router types is not guaranteed.
