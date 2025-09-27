"""Tests for message formatters with QRZ integration."""
import unittest
from unittest.mock import MagicMock

from formatters import SpotFormatter
from qrz import QRZClient, CallsignInfo


class TestSpotFormatterQRZ(unittest.TestCase):
    """Test SpotFormatter with QRZ integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_qrz = MagicMock(spec=QRZClient)
        self.formatter = SpotFormatter(self.mock_qrz)

    def test_callsign_suffix_stripping(self):
        """Test that callsign suffixes are properly stripped for QRZ lookup."""
        test_cases = [
            ("K1ABC", "K1ABC"),      # No suffix
            ("K1ABC/P", "K1ABC"),    # Portable
            ("K1ABC/M", "K1ABC"),    # Mobile
            ("K1ABC/MM", "K1ABC"),   # Maritime mobile
            ("VE3XYZ/W1", "VE3XYZ"), # District indicator
            ("W1AW/4", "W1AW"),      # Operating in different district
        ]

        for full_callsign, expected_base in test_cases:
            with self.subTest(callsign=full_callsign):
                # Mock QRZ response
                mock_info = CallsignInfo(callsign=expected_base, first_name="Test")
                self.mock_qrz.lookup_callsign.return_value = mock_info

                # Format the callsign
                result = self.formatter._format_callsign(full_callsign)

                # Verify QRZ lookup was called with base callsign
                self.mock_qrz.lookup_callsign.assert_called_with(expected_base)

                # Verify formatted result contains full callsign but QRZ link uses base
                self.assertIn(f"[{full_callsign}]", result)
                self.assertIn(f"qrz.com/db/{expected_base}", result)
                self.assertIn("(Test)", result)

    def test_qrz_link_generation(self):
        """Test QRZ link generation."""
        mock_info = CallsignInfo(callsign="K1ABC", first_name="John", last_name="Doe")
        self.mock_qrz.lookup_callsign.return_value = mock_info

        result = self.formatter._format_callsign("K1ABC")

        # Check all components are present
        self.assertIn("**[K1ABC](https://www.qrz.com/db/K1ABC)**", result)
        self.assertIn("(John)", result)

    def test_qrz_no_first_name(self):
        """Test formatting when QRZ has no first name."""
        mock_info = CallsignInfo(callsign="K1ABC", first_name=None, last_name="Doe")
        self.mock_qrz.lookup_callsign.return_value = mock_info

        result = self.formatter._format_callsign("K1ABC")

        # Should not include parentheses for first name, but will have QRZ link parentheses
        self.assertIn("**[K1ABC](https://www.qrz.com/db/K1ABC)**", result)
        # Should not include name in parentheses
        self.assertNotIn("(John)", result)
        self.assertNotIn("(Doe)", result)

    def test_spot_formatting_with_qrz(self):
        """Test complete spot formatting with QRZ integration."""
        # Mock QRZ response
        mock_info = CallsignInfo(callsign="W1ABC", first_name="Alice")
        self.mock_qrz.lookup_callsign.return_value = mock_info

        # Test SOTA spot
        sota_payload = {
            "fullCallsign": "W1ABC/P",
            "callsign": "W1ABC",
            "frequency": "14.074",
            "mode": "FT8",
            "spotter": "K1XYZ",
            "time": "1234567890",
            "source": "sotawatch",
            "summitName": "Mount Test W1/NH-001"
        }

        result = self.formatter.format_spot(sota_payload)

        # Verify SOTA formatting with QRZ integration
        self.assertIn("🏔️ SOTA spotted:", result)
        self.assertIn("[W1ABC/P]", result)
        self.assertIn("qrz.com/db/W1ABC", result)
        self.assertIn("(Alice)", result)
        self.assertIn("Mount Test", result)

    def test_qrz_client_none(self):
        """Test formatter behavior when QRZ client is None."""
        formatter = SpotFormatter(None)

        # Should create default QRZ client
        self.assertIsNotNone(formatter.qrz_client)
        self.assertIsInstance(formatter.qrz_client, QRZClient)

    def test_formatter_without_qrz_client(self):
        """Test formatter initialization without QRZ client."""
        formatter = SpotFormatter()

        # Should create default QRZ client
        self.assertIsNotNone(formatter.qrz_client)
        self.assertIsInstance(formatter.qrz_client, QRZClient)


if __name__ == "__main__":
    unittest.main()