"""HamAlert to Discord notification service."""
import json
import logging
import telnetlib
import threading
import time
from typing import Optional, Dict, Any

import requests

from config import Config
from formatters import SpotFormatter, validate_spot_payload
from qrz import QRZClient
from utils import exponential_backoff, RateLimiter


# Constants
DEFAULT_TIMEOUT = 30
TELNET_KEEPALIVE_INTERVAL = 30
DISCORD_SUCCESS_CODE = 204
REQUEST_TIMEOUT = 10


class HeartbeatService:
    """Periodically pings an Uptime Kuma push URL to signal liveness."""

    def __init__(self, url: Optional[str], interval: int = 600, check_callback: Optional[callable] = None):
        """
        Initialize heartbeat service.

        Args:
            url: Uptime Kuma push URL
            interval: Heartbeat interval in seconds
            check_callback: Function that returns True if service is healthy
        """
        self.url = url
        self.interval = interval
        self.check_callback = check_callback
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

    def start(self) -> None:
        """Start the heartbeat service."""
        if not self.url:
            logging.warning("No heartbeat URL provided; heartbeat disabled.")
            return
        
        logging.info(
            "Starting heartbeat service (interval: %ss) → %s", 
            self.interval, 
            self.url
        )
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False

    def _run(self) -> None:
        """Run the heartbeat loop."""
        while self._running:
            # Only send heartbeat if service is healthy
            if self.check_callback is None or self.check_callback():
                try:
                    resp = requests.get(self.url, timeout=REQUEST_TIMEOUT)
                    if resp.ok:
                        logging.debug("Heartbeat ping succeeded.")
                    else:
                        logging.warning("Heartbeat ping returned %s", resp.status_code)
                except Exception as e:
                    logging.error("Heartbeat ping error: %s", e)
            else:
                logging.debug("Skipping heartbeat - service not connected")

            time.sleep(self.interval)


class DiscordNotifier:
    """Handles sending messages to a Discord webhook."""
    
    # Rate limit: 30 messages per minute per webhook
    _rate_limiter = RateLimiter(calls=30, period=60)
    
    def __init__(self, webhook_url: str, qrz_client: Optional[QRZClient] = None):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL
            qrz_client: QRZ client for callsign lookups
        """
        self.webhook_url = webhook_url
        self.formatter = SpotFormatter(qrz_client)

    @_rate_limiter
    def send_message(self, content: str) -> bool:
        """
        Send a message to Discord.
        
        Args:
            content: Message content
            
        Returns:
            True if successful, False otherwise
        """
        data = {"content": content}
        headers = {"Content-Type": "application/json"}
        
        logging.info("Sending Discord message: %s", content)
        
        try:
            resp = requests.post(
                self.webhook_url, 
                json=data, 
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            if resp.status_code != DISCORD_SUCCESS_CODE:
                logging.error(
                    "Discord webhook failed (status %s): %s", 
                    resp.status_code,
                    resp.text
                )
                return False
            
            return True
            
        except requests.RequestException as e:
            logging.error("Discord webhook error: %s", e)
            return False

    def send_spot(self, payload: Dict[str, Any]) -> bool:
        """
        Format and send a spot notification.
        
        Args:
            payload: Spot data from HamAlert
            
        Returns:
            True if successful, False otherwise
        """
        message = self.formatter.format_spot(payload)
        return self.send_message(message)


class TelnetListener:
    """Connects to a Telnet server, switches to JSON mode, and forwards spots to Discord."""
    
    def __init__(
        self, 
        host: str, 
        port: int, 
        username: str, 
        password: str, 
        notifier: DiscordNotifier
    ):
        """
        Initialize Telnet listener.
        
        Args:
            host: HamAlert server hostname
            port: HamAlert server port
            username: HamAlert username
            password: HamAlert password
            notifier: Discord notifier instance
        """
        self.host = host
        self.port = port
        self.username = username.upper()
        self.password = password
        self.notifier = notifier
        self._running = False
        self._connected = False

    def is_connected(self) -> bool:
        """Check if the listener is currently connected to HamAlert."""
        return self._connected and self._running

    def initialize_connection(self, tn: telnetlib.Telnet) -> bool:
        """
        Initialize the Telnet connection and switch to JSON mode.
        
        Args:
            tn: Telnet connection
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Give the server a moment to respond after password
            time.sleep(0.5)

            # Try to read any immediate response
            try:
                immediate_response = tn.read_very_eager()
                if immediate_response:
                    response_text = immediate_response.decode().strip()
                    if "login failed" in response_text.lower() or "check username" in response_text.lower():
                        logging.error("Authentication failed: %s", response_text)
                        return False
                    # Check if we already got the command prompt in the immediate response
                    if ">" in response_text and "hamalert" in response_text.lower():
                        tn.write(b"set/json\n")
                        # Read the response to set/json command
                        json_response = tn.read_until(b"\n", timeout=5).decode().strip()
                        if "operation successful" in json_response.lower():
                            self._connected = True
                            return True
            except Exception:
                pass

            while True:
                line = tn.read_until(b"\n", timeout=DEFAULT_TIMEOUT).decode().strip()

                if line.endswith("HamAlert"):
                    continue
                elif line.endswith(">"):
                    tn.write(b"set/json\n")
                    continue
                elif line == "Operation successful":
                    self._connected = True
                    return True
                elif "Invalid" in line or "incorrect" in line.lower() or "denied" in line.lower():
                    logging.error("Authentication failed: %s", line)
                    return False
                elif not line:
                    logging.error("Connection closed during initialization")
                    return False
                    
        except Exception as e:
            logging.error("Error during initialization: %s", e)
            self._connected = False
            return False

    def process_data(self, data: str) -> None:
        """
        Process incoming data from HamAlert.
        
        Args:
            data: Raw data string from Telnet
        """
        try:
            payload = json.loads(data)
            
            if validate_spot_payload(payload):
                self.notifier.send_spot(payload)
            else:
                logging.warning("Invalid spot payload: %s", payload)
                
        except json.JSONDecodeError:
            # Not JSON, send as raw message
            logging.debug("Non-JSON message received: %s", data)
            self.notifier.send_message(data)

    @exponential_backoff(max_retries=-1, initial_delay=1, max_delay=60)
    def _connect_and_run(self) -> None:
        """Connect to HamAlert and process messages."""
        logging.info("Connecting to %s:%s", self.host, self.port)

        with telnetlib.Telnet(self.host, self.port) as tn:
            # Login
            tn.read_until(b"login:")
            tn.write(self.username.encode() + b"\n")
            tn.read_until(b"password:")
            tn.write(self.password.encode() + b"\n")
            
            # Initialize connection
            if not self.initialize_connection(tn):
                self._connected = False
                raise ConnectionError("Failed to initialize connection")
            
            logging.info("Connected and initialized successfully")
            
            # Main message loop
            last_keepalive = time.time()
            
            while self._running:
                try:
                    line = tn.read_until(b"\n", timeout=1).decode().strip()
                    
                    if line:
                        logging.debug("Received: %s", line)
                        self.process_data(line)
                        last_keepalive = time.time()
                    
                    # Send keepalive if needed
                    if time.time() - last_keepalive > TELNET_KEEPALIVE_INTERVAL:
                        tn.sock.sendall(telnetlib.IAC + telnetlib.NOP)
                        last_keepalive = time.time()
                        logging.debug("Sent keepalive")
                        
                except Exception as e:
                    if self._running:
                        logging.error("Error in message loop: %s", e)
                        self._connected = False
                        raise

    def run(self) -> None:
        """Run the listener with automatic reconnection."""
        self._running = True
        try:
            self._connect_and_run()
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        finally:
            self._running = False

    def stop(self) -> None:
        """Stop the listener."""
        self._running = False
        self._connected = False


def setup_logging(level: str) -> None:
    """
    Configure logging.
    
    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main() -> None:
    """Main entry point."""
    try:
        # Load configuration
        config = Config.from_args()
        
        # Setup logging
        setup_logging(config.log_level)
        
        # Initialize QRZ client
        qrz_client = QRZClient(config.qrz_username, config.qrz_password)

        # Start listener
        notifier = DiscordNotifier(config.webhook_url, qrz_client)
        listener = TelnetListener(
            config.host,
            config.port,
            config.username,
            config.password,
            notifier
        )

        # Start heartbeat service with connection check
        heartbeat = HeartbeatService(
            config.heartbeat_url,
            config.heartbeat_interval,
            check_callback=listener.is_connected
        )
        heartbeat.start()
        
        # Run the listener (blocks until stopped)
        listener.run()
        
    except ValueError as e:
        logging.error("Configuration error: %s", e)
        exit(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        exit(1)


if __name__ == "__main__":
    main()
