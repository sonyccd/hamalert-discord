"""Tests for improved connection handling and authentication."""
import unittest
from unittest.mock import Mock, patch, MagicMock
import telnetlib

from app import TelnetListener, DiscordNotifier
from qrz import QRZClient


class MockTelnet:
    """Mock telnet connection for testing."""

    def __init__(self, responses=None, immediate_response=b""):
        self.responses = responses or []
        self.response_index = 0
        self.immediate_response = immediate_response
        self.written_data = []
        self.sock = MagicMock()

    def read_until(self, delimiter, timeout=30):
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response
        return b""

    def read_very_eager(self):
        response = self.immediate_response
        self.immediate_response = b""  # Only return once
        return response

    def write(self, data):
        self.written_data.append(data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestConnectionHandling(unittest.TestCase):
    """Test connection handling improvements."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_qrz = MagicMock(spec=QRZClient)
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            self.notifier = DiscordNotifier("http://webhook", self.mock_qrz)
        self.listener = TelnetListener("test.host", 1234, "TESTUSER", "testpass", self.notifier)

    def test_successful_authentication_immediate_response(self):
        """Test successful authentication with immediate command prompt."""
        # Mock immediate response with successful login and command prompt
        immediate_response = b"Hello TESTUSER, this is HamAlert\r\nTESTUSER de HamAlert >"
        mock_telnet = MockTelnet(
            responses=[b"Operation successful\r\n"],
            immediate_response=immediate_response
        )

        result = self.listener.initialize_connection(mock_telnet)

        self.assertTrue(result)
        self.assertTrue(self.listener._connected)
        # Should have sent set/json command
        self.assertIn(b"set/json\n", mock_telnet.written_data)

    def test_authentication_failure_immediate_response(self):
        """Test authentication failure detection in immediate response."""
        # Mock immediate response with authentication failure
        immediate_response = b"Login failed, check username and password\r\n"
        mock_telnet = MockTelnet(immediate_response=immediate_response)

        result = self.listener.initialize_connection(mock_telnet)

        self.assertFalse(result)
        self.assertFalse(self.listener._connected)

    def test_traditional_handshake_flow(self):
        """Test traditional handshake flow when no immediate response."""
        mock_telnet = MockTelnet(responses=[
            b"Hello TESTUSER, this is HamAlert\r\n",
            b"TESTUSER de HamAlert >\r\n",
            b"Operation successful\r\n"
        ])

        result = self.listener.initialize_connection(mock_telnet)

        self.assertTrue(result)
        self.assertTrue(self.listener._connected)
        self.assertIn(b"set/json\n", mock_telnet.written_data)

    def test_connection_closed_during_initialization(self):
        """Test handling of connection closed during initialization."""
        mock_telnet = MockTelnet(responses=[b""])  # Empty response indicates closed connection

        result = self.listener.initialize_connection(mock_telnet)

        self.assertFalse(result)
        self.assertFalse(self.listener._connected)

    def test_invalid_credentials_in_response_line(self):
        """Test detection of invalid credentials in response lines."""
        mock_telnet = MockTelnet(responses=[
            b"Invalid username or password\r\n"
        ])

        result = self.listener.initialize_connection(mock_telnet)

        self.assertFalse(result)
        self.assertFalse(self.listener._connected)

    def test_exception_during_initialization(self):
        """Test handling of exceptions during initialization."""
        mock_telnet = MockTelnet()

        # Mock read_very_eager to raise an exception
        mock_telnet.read_very_eager = Mock(side_effect=Exception("Connection error"))

        result = self.listener.initialize_connection(mock_telnet)

        self.assertFalse(result)
        self.assertFalse(self.listener._connected)

    def test_json_mode_failure(self):
        """Test handling when JSON mode command fails."""
        # Mock immediate response with command prompt but JSON mode fails
        immediate_response = b"Hello TESTUSER, this is HamAlert\r\nTESTUSER de HamAlert >"
        mock_telnet = MockTelnet(
            responses=[b"Command not recognized\r\n"],
            immediate_response=immediate_response
        )

        result = self.listener.initialize_connection(mock_telnet)

        # Should attempt JSON mode but fail on response
        self.assertIn(b"set/json\n", mock_telnet.written_data)
        # Since "Operation successful" is not in response, should continue to traditional flow
        # which will eventually timeout or fail

    def test_tcp_connection_failure_simulation(self):
        """Test handling of TCP connection failure (simulation only)."""
        # This test simulates the behavior without actually calling _connect_and_run
        # to avoid infinite retry loops in tests

        # Verify that the method exists and is decorated
        self.assertTrue(hasattr(self.listener, '_connect_and_run'))
        self.assertTrue(hasattr(self.listener._connect_and_run, '__wrapped__'))

    def test_login_timeout_simulation(self):
        """Test handling of login timeout (simulation only)."""
        # This test simulates the behavior without actually calling _connect_and_run
        # to avoid infinite retry loops in tests

        # Test that timeout exceptions would be properly handled
        # by verifying the initialize_connection method behavior
        mock_telnet = MockTelnet()
        mock_telnet.read_until = Mock(side_effect=Exception("Timeout"))

        # This should return False and not crash
        result = self.listener.initialize_connection(mock_telnet)
        self.assertFalse(result)

    def test_connection_status_methods(self):
        """Test connection status tracking methods."""
        # Initially not connected
        self.assertFalse(self.listener.is_connected())

        # Set running but not connected
        self.listener._running = True
        self.assertFalse(self.listener.is_connected())

        # Set connected but not running
        self.listener._running = False
        self.listener._connected = True
        self.assertFalse(self.listener.is_connected())

        # Both running and connected
        self.listener._running = True
        self.listener._connected = True
        self.assertTrue(self.listener.is_connected())

        # Test stop method
        self.listener.stop()
        self.assertFalse(self.listener._running)
        self.assertFalse(self.listener._connected)
        self.assertFalse(self.listener.is_connected())


class TestAuthenticationEdgeCases(unittest.TestCase):
    """Test edge cases in authentication handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_qrz = MagicMock(spec=QRZClient)
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            self.notifier = DiscordNotifier("http://webhook", self.mock_qrz)
        self.listener = TelnetListener("test.host", 1234, "TESTUSER", "testpass", self.notifier)

    def test_case_insensitive_authentication_failure(self):
        """Test case-insensitive detection of authentication failures."""
        test_cases = [
            b"LOGIN FAILED\r\n",
            b"Access Denied\r\n",
            b"Authentication incorrect\r\n",
            b"Invalid credentials\r\n"
        ]

        for failure_message in test_cases:
            with self.subTest(failure_message=failure_message):
                mock_telnet = MockTelnet(immediate_response=failure_message)
                result = self.listener.initialize_connection(mock_telnet)
                self.assertFalse(result)

    def test_partial_command_prompt_detection(self):
        """Test detection of command prompts with various formats."""
        test_prompts = [
            b"TESTUSER de HamAlert >",
            b"TESTUSER@HamAlert >",
            b"> Welcome TESTUSER to HamAlert",
            b"HamAlert> "
        ]

        for prompt in test_prompts:
            with self.subTest(prompt=prompt):
                mock_telnet = MockTelnet(
                    responses=[b"Operation successful\r\n"],
                    immediate_response=prompt
                )
                result = self.listener.initialize_connection(mock_telnet)
                if b"hamalert" in prompt.lower():
                    self.assertTrue(result)
                # Test should verify appropriate handling based on prompt format

    def test_unicode_handling_in_responses(self):
        """Test handling of unicode characters in server responses."""
        # Mock response with unicode characters
        unicode_response = "Hello TESTUSER, this is HamAlert ©\r\nTESTUSER de HamAlert >".encode('utf-8')
        mock_telnet = MockTelnet(
            responses=[b"Operation successful\r\n"],
            immediate_response=unicode_response
        )

        result = self.listener.initialize_connection(mock_telnet)

        self.assertTrue(result)
        self.assertTrue(self.listener._connected)

    def test_empty_immediate_response(self):
        """Test handling when immediate response is empty."""
        mock_telnet = MockTelnet(
            responses=[
                b"Hello TESTUSER, this is HamAlert\r\n",
                b"TESTUSER de HamAlert >\r\n",
                b"Operation successful\r\n"
            ],
            immediate_response=b""
        )

        result = self.listener.initialize_connection(mock_telnet)

        self.assertTrue(result)
        self.assertTrue(self.listener._connected)


if __name__ == "__main__":
    unittest.main()