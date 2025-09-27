"""Tests for HamAlert Discord bot."""
import json
import time
import unittest
from unittest.mock import MagicMock, patch, Mock
from typing import List, Optional

import telnetlib

from app import (
    DiscordNotifier,
    TelnetListener,
    HeartbeatService,
)
from formatters import SpotFormatter, validate_spot_payload
from config import Config
from qrz import QRZClient


# Helper class to simulate Telnet interactions.
class FakeTelnet:
    def __init__(self, responses: List[str]):
        self.responses = responses  # List of responses to simulate.
        self.index = 0
        self.last_written: Optional[bytes] = None
        self.sock = MagicMock()  # Fake socket for sending keepalive messages.

    def read_until(self, match: bytes, timeout: int = 30) -> bytes:
        if self.index < len(self.responses):
            resp = self.responses[self.index]
            self.index += 1
            return resp.encode("utf-8") + b"\n"
        return b""

    def write(self, data: bytes) -> None:
        self.last_written = data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def test_username_uppercase(self):
        """Test that username is converted to uppercase."""
        config = Config(
            username="testuser",
            password="pass",
            webhook_url="http://webhook"
        )
        self.assertEqual(config.username, "TESTUSER")
    
    def test_missing_required_fields(self):
        """Test that missing required fields raise an error."""
        with self.assertRaises(ValueError):
            Config(username="", password="pass", webhook_url="http://webhook")
        
        with self.assertRaises(ValueError):
            Config(username="user", password="", webhook_url="http://webhook")
        
        with self.assertRaises(ValueError):
            Config(username="user", password="pass", webhook_url="")
    
    def test_invalid_heartbeat_interval(self):
        """Test that invalid heartbeat interval raises an error."""
        with self.assertRaises(ValueError):
            Config(
                username="user",
                password="pass",
                webhook_url="http://webhook",
                heartbeat_interval=0
            )


class TestSpotFormatter(unittest.TestCase):
    """Test message formatting."""
    
    def setUp(self):
        # Mock QRZ client to avoid network calls in tests
        mock_qrz = MagicMock(spec=QRZClient)
        self.formatter = SpotFormatter(mock_qrz)
    
    def test_format_generic_spot(self):
        """Test formatting of generic spots."""
        from qrz import CallsignInfo

        # Mock the QRZ lookup to return test data
        mock_info = CallsignInfo(callsign="K1ABC", first_name="John")
        self.formatter.qrz_client.lookup_callsign.return_value = mock_info

        payload = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "unknown"
        }
        message = self.formatter.format_spot(payload)
        self.assertNotIn("🏔️", message)
        self.assertNotIn("🌳", message)
        self.assertIn("spotted: **[John K1ABC]", message)
        self.assertIn("qrz.com/db/K1ABC", message)
        self.assertIn("on 14.250 SSB", message)
    
    def test_format_sota_spot(self):
        """Test formatting of SOTA spots."""
        from qrz import CallsignInfo

        # Mock the QRZ lookup to return test data
        mock_info = CallsignInfo(callsign="K1ABC", first_name="John")
        self.formatter.qrz_client.lookup_callsign.return_value = mock_info

        payload = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "sotawatch",
            "summitName": "Mount Test"
        }
        message = self.formatter.format_spot(payload)
        self.assertIn("🏔️ SOTA", message)
        self.assertIn("spotted: **[John K1ABC]", message)
        self.assertIn("qrz.com/db/K1ABC", message)
        self.assertIn("Summit: Mount Test", message)
    
    def test_format_pota_spot(self):
        """Test formatting of POTA spots."""
        from qrz import CallsignInfo

        # Mock the QRZ lookup to return test data
        mock_info = CallsignInfo(callsign="K1XYZ", first_name="Jane")
        self.formatter.qrz_client.lookup_callsign.return_value = mock_info

        payload = {
            "fullCallsign": "K1XYZ",
            "callsign": "K1XYZ",
            "frequency": "7.040",
            "mode": "CW",
            "spotter": "Spotter2",
            "time": "654321",
            "source": "pota",
            "wwffName": "National Park",
            "wwffRef": "NP-123"
        }
        message = self.formatter.format_spot(payload)
        self.assertIn("🌳 POTA", message)
        self.assertIn("spotted: **[Jane K1XYZ]", message)
        self.assertIn("qrz.com/db/K1XYZ", message)
        self.assertIn("Park: NP-123 [National Park]", message)
        self.assertIn("pota.app/#/park/NP-123", message)
    
    def test_validate_spot_payload(self):
        """Test payload validation."""
        valid_payload = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "unknown"
        }
        self.assertTrue(validate_spot_payload(valid_payload))
        
        # Missing required field
        invalid_payload = {
            "fullCallsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB"
        }
        self.assertFalse(validate_spot_payload(invalid_payload))


class TestDiscordNotifier(unittest.TestCase):
    """Test Discord notification functionality."""
    
    def setUp(self):
        self.webhook_url = "http://fake-webhook-url"
        # Mock QRZ client for tests
        self.mock_qrz = MagicMock(spec=QRZClient)
        # Patch the rate limiter to avoid delays in tests
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            self.notifier = DiscordNotifier(self.webhook_url, self.mock_qrz)

    @patch("app.requests.post")
    def test_send_message_success(self, mock_post):
        """Test successful message sending."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        result = self.notifier.send_message("Test message")
        
        self.assertTrue(result)
        mock_post.assert_called_once_with(
            self.webhook_url,
            json={"content": "Test message"},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

    @patch("app.requests.post")
    def test_send_message_failure(self, mock_post):
        """Test failed message sending."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        result = self.notifier.send_message("Test message")
        
        self.assertFalse(result)
        mock_post.assert_called_once()

    @patch("app.requests.post")
    def test_send_spot(self, mock_post):
        """Test sending a formatted spot."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        
        payload = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "sotawatch"
        }
        
        result = self.notifier.send_spot(payload)
        
        self.assertTrue(result)
        # Check that the formatted message was sent
        call_args = mock_post.call_args
        sent_content = call_args[1]["json"]["content"]
        self.assertIn("🏔️ SOTA", sent_content)
        self.assertIn("K1ABC", sent_content)


class TestTelnetListener(unittest.TestCase):
    """Test Telnet listener functionality."""
    
    def setUp(self):
        self.username = "TESTUSER"
        self.password = "testpass"
        self.webhook_url = "http://fake-webhook-url"
        self.mock_qrz = MagicMock(spec=QRZClient)
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            self.notifier = DiscordNotifier(self.webhook_url, self.mock_qrz)
        # Replace send_message with a MagicMock to capture calls.
        self.notifier.send_message = MagicMock(return_value=True)
        self.notifier.send_spot = MagicMock(return_value=True)

    def test_username_conversion(self):
        """Test that the listener converts a lowercase username to uppercase."""
        lower_username = "testuser"
        listener = TelnetListener("fakehost", 1234, lower_username, self.password, self.notifier)
        self.assertEqual(listener.username, lower_username.upper())

    def test_process_data_raw_message(self):
        """Test processing of non-JSON messages."""
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        raw_message = "Non JSON message"
        listener.process_data(raw_message)
        self.notifier.send_message.assert_called_once_with(raw_message)

    def test_process_data_valid_json(self):
        """Test processing of valid JSON spot data."""
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        payload = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "sotawatch",
            "summitName": "Mount Test"
        }
        json_data = json.dumps(payload)
        listener.process_data(json_data)
        self.notifier.send_spot.assert_called_once_with(payload)

    def test_initialize_connection(self):
        """Test Telnet connection initialization."""
        responses = [
            f"Hello {self.username}, this is HamAlert",
            f"{self.username} de HamAlert >",
            "Operation successful"
        ]
        fake_telnet = FakeTelnet(responses)
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        result = listener.initialize_connection(fake_telnet)
        self.assertTrue(result)
        # Verify that the JSON mode command was sent.
        self.assertEqual(fake_telnet.last_written, b"set/json\n")

    def test_connection_status_tracking(self):
        """Test connection status tracking."""
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)

        # Initially not connected
        self.assertFalse(listener.is_connected())

        # After starting, still not connected until successful initialization
        listener._running = True
        self.assertFalse(listener.is_connected())

        # After successful connection
        listener._connected = True
        self.assertTrue(listener.is_connected())

        # After stopping
        listener.stop()
        self.assertFalse(listener.is_connected())


class TestHeartbeatService(unittest.TestCase):
    """Test heartbeat service functionality."""
    
    @patch("app.logging.warning")
    def test_start_without_url_logs_warning(self, mock_warn):
        """Test that starting without URL logs a warning."""
        svc = HeartbeatService(url=None, interval=1)
        svc.start()
        mock_warn.assert_called_once_with("No heartbeat URL provided; heartbeat disabled.")

    @patch("app.threading.Thread.start")
    @patch("app.logging.info")
    def test_start_with_url_starts_thread(self, mock_info, mock_thread_start):
        """Test that starting with URL starts the thread."""
        svc = HeartbeatService(url="http://hb", interval=1)
        svc.start()
        mock_info.assert_called_with(
            "Starting heartbeat service (interval: %ss) → %s", 
            1, 
            "http://hb"
        )
        mock_thread_start.assert_called_once()

    @patch("app.requests.get")
    def test_run_pings_successfully(self, mock_get):
        """Test successful heartbeat ping."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_get.return_value = mock_response
        
        svc = HeartbeatService(url="http://hb", interval=1)
        svc._running = True
        
        # Run one iteration then stop
        def stop_after_one(interval):
            svc._running = False
            
        with patch("app.time.sleep", side_effect=stop_after_one):
            svc._run()
        
        mock_get.assert_called_once_with("http://hb", timeout=10)

    @patch("app.requests.get")
    def test_heartbeat_with_connection_check_healthy(self, mock_get):
        """Test heartbeat with connection check when service is healthy."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_get.return_value = mock_response

        # Mock connection check that returns True (healthy)
        check_callback = MagicMock(return_value=True)

        svc = HeartbeatService(url="http://hb", interval=1, check_callback=check_callback)
        svc._running = True

        # Run one iteration then stop
        def stop_after_one(interval):
            svc._running = False

        with patch("app.time.sleep", side_effect=stop_after_one):
            svc._run()

        # Should have sent heartbeat because service is healthy
        mock_get.assert_called_once_with("http://hb", timeout=10)
        check_callback.assert_called_once()

    @patch("app.requests.get")
    def test_heartbeat_with_connection_check_unhealthy(self, mock_get):
        """Test heartbeat with connection check when service is unhealthy."""
        # Mock connection check that returns False (unhealthy)
        check_callback = MagicMock(return_value=False)

        svc = HeartbeatService(url="http://hb", interval=1, check_callback=check_callback)
        svc._running = True

        # Run one iteration then stop
        def stop_after_one(interval):
            svc._running = False

        with patch("app.time.sleep", side_effect=stop_after_one):
            svc._run()

        # Should NOT have sent heartbeat because service is unhealthy
        mock_get.assert_not_called()
        check_callback.assert_called_once()


if __name__ == "__main__":
    unittest.main()