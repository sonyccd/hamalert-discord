"""Message formatting for different spot types."""
import time
from typing import Dict, Any


class SpotFormatter:
    """Formats spot messages for Discord."""
    
    SOTA_EMOJI = "🏔️"
    POTA_EMOJI = "🌳"
    
    @staticmethod
    def format_spot(payload: Dict[str, Any]) -> str:
        """
        Format a spot payload into a Discord message.
        
        Args:
            payload: Spot data from HamAlert
            
        Returns:
            Formatted Discord message
        """
        source = payload.get('source', '')
        
        if source == 'sotawatch':
            return SpotFormatter._format_sota(payload)
        elif source == 'pota':
            return SpotFormatter._format_pota(payload)
        else:
            return SpotFormatter._format_generic(payload)
    
    @staticmethod
    def _format_generic(payload: Dict[str, Any]) -> str:
        """Format a generic spot message."""
        return (
            f" spotted: **{payload['fullCallsign']}** "
            f"on {payload['frequency']} {payload['mode']} "
            f"<t:{int(time.time())}:R>"
        )
    
    @staticmethod
    def _format_sota(payload: Dict[str, Any]) -> str:
        """Format a SOTA spot message."""
        msg = (
            f"{SpotFormatter.SOTA_EMOJI} SOTA spotted: **{payload['fullCallsign']}** "
            f"on {payload['frequency']} {payload['mode']} "
            f"<t:{int(time.time())}:R>"
        )
        
        if summit := payload.get('summitName'):
            msg += f"\nSummit: {summit}"
        
        return msg
    
    @staticmethod
    def _format_pota(payload: Dict[str, Any]) -> str:
        """Format a POTA spot message."""
        msg = (
            f"{SpotFormatter.POTA_EMOJI} POTA spotted: **{payload['fullCallsign']}** "
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