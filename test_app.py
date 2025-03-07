import json
import time
import unittest
from unittest.mock import MagicMock, patch

from app import DiscordNotifier, TelnetListener

# Helper class to simulate Telnet interactions.
class FakeTelnet:
    def __init__(self, responses):
        self.responses = responses  # List of responses to simulate.
        self.index = 0
        self.last_written = None
        self.sock = MagicMock()  # Fake socket for sending keepalive messages.

    def read_until(self, match, timeout=30):
        if self.index < len(self.responses):
            resp = self.responses[self.index]
            self.index += 1
            return resp.encode("utf-8") + b"\n"
        return b""

    def write(self, data):
        self.last_written = data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class TestDiscordNotifier(unittest.TestCase):
    def setUp(self):
        self.webhook_url = "http://fake-webhook-url"
        self.notifier = DiscordNotifier(self.webhook_url)

    @patch("app.requests.post")
    def test_send_message_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        self.notifier.send_message("Test message")
        mock_post.assert_called_once_with(
            self.webhook_url,
            json={"content": "Test message"},
            headers={"Content-Type": "application/json"}
        )

    @patch("app.requests.post")
    def test_send_message_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        self.notifier.send_message("Test message")
        mock_post.assert_called_once()


class TestTelnetListener(unittest.TestCase):
    def setUp(self):
        self.username = "TESTUSER"
        self.password = "testpass"
        self.webhook_url = "http://fake-webhook-url"
        self.notifier = DiscordNotifier(self.webhook_url)
        # Replace send_message with a MagicMock to capture calls.
        self.notifier.send_message = MagicMock()

    def test_process_data_raw_message(self):
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        raw_message = "Non JSON message"
        listener.process_data(raw_message)
        self.notifier.send_message.assert_called_once_with(raw_message)

    def test_process_data_valid_json_unknown_source(self):
        # Valid JSON with a source other than 'sotawatch' or 'pota'.
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        data_dict = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "unknown"  # Unknown source; no emoji should be added.
        }
        json_data = json.dumps(data_dict)
        listener.process_data(json_data)
        self.notifier.send_message.assert_called_once()
        sent_message = self.notifier.send_message.call_args[0][0]
        # Ensure message does not start with either emoji prefix.
        self.assertFalse(sent_message.startswith("🏔️ SOTA"))
        self.assertFalse(sent_message.startswith("🌳 POTA"))
        self.assertIn("spotted:", sent_message)

    def test_process_data_valid_json_with_sotawatch(self):
        # Valid JSON for SOTA including summitName.
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        data_dict = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "sotawatch",
            "summitName": "Mount Test"
        }
        json_data = json.dumps(data_dict)
        listener.process_data(json_data)
        self.notifier.send_message.assert_called_once()
        sent_message = self.notifier.send_message.call_args[0][0]
        self.assertTrue(sent_message.startswith("🏔️ SOTA"))
        self.assertIn("Summit: Mount Test", sent_message)

    def test_process_data_valid_json_with_pota(self):
        # Valid JSON for POTA.
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        data_dict = {
            "fullCallsign": "K1XYZ",
            "callsign": "K1XYZ",
            "frequency": "7.040",
            "mode": "CW",
            "spotter": "Spotter2",
            "time": "654321",
            "source": "pota"
        }
        json_data = json.dumps(data_dict)
        listener.process_data(json_data)
        self.notifier.send_message.assert_called_once()
        sent_message = self.notifier.send_message.call_args[0][0]
        self.assertTrue(sent_message.startswith("🌳 POTA"))
        self.assertIn("spotted:", sent_message)

    def test_initialize_connection(self):
        responses = [
            f"Hello {self.username}, this is HamAlert",
            f"{self.username} de HamAlert >",
            "Operation successful"
        ]
        fake_telnet = FakeTelnet(responses)
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        result = listener.initialize_connection(fake_telnet)
        self.assertTrue(result)
        # Verify that the listener sent the JSON mode command.
        self.assertEqual(fake_telnet.last_written, b"set/json\n")


if __name__ == "__main__":
    unittest.main()
