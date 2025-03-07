import argparse
import json
import logging
import os
import telnetlib
import time
import requests


class DiscordNotifier:
    """Handles sending messages to a Discord webhook."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_message(self, content: str) -> None:
        data = {"content": content}
        headers = {"Content-Type": "application/json"}
        logging.info("Sending message to Discord: %s", content)
        response = requests.post(self.webhook_url, json=data, headers=headers)
        if response.status_code == 204:
            logging.info("Discord webhook sent successfully.")
        else:
            logging.error("Failed to send Discord webhook. Status code: %s", response.status_code)


class TelnetListener:
    """Connects to the Telnet server, performs initialization, and listens for messages."""
    
    def __init__(self, host: str, port: int, username: str, password: str, notifier: DiscordNotifier):
        self.host = host
        self.port = port
        self.username = username.upper() # call sign has to be in upper case
        self.password = password
        self.notifier = notifier

    def message_builder(self, payload: dict) -> str:
        """
        Builds a Discord message string from the given payload.
        
        - The base message includes the spotter, callsign, frequency, mode and a relative timestamp.
        - If the source is 'sotawatch', the message is prefixed with a mountain emoji (🏔️)
          and includes the summit name.
        - If the source is 'pota', the message is prefixed with a tree emoji (🌳) and includes
          the park name and reference if available.
        - Note that POTA uses the wwff as its event metadata.
        """
        # Build the basic message.
        message = (
            f" spotted: **{payload['fullCallsign']}** "
            f"on {payload['frequency']} {payload['mode']} <t:{int(time.time())}:R>"
        )

        # SOTA handling.
        if payload.get('source') == 'sotawatch':
            message = f"🏔️ SOTA " + message
            if 'summitName' in payload:
                message += f"\nSummit: {payload['summitName']}"
        # POTA handling.
        elif payload.get('source') == 'pota':
            message = f"🌳 POTA " + message
            if 'wwffName' in payload and 'wwffRef' in payload:
                message += f"\nPark:{payload['wwffRef']}  {payload['wwffName']}"
                message += f"\n<https://pota.app/#/park/{payload['wwffRef']}>"
        return message

    def initialize_connection(self, tn: telnetlib.Telnet) -> bool:
        """
        Performs the handshake with the Telnet server:
          - Waits for greeting messages
          - Sets the connection to JSON mode.
        Returns True if initialization is successful.
        """
        initialized = False
        while not initialized:
            data = tn.read_until(b"\n", timeout=30).decode("utf-8").strip()
            logging.info("Handshake received: %s", data)
            if data == f"Hello {self.username}, this is HamAlert":
                continue
            if data == f"{self.username} de HamAlert >":
                logging.info("Telnet connected, setting JSON mode.")
                time.sleep(1)
                tn.write(b"set/json\n")
                continue
            if data == "Operation successful":
                logging.info("Successfully set JSON mode")
                initialized = True
        return initialized

    def process_data(self, data: str) -> None:
        """
        Processes received data. If it is valid JSON with required fields,
        uses the message_builder to format a message; otherwise, sends the raw message.
        """
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError:
            self.notifier.send_message(data)
            return

        required_fields = {'fullCallsign', 'callsign', 'frequency', 'mode', 'spotter', 'time', 'source'}
        if not all(key in data_dict for key in required_fields):
            logging.warning("Received data in unexpected format: %s", data_dict)
            return

        message = self.message_builder(data_dict)
        self.notifier.send_message(message)

    def run(self) -> None:
        """Establishes the Telnet connection and continuously processes incoming data."""
        try:
            with telnetlib.Telnet(self.host, self.port) as tn:
                # Login
                tn.read_until(b"login: ")
                tn.write(self.username.encode("utf-8") + b"\n")
                tn.read_until(b"password: ")
                tn.write(self.password.encode("utf-8") + b"\n")
                
                # Perform handshake and initialize JSON mode.
                if not self.initialize_connection(tn):
                    logging.error("Failed to initialize connection.")
                    return

                # Main loop: read and process incoming data.
                while True:
                    data = tn.read_until(b"\n", timeout=30).decode("utf-8").strip()
                    if not data:
                        logging.debug("Timeout hit, sending keepalive.")
                        tn.sock.sendall(telnetlib.IAC + telnetlib.NOP)
                        continue
                    logging.info("Received data: %s", data)
                    self.process_data(data)

        except ConnectionRefusedError:
            logging.error("Telnet connection refused. Ensure the server is running and reachable.")
        except Exception as e:
            logging.error("An error occurred: %s", e)


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments with environment variable fallbacks."""
    parser = argparse.ArgumentParser(
        description="HamAlert Telnet to Discord webhook listener."
    )
    parser.add_argument(
        '--log-level',
        help='Logging level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO'
    )
    parser.add_argument('--username', default=os.getenv('USERNAME', ''), help="Telnet username")  # must be capital letters
    parser.add_argument('--password', default=os.getenv('PASSWORD', ''), help="Telnet password")
    parser.add_argument('--webhook', default=os.getenv('WEBHOOK_URL', ''), help="Discord webhook URL")
    parser.add_argument('--host', default='hamalert.org', help="Telnet server host")
    parser.add_argument('--port', type=int, default=7300, help="Telnet server port")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    logging.basicConfig(level=args.log_level, format='%(asctime)s [%(levelname)s] %(message)s')

    if not args.username or not args.password or not args.webhook:
        logging.error("Username, password, and webhook URL must be provided via command-line or environment variables.")
        exit(1)

    notifier = DiscordNotifier(args.webhook)
    listener = TelnetListener(args.host, args.port, args.username, args.password, notifier)
    listener.run()


if __name__ == "__main__":
    main()
