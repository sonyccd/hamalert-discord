"""Configuration management for HamAlert Discord bot."""
import argparse
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    username: str
    password: str
    webhook_url: str
    host: str = "hamalert.org"
    port: int = 7300
    heartbeat_url: Optional[str] = None
    heartbeat_interval: int = 300
    log_level: str = "INFO"
    qrz_username: Optional[str] = None
    qrz_password: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize configuration."""
        self.username = self.username.upper()
        if not all([self.username, self.password, self.webhook_url]):
            raise ValueError("Username, password, and webhook URL are required")
        
        if self.heartbeat_interval <= 0:
            raise ValueError("Heartbeat interval must be positive")
    
    @classmethod
    def from_args(cls) -> "Config":
        """Create configuration from command line arguments and environment variables.
        
        Maintains backward compatibility with original environment variable names:
        - USERNAME (not HAMALERT_USERNAME)
        - PASSWORD (not HAMALERT_PASSWORD)  
        - WEBHOOK_URL (not HAMALERT_WEBHOOK_URL)
        - UPTIMEKUMA_URL
        - HEARTBEAT_INTERVAL
        """
        parser = argparse.ArgumentParser(
            description="HamAlert to Discord notification service"
        )
        parser.add_argument(
            "--username",
            default=os.getenv("USERNAME", ""),
            help="HamAlert username"
        )
        parser.add_argument(
            "--password",
            default=os.getenv("PASSWORD", ""),
            help="HamAlert password"
        )
        parser.add_argument(
            "--webhook",
            default=os.getenv("WEBHOOK_URL", ""),
            help="Discord webhook URL"
        )
        parser.add_argument(
            "--host",
            default="hamalert.org",
            help="HamAlert server hostname"
        )
        parser.add_argument(
            "--port",
            type=int,
            default=7300,
            help="HamAlert server port"
        )
        parser.add_argument(
            "--heartbeat-url",
            default=os.getenv("UPTIMEKUMA_URL", ""),
            help="Uptime Kuma heartbeat URL"
        )
        parser.add_argument(
            "--heartbeat-interval",
            type=int,
            default=int(os.getenv("HEARTBEAT_INTERVAL", "300")),
            help="Heartbeat interval in seconds"
        )
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default=os.getenv("LOG_LEVEL", "INFO"),
            help="Logging level"
        )
        parser.add_argument(
            "--qrz-username",
            default=os.getenv("QRZ_USERNAME", ""),
            help="QRZ.com username for callsign lookups"
        )
        parser.add_argument(
            "--qrz-password",
            default=os.getenv("QRZ_PASSWORD", ""),
            help="QRZ.com password for callsign lookups"
        )
        
        args = parser.parse_args()
        
        return cls(
            username=args.username,
            password=args.password,
            webhook_url=args.webhook,
            host=args.host,
            port=args.port,
            heartbeat_url=args.heartbeat_url or None,
            heartbeat_interval=args.heartbeat_interval,
            log_level=args.log_level,
            qrz_username=args.qrz_username or None,
            qrz_password=args.qrz_password or None
        )