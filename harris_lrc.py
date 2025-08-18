import logging, subprocess, re, socket, time, json, threading, base64, argparse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global router configuration
router_host = None
router_port = 52116

class harris_lrc:
    def __init__(self, host, port=52116):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        logger.info(f"harris_lrc initialized with host {host}:{port}")

    def connect(self):
        #Establish connection to the router.
        if self.connected:
            return True
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5) 
            self.sock.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to router at {self.host}:{self.port}")
            return True
        except (socket.error, ConnectionRefusedError) as e:
            logger.error(f"Failed to connect to router: {str(e)}")
            self.connected = False
            return False

    def ensure_connection(self):
        #Ensure connection is established before operations.
        if not self.connected:
            return self.connect()
        return True

    def clear_buffer(self):
        #Clear any existing data in the socket buffer to prevent mixed responses.
        if not self.ensure_connection():
            return False

        self.sock.settimeout(0.1)
        try:
            while self.sock.recv(4096):
                pass
        except socket.timeout:
            pass
        self.sock.settimeout(None)

    def status(self, dst, retries=3):
        #Send the status command and attempt to get a valid response.
        if not self.ensure_connection():
            return None

        for attempt in range(retries):
            try:
                self.clear_buffer()
                command = f"~XPOINT?D${{{dst}}}\\\n"
                self.sock.sendall(command.encode())

                time.sleep(0.5)

                response = self.sock.recv(4096).decode()

                if f"D${{{dst}}}" in response:
                    match = re.search(r"S\${(.*?)}\\", response)
                    if match:
                        source = match.group(1)
                        logger.info(f"Source '{source}' is routed to Destination '{dst}'")
                        return source
                    else:
                        logger.warning(f"Could not parse source for {dst}. Raw response: '{response.strip()}'")
                        return None

                logger.warning(f"Attempt {attempt + 1} failed. Retrying...")

            except socket.error as e:
                logger.error(f"Socket error during status check: {str(e)}")
                self.connected = False
                if attempt == retries - 1:
                    return None
                time.sleep(1) 

        logger.error(f"Failed to get a valid response for {dst} after {retries} attempts.")
        return None

    def route(self, src, dst, retries=3):
        #route a source to a destination
        for attempt in range(retries):
            self.clear_buffer()
            command = f"~XPOINT:S${{{src}}};D${{{dst}}}\\\n"  
            self.sock.sendall(command.encode())

            time.sleep(0.5)  

            response = self.sock.recv(4096).decode()
            print(f"Router Response: '{response.strip()}'")

            if "LOCK!D" in response:
                print(f"Destination '{dst}' is locked")
                return "locked" 
                
            current_source = self.status(dst)
            if current_source == src:
                print(f"Successfully routed Source '{src}' to Destination '{dst}'")
                return True
            else:
                print(f"Attempt {attempt + 1} failed. Unexpected response.")

        print(f"Failed to route Source '{src}' to Destination '{dst}' after {retries} attempts.")
        return False

    def close(self):
        #Close the connection to the router.
        if self.sock:
            self.sock.close()
            self.connected = False
            logger.info("Router connection closed")

    def clear_route(self, src, retries=3):
        #Clear the route for a source.
        if not self.ensure_connection():
            return False

        for attempt in range(retries):
            try:
                self.clear_buffer()
                command = f"~XPOINT%D${{{src}}}\\\n"
                self.sock.sendall(command.encode())

                time.sleep(1.0)

                response = self.sock.recv(4096).decode()
                logger.info(f"Clear Route Response: '{response.strip()}'")

                if "cleared" in response or f"D${{{src}}}" not in response:
                    logger.info(f"Successfully cleared route for Source '{src}'")
                    return True
                else:
                    logger.warning(f"Attempt {attempt + 1} failed. Response: '{response.strip()}'")

            except socket.error as e:
                logger.error(f"Socket error during clear route: {str(e)}")
                self.connected = False
                if attempt == retries - 1:
                    return False
                time.sleep(1)  

        logger.error(f"Failed to clear route for Source '{src}' after {retries} attempts.")
        return False
    
    def lock_destination(self, dst, retries=3):
        #Lock a destination
        for attempt in range(retries):
            self.clear_buffer()
            command = f"LOCK:D${{{dst}}};V${{ON}};U#{{20}}\\\n"
            self.sock.sendall(command.encode())

            time.sleep(0.5)

            response = self.sock.recv(4096).decode()
            print(f"Lock Response: '{response.strip()}'")

            print(f"Lock command sent for destination '{dst}'")
            return True

        return False

    def unlock_destination(self, dst, retries=3):
        #Unlock a destination
        for attempt in range(retries):
            self.clear_buffer()
            command = f"LOCK:D${{{dst}}};V${{OFF}};U#{{20}}\\\n" 
            self.sock.sendall(command.encode())

            time.sleep(0.5)

            response = self.sock.recv(4096).decode()
            print(f"Unlock Response: '{response.strip()}'")

            if response:
                print(f"Successfully unlocked destination '{dst}'")
                return True
            else:
                print(f"Attempt {attempt + 1} failed to unlock destination")

        print(f"Failed to unlock destination '{dst}' after {retries} attempts")
        return False

# HTML template will be decoded from base64 at startup
HTML_TEMPLATE = None

HTML_TEMPLATE_B64 = """PCFET0NUWVBFIGh0bWw+PGh0bWwgbGFuZz0iZW4iPjxoZWFkPjxtZXRhIGNoYXJzZXQ9IlVURi04Ij48
bWV0YSBuYW1lPSJ2aWV3cG9ydCIgY29udGVudD0id2lkdGg9ZGV2aWNlLXdpZHRoLCBpbml0aWFsLXNj
YWxlPTEuMCI+PHRpdGxlPlJvdXRlciBDb250cm9sIEludGVyZmFjZTwvdGl0bGU+PHN0eWxlPjpyb290
ey0tYmFja2dyb3VuZC1kYXJrOiMxYTFmMmU7LS1wYW5lbC1iZzojMjMyODM2Oy0tYnV0dG9uLWJnOiMy
YTMwM2U7LS1hY2NlbnQtY3lhbjojMDBmMGZmOy0tYWNjZW50LXJlZDojZmYzYjNiOy0tdGV4dC1wcmlt
YXJ5OiNmZmZmZmY7LS10ZXh0LXNlY29uZGFyeTpyZ2JhKDI1NSwyNTUsMjU1LDAuNyk7LS1ib3JkZXIt
Y29sb3I6cmdiYSgyNTUsMjU1LDI1NSwwLjEpfSp7bWFyZ2luOjA7cGFkZGluZzowO2JveC1zaXppbmc6
Ym9yZGVyLWJveDtmb250LWZhbWlseTotYXBwbGUtc3lzdGVtLEJsaW5rTWFjU3lzdGVtRm9udCwiU2Vn
b2UgVUkiLFJvYm90byxBcmlhbCxzYW5zLXNlcmlmfWJvZHl7YmFja2dyb3VuZC1jb2xvcjp2YXIoLS1i
YWNrZ3JvdW5kLWRhcmspO2NvbG9yOnZhcigtLXRleHQtcHJpbWFyeSk7bGluZS1oZWlnaHQ6MS41O21p
bi1oZWlnaHQ6MTAwdmh9LmNvbnRhaW5lcnttYXgtd2lkdGg6MTgwMHB4O21hcmdpbjowIGF1dG87cGFk
ZGluZzoyMHB4fS50b3AtYmFye2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2Vl
bjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbToyMHB4O3BhZGRpbmc6MTBweCAyMHB4O2Jh
Y2tncm91bmQtY29sb3I6dmFyKC0tcGFuZWwtYmcpO2JvcmRlci1yYWRpdXM6OHB4fS5zdGF0dXMtaW5k
aWNhdG9yc3tkaXNwbGF5OmZsZXg7Z2FwOjIwcHg7YWxpZ24taXRlbXM6Y2VudGVyfS5zdGF0dXMtaXRl
bXtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHh9LnN0YXR1cy1kb3R7d2lkdGg6
MTBweDtoZWlnaHQ6MTBweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kLWNvbG9yOnZhcigtLWFj
Y2VudC1yZWQpfS5zdGF0dXMtZG90LmFjdGl2ZXtiYWNrZ3JvdW5kLWNvbG9yOiMwMGZmMDB9LnRpbWVz
dGFtcHtjb2xvcjp2YXIoLS10ZXh0LXNlY29uZGFyeSk7Zm9udC1zaXplOjAuOWVtfS5tYWluLWNvbnRl
bnR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczphdXRvIDFmciBhdXRvIDFmciBhdXRv
O2dhcDoyMHB4O2hlaWdodDpjYWxjKDEwMHZoIC0gMTIwcHgpfS5wYW5lbHtiYWNrZ3JvdW5kLWNvbG9y
OnZhcigtLXBhbmVsLWJnKTtib3JkZXItcmFkaXVzOjhweDtvdmVyZmxvdzpoaWRkZW47ZGlzcGxheTpm
bGV4O2ZsZXgtZGlyZWN0aW9uOmNvbHVtbn0ucGFuZWwtaGVhZGVye3BhZGRpbmc6MTVweDtiYWNrZ3Jv
dW5kLWNvbG9yOnJnYmEoMCwwLDAsMC4yKX0ucGFuZWwtaGVhZGVyIGgye2ZvbnQtc2l6ZToxLjFlbTtm
b250LXdlaWdodDo1MDA7bWFyZ2luLWJvdHRvbToxMHB4fS5zZWFyY2gtY29udGFpbmVye2Rpc3BsYXk6
ZmxleDtnYXA6MTBweDthbGlnbi1pdGVtczpjZW50ZXJ9LnNlYXJjaC1pbnB1dHtmbGV4OjE7YmFja2dy
b3VuZC1jb2xvcjp2YXIoLS1idXR0b24tYmcpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyLWNv
bG9yKTtjb2xvcjp2YXIoLS10ZXh0LXByaW1hcnkpO3BhZGRpbmc6OHB4IDEycHg7Ym9yZGVyLXJhZGl1
czo0cHg7Zm9udC1zaXplOjAuOWVtfS5zZWFyY2gtaW5wdXQ6Zm9jdXN7b3V0bGluZTpub25lO2JvcmRl
ci1jb2xvcjp2YXIoLS1hY2NlbnQtY3lhbil9LmNvdW50LWJhZGdle2JhY2tncm91bmQtY29sb3I6dmFy
KC0tYnV0dG9uLWJnKTtwYWRkaW5nOjRweCA4cHg7Ym9yZGVyLXJhZGl1czo0cHg7Zm9udC1zaXplOjAu
OGVtO2NvbG9yOnZhcigtLXRleHQtc2Vjb25kYXJ5KX0ucGFuZWwtY29udGVudHtwYWRkaW5nOjE1cHg7
ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoNCxtaW5tYXgoMCwxZnIpKTtn
YXA6OHB4O292ZXJmbG93LXk6YXV0bztmbGV4OjE7YWxpZ24tY29udGVudDpzdGFydDtqdXN0aWZ5LWNv
bnRlbnQ6c3RhcnR9LnNvdXJjZS1idG4sLmRlc3RpbmF0aW9uLWJ0bntiYWNrZ3JvdW5kLWNvbG9yOnZh
cigtLWJ1dHRvbi1iZyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXItY29sb3IpO2NvbG9yOnZh
cigtLXRleHQtcHJpbWFyeSk7cGFkZGluZzo4cHggMTBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6
cG9pbnRlcjt0ZXh0LWFsaWduOmNlbnRlcjtmb250LXNpemU6MC45ZW07dHJhbnNpdGlvbjphbGwgMC4y
cyBlYXNlO3dpZHRoOjEyMHB4O2hlaWdodDo0MnB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50
ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtvdmVyZmxvdzpoaWRkZW47d2hpdGUtc3BhY2U6bm93cmFw
O3RleHQtb3ZlcmZsb3c6ZWxsaXBzaXN9LnNvdXJjZS1idG57Ym9yZGVyLWxlZnQ6M3B4IHNvbGlkIHZh
cigtLWFjY2VudC1jeWFuKX0uZGVzdGluYXRpb24tYnRue2hlaWdodDo0OHB4O3BhZGRpbmc6NHB4IDhw
eDtmbGV4LWRpcmVjdGlvbjpjb2x1bW47anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47Ym9yZGVy
LWxlZnQ6M3B4IHNvbGlkIHZhcigtLWFjY2VudC1yZWQpfS5zb3VyY2UtYnRuOmhvdmVyLC5kZXN0aW5h
dGlvbi1idG46aG92ZXJ7YmFja2dyb3VuZC1jb2xvcjpyZ2JhKDI1NSwyNTUsMjU1LDAuMSl9LnNvdXJj
ZS1idG4uc2VsZWN0ZWR7YmFja2dyb3VuZC1jb2xvcjpyZ2JhKDAsMjQwLDI1NSwwLjIpO2JvcmRlci1j
b2xvcjp2YXIoLS1hY2NlbnQtY3lhbil9LmRlc3RpbmF0aW9uLWJ0bi5zZWxlY3RlZHtiYWNrZ3JvdW5k
LWNvbG9yOnJnYmEoMjU1LDU5LDU5LDAuMik7Ym9yZGVyLWNvbG9yOnZhcigtLWFjY2VudC1yZWQpfS5y
b3V0ZS1jb250cm9sLXBhbmVse2Rpc3BsYXk6ZmxleDtmbGV4LWRpcmVjdGlvbjpjb2x1bW47anVzdGlm
eS1jb250ZW50OmNlbnRlcjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzoyMHB4O2JhY2tncm91bmQt
Y29sb3I6dmFyKC0tcGFuZWwtYmcpO2JvcmRlci1yYWRpdXM6OHB4O21pbi13aWR0aDozMDBweDtnYXA6
MjBweH0uc2VsZWN0aW9uLWRpc3BsYXl7YmFja2dyb3VuZC1jb2xvcjp2YXIoLS1idXR0b24tYmcpO2Jv
cmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyLWNvbG9yKTtib3JkZXItcmFkaXVzOjRweDtwYWRkaW5n
OjEwcHg7Y3Vyc29yOnBvaW50ZXI7bWluLWhlaWdodDo4MHB4O21pbi13aWR0aDoyMTBweH0uc2VsZWN0
aW9uLWxhYmVse2ZvbnQtc2l6ZTowLjhlbTtjb2xvcjp2YXIoLS10ZXh0LXNlY29uZGFyeSk7bWFyZ2lu
LWJvdHRvbTo1cHh9LnNlbGVjdGlvbi12YWx1ZXtmb250LXNpemU6MS4yZW07bWluLWhlaWdodDoxLjVl
bX0udGFrZS1idXR0b257YmFja2dyb3VuZC1jb2xvcjp2YXIoLS1idXR0b24tYmcpO2NvbG9yOnZhcigt
LXRleHQtcHJpbWFyeSk7Ym9yZGVyOjJweCBzb2xpZCB2YXIoLS1hY2NlbnQtY3lhbik7cGFkZGluZzox
NXB4IDQwcHg7Ym9yZGVyLXJhZGl1czo0cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEuMmVtO3Ry
YW5zaXRpb246YWxsIDAuMnMgZWFzZX0udGFrZS1idXR0b246aG92ZXJ7YmFja2dyb3VuZC1jb2xvcjpy
Z2JhKDAsMjQwLDI1NSwwLjIpfS50YWtlLWJ1dHRvbi5hY3RpdmV7YmFja2dyb3VuZC1jb2xvcjp2YXIo
LS1hY2NlbnQtY3lhbik7Y29sb3I6dmFyKC0tYmFja2dyb3VuZC1kYXJrKX0uY29udHJvbC1idG57YmFj
a2dyb3VuZC1jb2xvcjp2YXIoLS1idXR0b24tYmcpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVy
LWNvbG9yKTtjb2xvcjp2YXIoLS10ZXh0LXByaW1hcnkpO3BhZGRpbmc6OHB4IDEwcHg7Ym9yZGVyLXJh
ZGl1czo0cHg7Y3Vyc29yOnBvaW50ZXI7dGV4dC1hbGlnbjpjZW50ZXI7Zm9udC1zaXplOjAuOWVtO3Ry
YW5zaXRpb246YWxsIDAuMnMgZWFzZTt3aWR0aDoxMjBweDtoZWlnaHQ6NDJweDtkaXNwbGF5OmZsZXg7
YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7b3ZlcmZsb3c6aGlkZGVuO3do
aXRlLXNwYWNlOm5vd3JhcDt0ZXh0LW92ZXJmbG93OmVsbGlwc2lzO2JvcmRlci1sZWZ0OjNweCBzb2xp
ZCB2YXIoLS1hY2NlbnQtY3lhbil9LmNvbnRyb2wtYnRuOmhvdmVye2JhY2tncm91bmQtY29sb3I6cmdi
YSgwLDI0MCwyNTUsMC4xKX0uY29udHJvbC1idG4uc2VsZWN0ZWR7YmFja2dyb3VuZC1jb2xvcjp2YXIo
LS1hY2NlbnQtY3lhbik7Y29sb3I6dmFyKC0tYmFja2dyb3VuZC1kYXJrKX0uY2F0ZWdvcnktYnV0dG9u
c3tiYWNrZ3JvdW5kLWNvbG9yOnZhcigtLXBhbmVsLWJnKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5n
OjE1cHg7ZGlzcGxheTpmbGV4O2ZsZXgtZGlyZWN0aW9uOmNvbHVtbjtnYXA6MTBweDttYXgtd2lkdGg6
MTUwcHg7b3ZlcmZsb3cteTphdXRvfS5jYXRlZ29yeS1idG57YmFja2dyb3VuZC1jb2xvcjp2YXIoLS1i
dXR0b24tYmcpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyLWNvbG9yKTtjb2xvcjp2YXIoLS10
ZXh0LXByaW1hcnkpO3BhZGRpbmc6OHB4IDEycHg7Ym9yZGVyLXJhZGl1czo0cHg7Y3Vyc29yOnBvaW50
ZXI7dGV4dC1hbGlnbjpsZWZ0O3RyYW5zaXRpb246YWxsIDAuMnMgZWFzZX0uY2F0ZWdvcnktYnRuOmhv
dmVye2JhY2tncm91bmQtY29sb3I6cmdiYSgyNTUsMjU1LDI1NSwwLjEpfS5jYXRlZ29yeS1idG4uYWN0
aXZle2JhY2tncm91bmQtY29sb3I6dmFyKC0tYWNjZW50LWN5YW4pO2NvbG9yOnZhcigtLWJhY2tncm91
bmQtZGFyayl9LmxvY2stbWVzc2FnZXtkaXNwbGF5Om5vbmU7YmFja2dyb3VuZC1jb2xvcjojMjMyODM2
O2NvbG9yOnZhcigtLWFjY2VudC1yZWQpO3BhZGRpbmc6MTBweDt0ZXh0LWFsaWduOmNlbnRlcjtib3Jk
ZXI6c29saWQ7Ym9yZGVyLWNvbG9yOnZhcigtLWFjY2VudC1yZWQpO2JvcmRlci1yYWRpdXM6NHB4O21h
cmdpbi10b3A6MTBweDtmb250LXdlaWdodDpib2xkO21heC13aWR0aDoyNjBweDtwb3NpdGlvbjphYnNv
bHV0ZTtib3R0b206MzBweH0ubG9jay1tZXNzYWdlLnZpc2libGV7ZGlzcGxheTpibG9ja30uc2ltdWxh
dGlvbi1iYW5uZXJ7cG9zaXRpb246Zml4ZWQ7Ym90dG9tOjA7bGVmdDowO3JpZ2h0OjA7YmFja2dyb3Vu
ZC1jb2xvcjp2YXIoLS1hY2NlbnQtcmVkKTtjb2xvcjp3aGl0ZTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRk
aW5nOjhweDtmb250LXdlaWdodDo1MDB9LmhpZGRlbntkaXNwbGF5Om5vbmUhaW1wb3J0YW50fTo6LXdl
YmtpdC1zY3JvbGxiYXJ7d2lkdGg6OHB4fTo6LXdlYmtpdC1zY3JvbGxiYXItdHJhY2t7YmFja2dyb3Vu
ZDp2YXIoLS1idXR0b24tYmcpfTo6LXdlYmtpdC1zY3JvbGxiYXItdGh1bWJ7YmFja2dyb3VuZDp2YXIo
LS1ib3JkZXItY29sb3IpO2JvcmRlci1yYWRpdXM6NHB4fTo6LXdlYmtpdC1zY3JvbGxiYXItdGh1bWI6
aG92ZXJ7YmFja2dyb3VuZDp2YXIoLS10ZXh0LXNlY29uZGFyeSl9PC9zdHlsZT48L2hlYWQ+PGJvZHk+
PGRpdiBjbGFzcz0iY29udGFpbmVyIj48ZGl2IGNsYXNzPSJ0b3AtYmFyIj48ZGl2IGNsYXNzPSJzdGF0
dXMtaW5kaWNhdG9ycyI+PGRpdiBjbGFzcz0ic3RhdHVzLWl0ZW0iPjxzcGFuIGNsYXNzPSJzdGF0dXMt
ZG90IHtyb3V0ZXJfc3RhdHVzfSI+PC9zcGFuPjxzcGFuIGNsYXNzPSJzdGF0dXMtbGFiZWwiPlJvdXRl
ciBDb25uZWN0aW9uIFN0YXR1czwvc3Bhbj48L2Rpdj48ZGl2IGNsYXNzPSJ0aW1lc3RhbXAiPnt0aW1l
c3RhbXB9PC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0icm91dGVyLWNvbnRyb2xzIj48YnV0dG9uIGNsYXNz
PSJjb250cm9sLWJ0biIgZGF0YS1zb3VyY2U9IkhELUJBUlMiPkhEIEJBUlM8L2J1dHRvbj48L2Rpdj48
L2Rpdj48ZGl2IGNsYXNzPSJtYWluLWNvbnRlbnQiPjxkaXYgY2xhc3M9ImNhdGVnb3J5LWJ1dHRvbnMg
c291cmNlcyI+PGJ1dHRvbiBjbGFzcz0iY2F0ZWdvcnktYnRuIGFjdGl2ZSIgZGF0YS1jYXRlZ29yeT0i
YWxsIj5BbGwgU291cmNlczwvYnV0dG9uPntzb3VyY2VfY2F0ZWdvcmllc308L2Rpdj48ZGl2IGNsYXNz
PSJwYW5lbCBzb3VyY2VzLXBhbmVsIj48aDI+U09VUkNFUzwvaDI+PGRpdiBjbGFzcz0ic2VhcmNoLWNv
bnRhaW5lciI+PGlucHV0IHR5cGU9InRleHQiIGlkPSJzb3VyY2Utc2VhcmNoIiBjbGFzcz0ic2VhcmNo
LWlucHV0IiBwbGFjZWhvbGRlcj0iU2VhcmNoIHNvdXJjZXMuLi4iPjxkaXYgY2xhc3M9ImNvdW50LWJh
ZGdlIiBpZD0ic291cmNlLWNvdW50Ij4wLzA8L2Rpdj48L2Rpdj48ZGl2IGNsYXNzPSJwYW5lbC1jb250
ZW50IiBpZD0ic291cmNlcy1ncmlkIj57c291cmNlc308L2Rpdj48L2Rpdj48ZGl2IGNsYXNzPSJyb3V0
ZS1jb250cm9sLXBhbmVsIj48ZGl2IGlkPSJzZWxlY3RlZC1zb3VyY2UiIGNsYXNzPSJzZWxlY3Rpb24t
ZGlzcGxheSI+PGRpdiBjbGFzcz0ic2VsZWN0aW9uLWxhYmVsIj5TT1VSQ0U8L2Rpdj48ZGl2IGNsYXNz
PSJzZWxlY3Rpb24tdmFsdWUiPjwvZGl2PjwvZGl2PjxkaXYgY2xhc3M9InRha2UtYnV0dG9uLWNvbnRh
aW5lciI+PGJ1dHRvbiBjbGFzcz0idGFrZS1idXR0b24iPlRBS0U8L2J1dHRvbj48L2Rpdj48ZGl2IGlk
PSJzZWxlY3RlZC1kZXN0aW5hdGlvbiIgY2xhc3M9InNlbGVjdGlvbi1kaXNwbGF5Ij48ZGl2IGNsYXNz
PSJzZWxlY3Rpb24tbGFiZWwiPkRFU1RJTkFUSU9OPC9kaXY+PGRpdiBjbGFzcz0ic2VsZWN0aW9uLXZh
bHVlIj48L2Rpdj48L2Rpdj48ZGl2IGlkPSJsb2NrLW1lc3NhZ2UiIGNsYXNzPSJsb2NrLW1lc3NhZ2Ui
PkRlc3RpbmF0aW9uIGlzIGxvY2tlZCwgY29udGFjdCBFbmdpbmVlcmluZzwvZGl2PjwvZGl2PjxkaXYg
Y2xhc3M9InBhbmVsIGRlc3RpbmF0aW9ucy1wYW5lbCI+PGgyPkRFU1RJTkFUSU9OUzwvaDI+PGRpdiBj
bGFzcz0ic2VhcmNoLWNvbnRhaW5lciI+PGlucHV0IHR5cGU9InRleHQiIGlkPSJkZXN0aW5hdGlvbi1z
ZWFyY2giIGNsYXNzPSJzZWFyY2gtaW5wdXQiIHBsYWNlaG9sZGVyPSJTZWFyY2ggZGVzdGluYXRpb25z
Li4uIj48ZGl2IGNsYXNzPSJjb3VudC1iYWRnZSIgaWQ9ImRlc3RpbmF0aW9uLWNvdW50Ij4wLzA8L2Rp
dj48L2Rpdj48ZGl2IGNsYXNzPSJwYW5lbC1jb250ZW50IiBpZD0iZGVzdGluYXRpb25zLWdyaWQiPntk
ZXN0aW5hdGlvbnN9PC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0iY2F0ZWdvcnktYnV0dG9ucyBkZXN0aW5h
dGlvbnMiPjxidXR0b24gY2xhc3M9ImNhdGVnb3J5LWJ0biBhY3RpdmUiIGRhdGEtY2F0ZWdvcnk9ImFs
bCI+QWxsIERlc3RpbmF0aW9uczwvYnV0dG9uPntkZXN0aW5hdGlvbl9jYXRlZ29yaWVzfTwvZGl2Pjwv
ZGl2PntzaW11bGF0aW9uX2Jhbm5lcn08L2Rpdj48c2NyaXB0PmRvY3VtZW50LmFkZEV2ZW50TGlzdGVu
ZXIoJ0RPTUNvbnRlbnRMb2FkZWQnLGZ1bmN0aW9uKCl7bGV0IHNlbGVjdGVkU291cmNlPW51bGw7bGV0
IHNlbGVjdGVkRGVzdGluYXRpb249bnVsbDtmdW5jdGlvbiB1cGRhdGVUaW1lc3RhbXAoKXtjb25zdCB0
aW1lc3RhbXBFbGVtZW50PWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJy50aW1lc3RhbXAnKTtmdW5jdGlv
biB1cGRhdGUoKXtjb25zdCBub3c9bmV3IERhdGUoKTtjb25zdCBmb3JtYXR0ZWREYXRlPW5vdy50b0xv
Y2FsZURhdGVTdHJpbmcoJ2VuLUdCJyk7Y29uc3QgZm9ybWF0dGVkVGltZT1ub3cudG9Mb2NhbGVUaW1l
U3RyaW5nKCdlbi1HQicse2hvdXI6JzItZGlnaXQnLG1pbnV0ZTonMi1kaWdpdCcsc2Vjb25kOicyLWRp
Z2l0J30pO3RpbWVzdGFtcEVsZW1lbnQudGV4dENvbnRlbnQ9YCR7Zm9ybWF0dGVkRGF0ZX0gJHtmb3Jt
YXR0ZWRUaW1lfWA7fXVwZGF0ZSgpO3NldEludGVydmFsKHVwZGF0ZSwxMDAwKTt9ZnVuY3Rpb24gc2V0
dXBTZWFyY2goc2VhcmNoSWQsYnV0dG9uQ2xhc3MsY291bnRJZCl7Y29uc3Qgc2VhcmNoSW5wdXQ9ZG9j
dW1lbnQuZ2V0RWxlbWVudEJ5SWQoc2VhcmNoSWQpO2NvbnN0IGNvdW50RGlzcGxheT1kb2N1bWVudC5n
ZXRFbGVtZW50QnlJZChjb3VudElkKTtmdW5jdGlvbiB1cGRhdGVDb3VudCgpe2NvbnN0IHRvdGFsQnV0
dG9ucz1kb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKGAuJHtidXR0b25DbGFzc31gKS5sZW5ndGg7Y29u
c3QgdmlzaWJsZUJ1dHRvbnM9ZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbChgLiR7YnV0dG9uQ2xhc3N9
Om5vdCguaGlkZGVuKWApLmxlbmd0aDtjb3VudERpc3BsYXkudGV4dENvbnRlbnQ9YCR7dmlzaWJsZUJ1
dHRvbnN9LyR7dG90YWxCdXR0b25zfWA7fXVwZGF0ZUNvdW50KCk7c2VhcmNoSW5wdXQuYWRkRXZlbnRM
aXN0ZW5lcignaW5wdXQnLGZ1bmN0aW9uKCl7Y29uc3Qgc2VhcmNoVGVybT10aGlzLnZhbHVlLnRvTG93
ZXJDYXNlKCk7ZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbChgLiR7YnV0dG9uQ2xhc3N9YCkuZm9yRWFj
aChidG49Pntjb25zdCB0ZXh0PWJ0bi50ZXh0Q29udGVudC50b0xvd2VyQ2FzZSgpO2NvbnN0IGlzVmlz
aWJsZT10ZXh0LmluY2x1ZGVzKHNlYXJjaFRlcm0pO2J0bi5jbGFzc0xpc3QudG9nZ2xlKCdoaWRkZW4n
LCFpc1Zpc2libGUpO30pO3VwZGF0ZUNvdW50KCk7fSk7ZnVuY3Rpb24gY2xlYXJTZWFyY2goKXtkb2N1
bWVudC5xdWVyeVNlbGVjdG9yQWxsKGAuJHtidXR0b25DbGFzc31gKS5mb3JFYWNoKGJ0bj0+e2J0bi5j
bGFzc0xpc3QucmVtb3ZlKCdoaWRkZW4nKTt9KTt1cGRhdGVDb3VudCgpO31zZWFyY2hJbnB1dC5hZGRF
dmVudExpc3RlbmVyKCdzZWFyY2gnLGZ1bmN0aW9uKCl7aWYodGhpcy52YWx1ZT09PScnKXtjbGVhclNl
YXJjaCgpO319KTtzZWFyY2hJbnB1dC5hZGRFdmVudExpc3RlbmVyKCdrZXlkb3duJyxmdW5jdGlvbihl
KXtpZihlLmtleT09PSdFc2NhcGUnKXt0aGlzLnZhbHVlPScnO2NsZWFyU2VhcmNoKCk7fX0pO31mdW5j
dGlvbiBpbml0aWFsaXplQ2F0ZWdvcmllcygpe2RvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy5jYXRl
Z29yeS1idXR0b25zLnNvdXJjZXMgLmNhdGVnb3J5LWJ0bicpLmZvckVhY2goYnRuPT57YnRuLmFkZEV2
ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpe2NvbnN0IGNhdGVnb3J5PXRoaXMuZGF0YXNldC5j
YXRlZ29yeTtkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcuY2F0ZWdvcnktYnV0dG9ucy5zb3VyY2Vz
IC5jYXRlZ29yeS1idG4nKS5mb3JFYWNoKGI9PmIuY2xhc3NMaXN0LnJlbW92ZSgnYWN0aXZlJykpO3Ro
aXMuY2xhc3NMaXN0LmFkZCgnYWN0aXZlJyk7ZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgnLnNvdXJj
ZS1idG4nKS5mb3JFYWNoKHNvdXJjZUJ0bj0+e2lmKGNhdGVnb3J5PT09J2FsbCd8fHNvdXJjZUJ0bi5k
YXRhc2V0LmNhdGVnb3JpZXMuaW5jbHVkZXMoY2F0ZWdvcnkpKXtzb3VyY2VCdG4uY2xhc3NMaXN0LnJl
bW92ZSgnaGlkZGVuJyk7fWVsc2V7c291cmNlQnRuLmNsYXNzTGlzdC5hZGQoJ2hpZGRlbicpO319KTtj
b25zdCBjb3VudERpc3BsYXk9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3NvdXJjZS1jb3VudCcpO2Nv
bnN0IHRvdGFsQnV0dG9ucz1kb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcuc291cmNlLWJ0bicpLmxl
bmd0aDtjb25zdCB2aXNpYmxlQnV0dG9ucz1kb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcuc291cmNl
LWJ0bjpub3QoLmhpZGRlbiknKS5sZW5ndGg7Y291bnREaXNwbGF5LnRleHRDb250ZW50PWAke3Zpc2li
bGVCdXR0b25zfS8ke3RvdGFsQnV0dG9uc31gO30pO30pO2RvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwo
Jy5jYXRlZ29yeS1idXR0b25zLmRlc3RpbmF0aW9ucyAuY2F0ZWdvcnktYnRuJykuZm9yRWFjaChidG49
PntidG4uYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7Y29uc3QgY2F0ZWdvcnk9dGhp
cy5kYXRhc2V0LmNhdGVnb3J5O2RvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy5jYXRlZ29yeS1idXR0
b25zLmRlc3RpbmF0aW9ucyAuY2F0ZWdvcnktYnRuJykuZm9yRWFjaChiPT5iLmNsYXNzTGlzdC5yZW1v
dmUoJ2FjdGl2ZScpKTt0aGlzLmNsYXNzTGlzdC5hZGQoJ2FjdGl2ZScpO2RvY3VtZW50LnF1ZXJ5U2Vs
ZWN0b3JBbGwoJy5kZXN0aW5hdGlvbi1idG4nKS5mb3JFYWNoKGRlc3RCdG49PntpZihjYXRlZ29yeT09
PSdhbGwnfHxkZXN0QnRuLmRhdGFzZXQuY2F0ZWdvcmllcy5pbmNsdWRlcyhjYXRlZ29yeSkpe2Rlc3RC
dG4uY2xhc3NMaXN0LnJlbW92ZSgnaGlkZGVuJyk7fWVsc2V7ZGVzdEJ0bi5jbGFzc0xpc3QuYWRkKCdo
aWRkZW4nKTt9fSk7Y29uc3QgY291bnREaXNwbGF5PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdkZXN0
aW5hdGlvbi1jb3VudCcpO2NvbnN0IHRvdGFsQnV0dG9ucz1kb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxs
KCcuZGVzdGluYXRpb24tYnRuJykubGVuZ3RoO2NvbnN0IHZpc2libGVCdXR0b25zPWRvY3VtZW50LnF1
ZXJ5U2VsZWN0b3JBbGwoJy5kZXN0aW5hdGlvbi1idG46bm90KC5oaWRkZW4pJykubGVuZ3RoO2NvdW50
RGlzcGxheS50ZXh0Q29udGVudD1gJHt2aXNpYmxlQnV0dG9uc30vJHt0b3RhbEJ1dHRvbnN9YDt9KTt9
KTt9ZnVuY3Rpb24gdXBkYXRlRGVzdGluYXRpb25TdGF0dXMoZGVzdGluYXRpb24pe2NvbnN0IGJ0bj1k
b2N1bWVudC5xdWVyeVNlbGVjdG9yKGAuZGVzdGluYXRpb24tYnRuW2RhdGEtZGVzdGluYXRpb249IiR7
ZGVzdGluYXRpb259Il1gKTtpZighYnRuKXJldHVybjtmZXRjaChgL3N0YXR1cy8ke2Rlc3RpbmF0aW9u
fWApLnRoZW4ocmVzcG9uc2U9PnJlc3BvbnNlLmpzb24oKSkudGhlbihkYXRhPT57aWYoc2VsZWN0ZWRE
ZXN0aW5hdGlvbj09PWRlc3RpbmF0aW9uJiZkYXRhLnNvdXJjZSl7Y29uc3Qgc291cmNlQnRuPWRvY3Vt
ZW50LnF1ZXJ5U2VsZWN0b3IoYC5zb3VyY2UtYnRuW2RhdGEtc291cmNlPSIke2RhdGEuc291cmNlfSJd
YCk7aWYoZGF0YS5zb3VyY2U9PT0nSEQtQkFSUycpe3NlbGVjdFNvdXJjZSgnSEQtQkFSUycsZG9jdW1l
bnQucXVlcnlTZWxlY3RvcignLmNvbnRyb2wtYnRuW2RhdGEtc291cmNlPSJIRC1CQVJTIl0nKSk7fWVs
c2UgaWYoc291cmNlQnRuKXtzZWxlY3RTb3VyY2UoZGF0YS5zb3VyY2Usc291cmNlQnRuKTt9fX0pLmNh
dGNoKGVycm9yPT57Y29uc29sZS5lcnJvcignRXJyb3IgZ2V0dGluZyBzdGF0dXM6JyxlcnJvcik7fSk7
fWZ1bmN0aW9uIHNlbGVjdFNvdXJjZShzb3VyY2UsYnV0dG9uRWxlbWVudCl7ZG9jdW1lbnQucXVlcnlT
ZWxlY3RvckFsbCgnLnNvdXJjZS1idG4sIC5jb250cm9sLWJ0bicpLmZvckVhY2goYj0+Yi5jbGFzc0xp
c3QucmVtb3ZlKCdzZWxlY3RlZCcpKTtpZihidXR0b25FbGVtZW50KXtidXR0b25FbGVtZW50LmNsYXNz
TGlzdC5hZGQoJ3NlbGVjdGVkJyk7fXNlbGVjdGVkU291cmNlPXNvdXJjZTtkb2N1bWVudC5xdWVyeVNl
bGVjdG9yKCcjc2VsZWN0ZWQtc291cmNlIC5zZWxlY3Rpb24tdmFsdWUnKS50ZXh0Q29udGVudD1zb3Vy
Y2U7dXBkYXRlVGFrZUJ1dHRvbigpO31mdW5jdGlvbiByZXNldFNlbGVjdGlvbnMoKXtkb2N1bWVudC5x
dWVyeVNlbGVjdG9yQWxsKCcuc291cmNlLWJ0biwgLmNvbnRyb2wtYnRuJykuZm9yRWFjaChidG49PmJ0
bi5jbGFzc0xpc3QucmVtb3ZlKCdzZWxlY3RlZCcpKTtkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcu
ZGVzdGluYXRpb24tYnRuJykuZm9yRWFjaChidG49PmJ0bi5jbGFzc0xpc3QucmVtb3ZlKCdzZWxlY3Rl
ZCcpKTtkb2N1bWVudC5xdWVyeVNlbGVjdG9yKCcjc2VsZWN0ZWQtc291cmNlIC5zZWxlY3Rpb24tdmFs
dWUnKS50ZXh0Q29udGVudD0nJztkb2N1bWVudC5xdWVyeVNlbGVjdG9yKCcjc2VsZWN0ZWQtZGVzdGlu
YXRpb24gLnNlbGVjdGlvbi12YWx1ZScpLnRleHRDb250ZW50PScnO2RvY3VtZW50LmdldEVsZW1lbnRC
eUlkKCdsb2NrLW1lc3NhZ2UnKS5jbGFzc0xpc3QucmVtb3ZlKCd2aXNpYmxlJyk7c2VsZWN0ZWRTb3Vy
Y2U9bnVsbDtzZWxlY3RlZERlc3RpbmF0aW9uPW51bGw7dXBkYXRlVGFrZUJ1dHRvbigpO31mdW5jdGlv
biB1cGRhdGVUYWtlQnV0dG9uKCl7Y29uc3QgdGFrZUJ1dHRvbj1kb2N1bWVudC5xdWVyeVNlbGVjdG9y
KCcudGFrZS1idXR0b24nKTtpZihzZWxlY3RlZFNvdXJjZSYmc2VsZWN0ZWREZXN0aW5hdGlvbil7dGFr
ZUJ1dHRvbi5jbGFzc0xpc3QuYWRkKCdhY3RpdmUnKTt9ZWxzZXt0YWtlQnV0dG9uLmNsYXNzTGlzdC5y
ZW1vdmUoJ2FjdGl2ZScpO319ZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgnLnNvdXJjZS1idG4nKS5m
b3JFYWNoKGJ0bj0+e2J0bi5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXtzZWxlY3RT
b3VyY2UodGhpcy5kYXRhc2V0LnNvdXJjZSx0aGlzKTt9KTt9KTtkb2N1bWVudC5xdWVyeVNlbGVjdG9y
QWxsKCcuZGVzdGluYXRpb24tYnRuJykuZm9yRWFjaChidG49PntidG4uYWRkRXZlbnRMaXN0ZW5lcign
Y2xpY2snLGZ1bmN0aW9uKCl7ZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgnLmRlc3RpbmF0aW9uLWJ0
bicpLmZvckVhY2goYj0+Yi5jbGFzc0xpc3QucmVtb3ZlKCdzZWxlY3RlZCcpKTt0aGlzLmNsYXNzTGlz
dC5hZGQoJ3NlbGVjdGVkJyk7c2VsZWN0ZWREZXN0aW5hdGlvbj10aGlzLmRhdGFzZXQuZGVzdGluYXRp
b247ZG9jdW1lbnQucXVlcnlTZWxlY3RvcignI3NlbGVjdGVkLWRlc3RpbmF0aW9uIC5zZWxlY3Rpb24t
dmFsdWUnKS50ZXh0Q29udGVudD1zZWxlY3RlZERlc3RpbmF0aW9uO3VwZGF0ZVRha2VCdXR0b24oKTt1
cGRhdGVEZXN0aW5hdGlvblN0YXR1cyhzZWxlY3RlZERlc3RpbmF0aW9uKTt9KTt9KTtkb2N1bWVudC5n
ZXRFbGVtZW50QnlJZCgnc2VsZWN0ZWQtc291cmNlJykuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1
bmN0aW9uKCl7c2VsZWN0ZWRTb3VyY2U9bnVsbDt0aGlzLnF1ZXJ5U2VsZWN0b3IoJy5zZWxlY3Rpb24t
dmFsdWUnKS50ZXh0Q29udGVudD0nJztkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcuc291cmNlLWJ0
biwgLmNvbnRyb2wtYnRuJykuZm9yRWFjaChidG49PmJ0bi5jbGFzc0xpc3QucmVtb3ZlKCdzZWxlY3Rl
ZCcpKTt1cGRhdGVUYWtlQnV0dG9uKCk7fSk7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3NlbGVjdGVk
LWRlc3RpbmF0aW9uJykuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7c2VsZWN0ZWRE
ZXN0aW5hdGlvbj1udWxsO3RoaXMucXVlcnlTZWxlY3RvcignLnNlbGVjdGlvbi12YWx1ZScpLnRleHRD
b250ZW50PScnO2RvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy5kZXN0aW5hdGlvbi1idG4nKS5mb3JF
YWNoKGJ0bj0+YnRuLmNsYXNzTGlzdC5yZW1vdmUoJ3NlbGVjdGVkJykpO3VwZGF0ZVRha2VCdXR0b24o
KTtsb2NrTWVzc2FnZT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnbG9jay1tZXNzYWdlJykuY2xhc3NM
aXN0LnJlbW92ZSgndmlzaWJsZScpO30pO2RvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJy50YWtlLWJ1dHRv
bicpLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpe2lmKHNlbGVjdGVkU291cmNlJiZz
ZWxlY3RlZERlc3RpbmF0aW9uKXtmZXRjaCgnL3JvdXRlJyx7bWV0aG9kOidQT1NUJyxoZWFkZXJzOnsn
Q29udGVudC1UeXBlJzonYXBwbGljYXRpb24vanNvbicsfSxib2R5OkpTT04uc3RyaW5naWZ5KHtzb3Vy
Y2U6c2VsZWN0ZWRTb3VyY2UsZGVzdGluYXRpb246c2VsZWN0ZWREZXN0aW5hdGlvbn0pfSkudGhlbihy
ZXNwb25zZT0+cmVzcG9uc2UuanNvbigpKS50aGVuKGRhdGE9Pntjb25zb2xlLmxvZygnUm91dGUgcmVz
cG9uc2U6JyxkYXRhKTtjb25zdCBsb2NrTWVzc2FnZT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnbG9j
ay1tZXNzYWdlJyk7Y29uc29sZS5sb2coJ0xvY2sgbWVzc2FnZSBlbGVtZW50OicsbG9ja01lc3NhZ2Up
O2lmKGRhdGEubG9ja2VkKXtjb25zb2xlLmxvZygnU2hvd2luZyBsb2NrIG1lc3NhZ2UnKTtsb2NrTWVz
c2FnZS5jbGFzc0xpc3QuYWRkKCd2aXNpYmxlJyk7fWVsc2V7Y29uc29sZS5sb2coJ0hpZGluZyBsb2Nr
IG1lc3NhZ2UnKTtsb2NrTWVzc2FnZS5jbGFzc0xpc3QucmVtb3ZlKCd2aXNpYmxlJyk7aWYoZGF0YS5z
dWNjZXNzKXtyZXNldFNlbGVjdGlvbnMoKTt9fX0pO319KTtkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxs
KCcuY29udHJvbC1idG4nKS5mb3JFYWNoKGJ0bj0+e2J0bi5hZGRFdmVudExpc3RlbmVyKCdjbGljaycs
ZnVuY3Rpb24oKXtzZWxlY3RTb3VyY2UodGhpcy5kYXRhc2V0LnNvdXJjZSx0aGlzKTt9KTt9KTt1cGRh
dGVUaW1lc3RhbXAoKTtzZXR1cFNlYXJjaCgnc291cmNlLXNlYXJjaCcsJ3NvdXJjZS1idG4nLCdzb3Vy
Y2UtY291bnQnKTtzZXR1cFNlYXJjaCgnZGVzdGluYXRpb24tc2VhcmNoJywnZGVzdGluYXRpb24tYnRu
JywnZGVzdGluYXRpb24tY291bnQnKTtpbml0aWFsaXplQ2F0ZWdvcmllcygpO30pOzwvc2NyaXB0Pjwv
Ym9keT48L2h0bWw+Cg=="""

def load_ui_template():
    global HTML_TEMPLATE
    HTML_TEMPLATE = base64.b64decode(HTML_TEMPLATE_B64).decode('utf-8')

# Global variables
router = None
simulation_mode = False
SOURCES = {
    
}
DESTINATIONS = {

}
SOURCE_ALIASES = {

}
DESTINATION_ALIASES = {

}


#
# Source and Destination Categories
#

SOURCE_CATEGORIES = {
    'SRC CAT 1': ['', '', '', ''], 
    'SRC CAT 2': ['', '', '', ''],
    'SRC CAT 3': ['', '', '', ''],
    'SRC CAT 4': ['', '', '', ''],
    }

DESTINATION_CATEGORIES = {
    'DST CAT 1': ['', '', '', ''], 
    'DST CAT 2': ['', '', '', ''],
    'DST CAT 3': ['', '', '', ''],
    'DST CAT 4': ['', '', '', ''],
}

def categorize_with_mapping(items, category_map):
    #Categorize items based on custom mapping
    categories = {}
    uncategorized = []

    for category, category_items in category_map.items():
        categories[category] = []
        for item in items:
            if item in category_items:
                categories[category].append(item)
        categories[category].sort()

    categorized_items = [item for sublist in category_map.values() for item in sublist]
    uncategorized = [item for item in items if item not in categorized_items]

    if uncategorized:
        categories['Other'] = sorted(uncategorized)

    categories = {k: v for k, v in categories.items() if v}

    return dict(sorted(categories.items()))

def load_router_config():
    global SOURCES, DESTINATIONS, router
    try:
        # Ensure router connection is available
        if router is None:
            initialize_router()
        
        if router is None or simulation_mode:
            logger.warning("Router not available, using empty configuration")
            return {}, {}
        
        # Query sources from router using proper Harris LRC protocol
        sources = []
        SOURCES.clear()
        try:
            router.clear_buffer()
            src_command = "~SRC?Q${NAME}\\\n"
            router.sock.sendall(src_command.encode())
            
            import time
            time.sleep(0.5)
            
            # Read the full response until we see the termination marker
            src_response = ""
            while True:
                chunk = router.sock.recv(4096).decode()
                src_response += chunk
                if '~SRC%Q${NAME}\\' in src_response:  # Complete response received
                    break
                    
            logger.info(f"Source query response length: {len(src_response)} characters")
            logger.info(f"Source query response (first 200 chars): '{src_response[:200]}...'")
            
            # Parse source entries using the working pattern
            src_pattern = r'~SRC%I#\{(\d+)\};NAME\$\{([^}]+)\}'
            src_matches = re.findall(src_pattern, src_response)
            logger.info(f"Source regex matches: {len(src_matches)} total matches")
            
            # Sort by source number and populate SOURCES dict
            src_matches.sort(key=lambda x: int(x[0]))
            for number, name in src_matches:
                SOURCES[int(number)] = name
                sources.append(name)
            
            logger.info(f"Loaded {len(sources)} sources from router")
            
        except Exception as e:
            logger.error(f"Error querying sources: {str(e)}")
        
        # Query destinations from router using proper Harris LRC protocol
        destinations = []
        DESTINATIONS.clear()
        try:
            router.clear_buffer()
            dest_command = "~DEST?Q${NAME}\\\n"
            router.sock.sendall(dest_command.encode())
            
            time.sleep(0.5)
            
            # Read the full response until we see the termination marker
            dest_response = ""
            while True:
                chunk = router.sock.recv(4096).decode()
                dest_response += chunk
                if '~DEST%Q${NAME}\\' in dest_response:  # Complete response received
                    break
                    
            logger.info(f"Destination query response length: {len(dest_response)} characters")
            logger.info(f"Destination query response (first 200 chars): '{dest_response[:200]}...'")
            
            # Parse destination entries using the working pattern
            dest_pattern = r'~DEST%I#\{(\d+)\};NAME\$\{([^}]+)\}'
            dest_matches = re.findall(dest_pattern, dest_response)
            logger.info(f"Destination regex matches: {len(dest_matches)} total matches")
            
            # Sort by destination number and populate DESTINATIONS dict
            dest_matches.sort(key=lambda x: int(x[0]))
            for number, name in dest_matches:
                DESTINATIONS[int(number)] = name
                destinations.append(name)
            
            logger.info(f"Loaded {len(destinations)} destinations from router")
            
        except Exception as e:
            logger.error(f"Error querying destinations: {str(e)}")
        
        # Add alias sources while keeping originals
        for alias in SOURCE_ALIASES.keys():
            if SOURCE_ALIASES[alias] in sources:
                sources.append(alias)

        # Add alias destinations while keeping originals
        for alias in DESTINATION_ALIASES.keys():
            if DESTINATION_ALIASES[alias] in destinations:
                destinations.append(alias)
        
        grouped_sources = categorize_with_mapping(sources, SOURCE_CATEGORIES)
        grouped_destinations = categorize_with_mapping(destinations, DESTINATION_CATEGORIES)
        
        logger.info(f"Successfully loaded and categorized router configuration from router queries")
        return grouped_sources, grouped_destinations
        
    except Exception as e:
        logger.error(f"Error loading router config: {str(e)}")
        return {}, {}
    

def try_router_connection(host, port=52116):
    #Attempt to connect to the router
    global router, simulation_mode
    try:
        router = harris_lrc(host, port)
        simulation_mode = False
        logger.info("Successfully connected to physical router")
        return True
    except Exception as e:
        logger.warning(f"Router connection failed: {str(e)}")
        return False

def initialize_router():
    #Initialize router connection
    global router, router_host, router_port
    if router is None and router_host is not None:
        try_router_connection(router_host, router_port)


class RouterHTTPRequestHandler(BaseHTTPRequestHandler):
    #HTTP requets for router control interface
    
    def do_GET(self):
        #Handle GET requests
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/':
            self.serve_index()
        elif path.startswith('/status/'):
            destination = path.split('/')[-1]
            self.handle_status(destination)
        elif path == '/router_status':
            self.handle_router_status()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        #Handle POST requests
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/route':
            self.handle_route()
        elif path.startswith('/lock/'):
            destination = path.split('/')[-1]
            self.handle_lock(destination)
        elif path.startswith('/unlock/'):
            destination = path.split('/')[-1]
            self.handle_unlock(destination)
        else:
            self.send_error(404, "Not Found")
    
    def serve_index(self):
        #Serve the main index.html page with router data
        try:
            # Load router configuration
            grouped_sources, grouped_destinations = load_router_config()
            
            # Extract flat lists from categorized data
            sources = []
            for category_items in grouped_sources.values():
                sources.extend(category_items)
            sources = sorted(list(set(sources)))  # Remove duplicates and sort
            
            destinations = []
            for category_items in grouped_destinations.values():
                destinations.extend(category_items)
            destinations = sorted(list(set(destinations)))  # Remove duplicates and sort
            
            # Render embedded template with context
            html_content = self.render_template(
                sources=sources,
                destinations=destinations,
                source_categories=list(SOURCE_CATEGORIES.keys()),
                destination_categories=list(DESTINATION_CATEGORIES.keys()),
                source_to_categories={src: [cat for cat, items in SOURCE_CATEGORIES.items() if src in items] for src in sources},
                destination_to_categories={dst: [cat for cat, items in DESTINATION_CATEGORIES.items() if dst in items] for dst in destinations},
                simulation_mode=simulation_mode
            )
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error serving index: {str(e)}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    

    
    def handle_route(self):
        #Handle routing requests
        if router is None:
            initialize_router()
        
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            source = data.get('source')
            destination = data.get('destination')
            
            if not source or not destination:
                response = {
                    'success': False, 
                    'message': 'Source and destination required'
                }
            else:
                router_destination = DESTINATION_ALIASES.get(destination, destination)
                router_source = SOURCE_ALIASES.get(source, source)
                
                result = router.route(router_source, router_destination)
                
                if result == "locked":
                    response = {
                        'success': False,
                        'locked': True,
                        'message': 'Destination is locked, contact Engineering',
                        'simulation': simulation_mode
                    }
                else:
                    response = {
                        'success': True,
                        'result': result,
                        'simulation': simulation_mode
                    }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in route operation: {str(e)}")
            response = {
                'success': False,
                'message': f'Error: {str(e)}',
                'simulation': simulation_mode
            }
            self.send_json_response(response)
    
    def handle_status(self, destination):
        #Handle status requests
        if router is None:
            initialize_router()
        
        try:
            router_destination = DESTINATION_ALIASES.get(destination, destination)
            current_source = router.status(router_destination)
            
            response = {
                'success': True if current_source else False,
                'source': current_source,
                'destination': destination,
                'simulation': simulation_mode
            }
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in status check: {str(e)}")
            response = {
                'success': False,
                'message': str(e),
                'simulation': simulation_mode
            }
            self.send_json_response(response)
    
    def handle_router_status(self):
        #Handle router status requests
        if router is None:
            initialize_router()
        
        response = {
            'simulation_mode': simulation_mode,
            'status': 'Simulated' if simulation_mode else 'Connected'
        }
        self.send_json_response(response)
    
    def handle_lock(self, destination):
        #Handle lock destination requests
        if router is None:
            initialize_router()
        
        try:
            router_destination = DESTINATION_ALIASES.get(destination, destination)
            success = router.lock_destination(router_destination)
            response = {
                'success': success,
                'message': f"{'Successfully locked' if success else 'Failed to lock'} {destination}",
                'simulation': simulation_mode
            }
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in lock operation: {str(e)}")
            response = {
                'success': False,
                'message': f'Error: {str(e)}',
                'simulation': simulation_mode
            }
            self.send_json_response(response)
    
    def handle_unlock(self, destination):
        #Handle unlock destination requests
        if router is None:
            initialize_router()
        
        try:
            router_destination = DESTINATION_ALIASES.get(destination, destination)
            success = router.unlock_destination(router_destination)
            response = {
                'success': success,
                'message': f"{'Successfully unlocked' if success else 'Failed to unlock'} {destination}",
                'simulation': simulation_mode
            }
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in unlock operation: {str(e)}")
            response = {
                'success': False,
                'message': f'Error: {str(e)}',
                'simulation': simulation_mode
            }
            self.send_json_response(response)
    
    def send_json_response(self, data):
        #Send a JSON response
        json_data = json.dumps(data)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json_data.encode('utf-8'))
    
    def render_template(self, **context):
        #Render the embedded HTML template with context data
        rendered = HTML_TEMPLATE
        
        # Generate HTML for sources
        sources_html = ""
        for source in context.get('sources', []):
            categories = " ".join(context.get('source_to_categories', {}).get(source, []))
            sources_html += f'<div class="source-btn" data-source="{source}" data-categories="{categories}">{source}</div>\n'
        
        # Generate HTML for destinations  
        destinations_html = ""
        for destination in context.get('destinations', []):
            categories = " ".join(context.get('destination_to_categories', {}).get(destination, []))
            destinations_html += f'<div class="destination-btn" data-destination="{destination}" data-categories="{categories}">{destination}</div>\n'
        
        # Generate HTML for source categories
        source_categories_html = ""
        for category in context.get('source_categories', []):
            source_categories_html += f'<button class="category-btn" data-category="{category}">{category}</button>\n'
        
        # Generate HTML for destination categories
        destination_categories_html = ""
        for category in context.get('destination_categories', []):
            destination_categories_html += f'<button class="category-btn" data-category="{category}">{category}</button>\n'
        
        # Router status
        router_status = "active" if not context.get('simulation_mode', False) else ""
        
        # Simulation banner
        simulation_banner = '<div class="simulation-banner">Router Not Connected</div>' if context.get('simulation_mode', False) else ""
        
        # Current timestamp
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        # Replace placeholders
        rendered = rendered.replace('{sources}', sources_html)
        rendered = rendered.replace('{destinations}', destinations_html)
        rendered = rendered.replace('{source_categories}', source_categories_html)
        rendered = rendered.replace('{destination_categories}', destination_categories_html)
        rendered = rendered.replace('{router_status}', router_status)
        rendered = rendered.replace('{simulation_banner}', simulation_banner)
        rendered = rendered.replace('{timestamp}', timestamp)
        
        return rendered
    
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")


def start_server(port=5050):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, RouterHTTPRequestHandler)
    logger.info(f"Starting HTTP server on {server_address[0]}:{server_address[1]}")
    
    # Initialize router in a separate thread
    router_thread = threading.Thread(target=initialize_router)
    router_thread.daemon = True
    router_thread.start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        httpd.shutdown()


def parse_arguments():
    parser = argparse.ArgumentParser(description='Harris LRC Router Control Server')
    parser.add_argument('--host', required=True, help='Router IP address (required)')
    parser.add_argument('--port', type=int, default=52116, help='Router port (default: 52116)')
    return parser.parse_args()

def set_router_config(host, port):
    global router_host, router_port
    router_host = host
    router_port = port

if __name__ == '__main__':
    args = parse_arguments()
    set_router_config(args.host, args.port)
    
    logger.info(f"Starting router control server...")
    logger.info(f"Router: {router_host}:{router_port}")
    logger.info(f"Web server will run on port 5050")
    
    load_ui_template()  
    start_server(5050)
