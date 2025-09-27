"""Integration tests for the complete HamAlert Discord bot flow."""
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
import time

from app import main, TelnetListener, DiscordNotifier, HeartbeatService
from config import Config
from qrz import QRZClient, CallsignInfo


class TestEndToEndFlow(unittest.TestCase):
    """Test complete end-to-end functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config_data = {
            'username': 'TESTUSER',
            'password': 'testpass',
            'webhook_url': 'http://test-webhook',
            'qrz_username': 'qrzuser',
            'qrz_password': 'qrzpass',
            'heartbeat_url': 'http://heartbeat',
            'heartbeat_interval': 1
        }

    @patch('app.Config.from_args')
    @patch('app.TelnetListener')
    @patch('app.DiscordNotifier')
    @patch('app.HeartbeatService')
    @patch('app.QRZClient')
    @patch('app.setup_logging')
    def test_main_function_initialization(self, mock_logging, mock_qrz_class,
                                        mock_heartbeat_class, mock_notifier_class,
                                        mock_listener_class, mock_config):
        """Test main function initializes all components correctly."""
        # Mock config
        config = Config(**self.config_data)
        mock_config.return_value = config

        # Mock components
        mock_qrz = MagicMock(spec=QRZClient)
        mock_qrz_class.return_value = mock_qrz

        mock_notifier = MagicMock(spec=DiscordNotifier)
        mock_notifier_class.return_value = mock_notifier

        mock_listener = MagicMock(spec=TelnetListener)
        mock_listener_class.return_value = mock_listener

        mock_heartbeat = MagicMock(spec=HeartbeatService)
        mock_heartbeat_class.return_value = mock_heartbeat

        # Mock listener.run() to avoid blocking
        mock_listener.run.side_effect = KeyboardInterrupt()

        try:
            main()
        except KeyboardInterrupt:
            pass

        # Verify initialization
        mock_qrz_class.assert_called_once_with('qrzuser', 'qrzpass')
        mock_notifier_class.assert_called_once_with('http://test-webhook', mock_qrz)
        mock_listener_class.assert_called_once_with(
            'hamalert.org', 7300, 'TESTUSER', 'testpass', mock_notifier
        )
        mock_heartbeat_class.assert_called_once_with(
            'http://heartbeat', 1, check_callback=mock_listener.is_connected
        )
        mock_heartbeat.start.assert_called_once()
        mock_listener.run.assert_called_once()


class TestMessageFlowIntegration(unittest.TestCase):
    """Test complete message flow from HamAlert to Discord."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_qrz = MagicMock(spec=QRZClient)
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            self.notifier = DiscordNotifier("http://test-webhook", self.mock_qrz)
        self.listener = TelnetListener("test.host", 1234, "TESTUSER", "testpass", self.notifier)

    @patch('app.requests.post')
    def test_complete_sota_spot_flow(self, mock_post):
        """Test complete flow for SOTA spot processing."""
        # Mock successful Discord response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        # Mock QRZ lookup
        qrz_info = CallsignInfo(callsign="W1ABC", first_name="John", last_name="Doe")
        self.mock_qrz.lookup_callsign.return_value = qrz_info

        # Test SOTA spot payload
        sota_payload = {
            "fullCallsign": "W1ABC/P",
            "callsign": "W1ABC",
            "frequency": "14.074",
            "mode": "FT8",
            "spotter": "K1XYZ",
            "time": str(int(time.time())),
            "source": "sotawatch",
            "summitName": "Mount Washington W1/NH-001"
        }

        # Process the spot
        json_data = json.dumps(sota_payload)
        self.listener.process_data(json_data)

        # Verify QRZ lookup was called
        self.mock_qrz.lookup_callsign.assert_called_with("W1ABC")

        # Verify Discord webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check webhook URL
        self.assertEqual(call_args[0][0], "http://test-webhook")

        # Check message content
        sent_content = call_args[1]["json"]["content"]
        self.assertIn("🏔️ SOTA spotted:", sent_content)
        self.assertIn("[W1ABC/P]", sent_content)
        self.assertIn("qrz.com/db/W1ABC", sent_content)
        self.assertIn("(John)", sent_content)
        self.assertIn("Mount Washington", sent_content)

    @patch('app.requests.post')
    def test_complete_pota_spot_flow(self, mock_post):
        """Test complete flow for POTA spot processing."""
        # Mock successful Discord response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        # Mock QRZ lookup
        qrz_info = CallsignInfo(callsign="K4XYZ", first_name="Sarah")
        self.mock_qrz.lookup_callsign.return_value = qrz_info

        # Test POTA spot payload
        pota_payload = {
            "fullCallsign": "K4XYZ",
            "callsign": "K4XYZ",
            "frequency": "7.032",
            "mode": "CW",
            "spotter": "W1ABC",
            "time": str(int(time.time())),
            "source": "pota",
            "wwffRef": "K-0123",
            "wwffName": "Great Smoky Mountains National Park"
        }

        # Process the spot
        json_data = json.dumps(pota_payload)
        self.listener.process_data(json_data)

        # Verify QRZ lookup was called
        self.mock_qrz.lookup_callsign.assert_called_with("K4XYZ")

        # Verify Discord webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        sent_content = call_args[1]["json"]["content"]
        self.assertIn("🌳 POTA spotted:", sent_content)
        self.assertIn("[K4XYZ]", sent_content)
        self.assertIn("qrz.com/db/K4XYZ", sent_content)
        self.assertIn("(Sarah)", sent_content)
        self.assertIn("K-0123", sent_content)
        self.assertIn("pota.app/#/park/K-0123", sent_content)

    @patch('app.requests.post')
    def test_qrz_fallback_without_credentials(self, mock_post):
        """Test fallback behavior when QRZ credentials are not available."""
        # Create notifier with QRZ client without credentials
        qrz_client = QRZClient()  # No credentials
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            notifier = DiscordNotifier("http://test-webhook", qrz_client)

        listener = TelnetListener("test.host", 1234, "TESTUSER", "testpass", notifier)

        # Mock successful Discord response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        # Test generic spot payload
        generic_payload = {
            "fullCallsign": "VK2DEF",
            "callsign": "VK2DEF",
            "frequency": "21.074",
            "mode": "FT8",
            "spotter": "W1ABC",
            "time": str(int(time.time())),
            "source": "dxcluster"
        }

        # Process the spot
        json_data = json.dumps(generic_payload)
        listener.process_data(json_data)

        # Verify Discord webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        sent_content = call_args[1]["json"]["content"]
        self.assertIn("spotted: **[VK2DEF]", sent_content)
        self.assertIn("qrz.com/db/VK2DEF", sent_content)
        # Should not have first name since no QRZ credentials
        # Check that there's no " (FirstName)" pattern after the callsign
        self.assertNotIn("** (", sent_content)

    def test_invalid_json_handling(self):
        """Test handling of invalid JSON data."""
        # Mock the notifier's send_message method
        self.notifier.send_message = Mock(return_value=True)

        # Send invalid JSON
        invalid_data = "This is not JSON data"
        self.listener.process_data(invalid_data)

        # Should send raw message to Discord
        self.notifier.send_message.assert_called_once_with(invalid_data)

    def test_incomplete_spot_payload(self):
        """Test handling of incomplete spot payloads."""
        # Mock the notifier's send_message method
        self.notifier.send_message = Mock(return_value=True)
        self.notifier.send_spot = Mock(return_value=True)

        # Create incomplete payload (missing required fields)
        incomplete_payload = {
            "fullCallsign": "W1ABC",
            "frequency": "14.074"
            # Missing other required fields
        }

        # Process the incomplete spot
        json_data = json.dumps(incomplete_payload)
        self.listener.process_data(json_data)

        # Should not process as spot due to validation failure
        self.notifier.send_spot.assert_not_called()


class TestHeartbeatIntegration(unittest.TestCase):
    """Test heartbeat service integration with connection status."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_qrz = MagicMock(spec=QRZClient)
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            self.notifier = DiscordNotifier("http://test-webhook", self.mock_qrz)
        self.listener = TelnetListener("test.host", 1234, "TESTUSER", "testpass", self.notifier)

    @patch('app.requests.get')
    def test_heartbeat_integration_with_connection_status(self, mock_get):
        """Test heartbeat service respects connection status."""
        # Mock successful heartbeat response
        mock_response = Mock()
        mock_response.ok = True
        mock_get.return_value = mock_response

        # Create heartbeat service with connection check
        heartbeat = HeartbeatService(
            url="http://heartbeat",
            interval=0.1,  # Very short interval for testing
            check_callback=self.listener.is_connected
        )

        # Start heartbeat service
        heartbeat.start()

        try:
            # Initially not connected - no heartbeat should be sent
            time.sleep(0.2)
            mock_get.assert_not_called()

            # Simulate connection
            self.listener._running = True
            self.listener._connected = True

            # Now heartbeat should be sent
            time.sleep(0.2)
            mock_get.assert_called()

            # Simulate disconnection
            self.listener._connected = False
            mock_get.reset_mock()

            # Heartbeat should stop
            time.sleep(0.2)
            mock_get.assert_not_called()

        finally:
            heartbeat.stop()

    @patch('app.requests.get')
    def test_heartbeat_error_handling(self, mock_get):
        """Test heartbeat service handles errors gracefully."""
        # Mock heartbeat request to raise exception
        mock_get.side_effect = Exception("Network error")

        heartbeat = HeartbeatService(
            url="http://heartbeat",
            interval=0.1,
            check_callback=lambda: True  # Always healthy
        )

        # Should not raise exception
        heartbeat.start()

        try:
            time.sleep(0.2)
            # Should have attempted the request despite error
            mock_get.assert_called()
        finally:
            heartbeat.stop()


class TestConfigurationIntegration(unittest.TestCase):
    """Test configuration integration across components."""

    def test_config_propagation(self):
        """Test that configuration is properly propagated to all components."""
        config_data = {
            'username': 'testuser',
            'password': 'testpass',
            'webhook_url': 'http://webhook',
            'host': 'custom.host',
            'port': 9999,
            'qrz_username': 'qrzuser',
            'qrz_password': 'qrzpass',
            'heartbeat_url': 'http://heartbeat',
            'heartbeat_interval': 600,
            'log_level': 'DEBUG'
        }

        config = Config(**config_data)

        # Test username conversion
        self.assertEqual(config.username, 'TESTUSER')

        # Test QRZ client initialization
        qrz_client = QRZClient(config.qrz_username, config.qrz_password)
        self.assertEqual(qrz_client.username, 'qrzuser')
        self.assertEqual(qrz_client.password, 'qrzpass')

        # Test Discord notifier initialization
        with patch('app.DiscordNotifier._rate_limiter', lambda f: f):
            notifier = DiscordNotifier(config.webhook_url, qrz_client)
            self.assertEqual(notifier.webhook_url, 'http://webhook')

        # Test telnet listener initialization
        listener = TelnetListener(
            config.host, config.port, config.username, config.password, notifier
        )
        self.assertEqual(listener.host, 'custom.host')
        self.assertEqual(listener.port, 9999)
        self.assertEqual(listener.username, 'TESTUSER')

        # Test heartbeat service initialization
        heartbeat = HeartbeatService(
            config.heartbeat_url, config.heartbeat_interval, listener.is_connected
        )
        self.assertEqual(heartbeat.url, 'http://heartbeat')
        self.assertEqual(heartbeat.interval, 600)


if __name__ == "__main__":
    unittest.main()