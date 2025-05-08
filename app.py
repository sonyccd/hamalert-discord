import argparse
import json
import logging
import os
import telnetlib
import time
import threading
import requests


class HeartbeatService:
    """Periodically pings an Uptime Kuma push URL to signal liveness."""

    def __init__(self, url: str, interval: int = 600):
        self.url = url
        self.interval = interval
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        if not self.url:
            logging.warning("No heartbeat URL provided; heartbeat disabled.")
            return
        logging.info("Starting heartbeat service (interval: %ss) → %s", self.interval, self.url)
        self._thread.start()

    def _run(self) -> None:
        while True:
            try:
                resp = requests.get(self.url, timeout=10)
                if resp.ok:
                    logging.debug("Heartbeat ping succeeded.")
                else:
                    logging.warning("Heartbeat ping returned %s", resp.status_code)
            except Exception as e:
                logging.error("Heartbeat ping error: %s", e)
            time.sleep(self.interval)


class DiscordNotifier:
    """Handles sending messages to a Discord webhook."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_message(self, content: str) -> None:
        data = {"content": content}
        headers = {"Content-Type": "application/json"}
        logging.info("Sending Discord message: %s", content)
        resp = requests.post(self.webhook_url, json=data, headers=headers)
        if resp.status_code != 204:
            logging.error("Discord webhook failed (%s)", resp.status_code)


class TelnetListener:
    """Connects to a Telnet server, switches to JSON mode, and forwards spots to Discord."""
    
    def __init__(self, host: str, port: int, username: str, password: str, notifier: DiscordNotifier):
        self.host = host
        self.port = port
        self.username = username.upper()
        self.password = password
        self.notifier = notifier

    def message_builder(self, payload: dict) -> str:
        msg = (
            f" spotted: **{payload['fullCallsign']}** "
            f"on {payload['frequency']} {payload['mode']} <t:{int(time.time())}:R>"
        )
        if payload.get('source') == 'sotawatch':
            msg = f"🏔️ SOTA " + msg
            if summit := payload.get('summitName'):
                msg += f"\nSummit: {summit}"
        elif payload.get('source') == 'pota':
            msg = f"🌳 POTA " + msg
            if ref := payload.get('wwffRef'):
                name = payload.get('wwffName', '')
                msg += f"\nPark:{ref} {name}\n<https://pota.app/#/park/{ref}>"
        return msg

    def initialize_connection(self, tn: telnetlib.Telnet) -> bool:
        initialized = False
        while not initialized:
            line = tn.read_until(b"\n", timeout=30).decode().strip()
            logging.info("Handshake: %s", line)
            if line.endswith("HamAlert"):
                continue
            if line.endswith(">"):
                tn.write(b"set/json\n")
                continue
            if line == "Operation successful":
                initialized = True
        return initialized

    def process_data(self, data: str) -> None:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return self.notifier.send_message(data)

        required = {'fullCallsign','callsign','frequency','mode','spotter','time','source'}
        if required.issubset(payload):
            self.notifier.send_message(self.message_builder(payload))
        else:
            logging.warning("Unexpected payload: %s", payload)

    def run(self) -> None:
        backoff, max_backoff = 1, 60
        while True:
            try:
                logging.info("Connecting to %s:%s", self.host, self.port)
                with telnetlib.Telnet(self.host, self.port) as tn:
                    backoff = 1
                    tn.read_until(b"login: ")
                    tn.write(self.username.encode() + b"\n")
                    tn.read_until(b"password: ")
                    tn.write(self.password.encode() + b"\n")
                    if not self.initialize_connection(tn):
                        logging.error("Init failed.")
                        return
                    while True:
                        line = tn.read_until(b"\n", timeout=30).decode().strip()
                        if not line:
                            tn.sock.sendall(telnetlib.IAC + telnetlib.NOP)
                            continue
                        logging.info("Received: %s", line)
                        self.process_data(line)
            except Exception as e:
                logging.error("Listener error: %s", e)
            time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


def parse_arguments():
    p = argparse.ArgumentParser(description="HamAlert → Discord with heartbeat")
    p.add_argument("--username",   default=os.getenv("USERNAME", ""))
    p.add_argument("--password",   default=os.getenv("PASSWORD", ""))
    p.add_argument("--webhook",    default=os.getenv("WEBHOOK_URL", ""))
    p.add_argument("--host",       default="hamalert.org")
    p.add_argument("--port",  type=int, default=7300)
    p.add_argument("--heartbeat-url",      default=os.getenv("UPTIMEKUMA_URL", ""))
    p.add_argument("--heartbeat-interval", type=int, default=int(os.getenv("HEARTBEAT_INTERVAL", "300")))
    p.add_argument("--log-level", choices=["DEBUG","INFO","WARNING","ERROR"], default="INFO")
    return p.parse_args()


def main():
    args = parse_arguments()
    logging.basicConfig(level=args.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    if not (args.username and args.password and args.webhook):
        logging.error("Require username, password, and webhook.")
        return

    # Start heartbeat independently
    hb = HeartbeatService(args.heartbeat_url, args.heartbeat_interval)
    hb.start()

    # Then start whatever workers you like
    notifier = DiscordNotifier(args.webhook)
    listener = TelnetListener(args.host, args.port, args.username, args.password, notifier)
    listener.run()


if __name__ == "__main__":
    main()
