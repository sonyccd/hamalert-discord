"""Message formatting for different spot types."""
import re
import time
from typing import Dict, Any, Optional

from qrz import QRZClient


class SpotFormatter:
    """Formats spot messages for Discord."""

    SOTA_EMOJI = "🏔️"
    POTA_EMOJI = "🌳"

    def __init__(self, qrz_client: Optional[QRZClient] = None):
        """
        Initialize formatter.

        Args:
            qrz_client: QRZ client for callsign lookups
        """
        self.qrz_client = qrz_client or QRZClient()
    
    def format_spot(self, payload: Dict[str, Any]) -> str:
        """
        Format a spot payload into a Discord message.

        Args:
            payload: Spot data from HamAlert

        Returns:
            Formatted Discord message
        """
        source = payload.get('source', '')

        if source == 'sotawatch':
            return self._format_sota(payload)
        elif source == 'pota':
            return self._format_pota(payload)
        else:
            return self._format_generic(payload)
    
    def _format_callsign(self, callsign: str) -> str:
        """
        Format callsign with QRZ link and name if available.

        Args:
            callsign: Amateur radio callsign

        Returns:
            Formatted callsign string
        """
        # Extract base callsign (remove /P, /M, etc.)
        base_callsign = re.split(r'[/]', callsign)[0]

        # Look up callsign info
        info = self.qrz_client.lookup_callsign(base_callsign)

        # Create formatted callsign with link
        formatted = f"**[{callsign}]({info.qrz_url})**"

        # Add first name if available
        if info.first_name:
            formatted += f" ({info.first_name})"

        return formatted

    def _format_generic(self, payload: Dict[str, Any]) -> str:
        """Format a generic spot message."""
        callsign = self._format_callsign(payload['fullCallsign'])
        return (
            f" spotted: {callsign} "
            f"on {payload['frequency']} {payload['mode']} "
            f"<t:{int(time.time())}:R>"
        )
    
    def _format_sota(self, payload: Dict[str, Any]) -> str:
        """Format a SOTA spot message."""
        callsign = self._format_callsign(payload['fullCallsign'])
        msg = (
            f"{SpotFormatter.SOTA_EMOJI} SOTA spotted: {callsign} "
            f"on {payload['frequency']} {payload['mode']} "
            f"<t:{int(time.time())}:R>"
        )

        if summit := payload.get('summitName'):
            msg += f"\nSummit: {summit}"

        return msg
    
    def _format_pota(self, payload: Dict[str, Any]) -> str:
        """Format a POTA spot message."""
        callsign = self._format_callsign(payload['fullCallsign'])
        msg = (
            f"{SpotFormatter.POTA_EMOJI} POTA spotted: {callsign} "
            f"on {payload['frequency']} {payload['mode']} "
            f"<t:{int(time.time())}:R>"
        )

        if ref := payload.get('wwffRef'):
            name = payload.get('wwffName', '')
            msg += f"\nPark: {ref} {name}"
            msg += f"\n<https://pota.app/#/park/{ref}>"

        return msg


def validate_spot_payload(payload: Dict[str, Any]) -> bool:
    """
    Validate that a payload contains required spot fields.
    
    Args:
        payload: Spot data to validate
        
    Returns:
        True if payload is valid, False otherwise
    """
    required_fields = {
        'fullCallsign',
        'callsign',
        'frequency',
        'mode',
        'spotter',
        'time',
        'source'
    }
    return required_fields.issubset(payload)