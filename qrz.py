"""QRZ.com API integration for callsign lookups."""
import logging
import time
import xml.etree.ElementTree as ET
from typing import Dict, Optional, NamedTuple
from urllib.parse import urlencode

import requests

from utils import exponential_backoff


class CallsignInfo(NamedTuple):
    """Callsign information from QRZ."""
    callsign: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Get display name for the callsign."""
        if self.first_name:
            return f"{self.callsign} ({self.first_name})"
        return self.callsign

    @property
    def qrz_url(self) -> str:
        """Get QRZ.com URL for the callsign."""
        return f"https://www.qrz.com/db/{self.callsign}"


class QRZClient:
    """Client for QRZ.com XML API."""

    BASE_URL = "https://xmldata.qrz.com/xml/current/"
    SESSION_TIMEOUT = 3600  # 1 hour
    CACHE_TIMEOUT = 86400   # 24 hours

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize QRZ client.

        Args:
            username: QRZ username (optional for basic functionality)
            password: QRZ password (optional for basic functionality)
        """
        self.username = username
        self.password = password
        self.session_key: Optional[str] = None
        self.session_expires: float = 0
        self._cache: Dict[str, tuple[CallsignInfo, float]] = {}

    def _is_session_valid(self) -> bool:
        """Check if current session is still valid."""
        return (self.session_key is not None and
                time.time() < self.session_expires)

    @exponential_backoff(max_retries=3, initial_delay=1, max_delay=10)
    def _authenticate(self) -> bool:
        """
        Authenticate with QRZ and get session key.

        Returns:
            True if authentication successful, False otherwise
        """
        if not self.username or not self.password:
            logging.debug("No QRZ credentials provided, using fallback mode")
            return False

        params = {
            'username': self.username,
            'password': self.password,
            'agent': 'hamalert-discord-1.0'
        }

        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            root = ET.fromstring(response.text)
            session_elem = root.find('.//Key')

            if session_elem is not None:
                self.session_key = session_elem.text
                self.session_expires = time.time() + self.SESSION_TIMEOUT
                logging.info("QRZ authentication successful")
                return True
            else:
                error_elem = root.find('.//Error')
                error_msg = error_elem.text if error_elem is not None else "Unknown error"
                logging.error("QRZ authentication failed: %s", error_msg)
                return False

        except Exception as e:
            logging.error("QRZ authentication error: %s", e)
            return False

    def _get_from_cache(self, callsign: str) -> Optional[CallsignInfo]:
        """Get callsign info from cache if available and not expired."""
        if callsign in self._cache:
            info, cached_time = self._cache[callsign]
            if time.time() - cached_time < self.CACHE_TIMEOUT:
                logging.debug("Using cached QRZ data for %s", callsign)
                return info
            else:
                # Remove expired entry
                del self._cache[callsign]
        return None

    def _cache_result(self, callsign: str, info: CallsignInfo) -> None:
        """Cache callsign info."""
        self._cache[callsign] = (info, time.time())

        # Simple cache cleanup - remove oldest entries if cache gets too large
        if len(self._cache) > 1000:
            oldest = min(self._cache.items(), key=lambda x: x[1][1])
            del self._cache[oldest[0]]

    @exponential_backoff(max_retries=2, initial_delay=1, max_delay=5)
    def _lookup_callsign_api(self, callsign: str) -> Optional[CallsignInfo]:
        """
        Look up callsign using QRZ XML API.

        Args:
            callsign: Amateur radio callsign to look up

        Returns:
            CallsignInfo if found, None otherwise
        """
        # Ensure we have a valid session
        if not self._is_session_valid() and not self._authenticate():
            return None

        params = {
            's': self.session_key,
            'callsign': callsign.upper()
        }

        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            root = ET.fromstring(response.text)

            # Check for session expiry
            session_elem = root.find('.//Session')
            if session_elem is not None:
                error_elem = session_elem.find('Error')
                if error_elem is not None and 'Session Timeout' in error_elem.text:
                    logging.debug("QRZ session expired, re-authenticating")
                    self.session_key = None
                    if self._authenticate():
                        return self._lookup_callsign_api(callsign)  # Retry once
                    return None

            # Parse callsign data
            callsign_elem = root.find('.//Callsign')
            if callsign_elem is not None:
                first_name = None
                last_name = None

                fname_elem = callsign_elem.find('fname')
                if fname_elem is not None:
                    first_name = fname_elem.text

                name_elem = callsign_elem.find('name')
                if name_elem is not None:
                    last_name = name_elem.text

                return CallsignInfo(
                    callsign=callsign.upper(),
                    first_name=first_name,
                    last_name=last_name
                )
            else:
                logging.debug("Callsign %s not found in QRZ database", callsign)
                return None

        except Exception as e:
            logging.error("QRZ API lookup error for %s: %s", callsign, e)
            return None

    def lookup_callsign(self, callsign: str) -> CallsignInfo:
        """
        Look up callsign information.

        Args:
            callsign: Amateur radio callsign to look up

        Returns:
            CallsignInfo with available data
        """
        callsign = callsign.upper()

        # Check cache first
        cached = self._get_from_cache(callsign)
        if cached is not None:
            return cached

        # Try API lookup if credentials available
        if self.username and self.password:
            info = self._lookup_callsign_api(callsign)
            if info is not None:
                self._cache_result(callsign, info)
                return info

        # Fallback: return basic info with just callsign
        fallback_info = CallsignInfo(callsign=callsign)
        self._cache_result(callsign, fallback_info)
        return fallback_info