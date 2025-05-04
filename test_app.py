import json
import time
import unittest
from unittest.mock import MagicMock, patch

import telnetlib

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

    def test_username_conversion(self):
        """Test that the listener converts a lowercase username to uppercase."""
        lower_username = "testuser"
        listener = TelnetListener("fakehost", 1234, lower_username, self.password, self.notifier)
        self.assertEqual(listener.username, lower_username.upper())

    def test_message_builder_generic(self):
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        payload = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "unknown"
        }
        message = listener.message_builder(payload)
        # Generic message should not be prefixed with SOTA or POTA emojis.
        self.assertFalse(message.startswith("🏔️ SOTA"))
        self.assertFalse(message.startswith("🌳 POTA"))
        # It should contain the basic information.
        self.assertIn("spotted: **K1ABC**", message)
        self.assertIn("on 14.250 SSB", message)

    def test_message_builder_sotawatch(self):
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
        message = listener.message_builder(payload)
        self.assertTrue(message.startswith("🏔️ SOTA"))
        self.assertIn("spotted: **K1ABC**", message)
        self.assertIn("\nSummit: Mount Test", message)

    def test_message_builder_pota(self):
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
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
        message = listener.message_builder(payload)
        self.assertTrue(message.startswith("🌳 POTA"))
        self.assertIn("spotted: **K1XYZ**", message)
        self.assertIn("\nPark:NP-123  National Park", message)
        self.assertIn("\n<https://pota.app/#/park/NP-123>", message)

    def test_process_data_raw_message(self):
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        raw_message = "Non JSON message"
        listener.process_data(raw_message)
        self.notifier.send_message.assert_called_once_with(raw_message)

    def test_process_data_valid_json(self):
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
        expected_message = listener.message_builder(payload)
        sent_message = self.notifier.send_message.call_args[0][0]
        self.assertEqual(expected_message, sent_message)

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
        # Verify that the JSON mode command was sent.
        self.assertEqual(fake_telnet.last_written, b"set/json\n")

    @patch("app.telnetlib.Telnet", side_effect=ConnectionRefusedError("refused"))
    @patch("app.time.sleep", side_effect=lambda s: (_ for _ in ()).throw(SystemExit))
    def test_run_retries_on_connection_refused(self, mock_sleep, mock_telnet_ctor):
        """If Telnet(...) raises ConnectionRefusedError, run() should back off once then retry."""
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        with self.assertRaises(SystemExit):
            listener.run()
        # initial backoff should be 1 second
        mock_sleep.assert_called_once_with(1)

    @patch("app.telnetlib.Telnet")
    @patch("app.time.sleep", lambda s: None)
    def test_run_processes_one_message_and_exits(self, mock_telnet_ctor):
        """Simulate a successful connect + one payload, then break out via SystemExit."""
        # Prepare a valid payload for main loop
        payload = {
            "fullCallsign": "K1FOO",
            "callsign": "K1FOO",
            "frequency": "14.000",
            "mode": "FT8",
            "spotter": "Someone",
            "time": "111111",
            "source": "unknown"
        }
        responses = [
            "login: ",
            "password: ",
            f"Hello {self.username}, this is HamAlert",
            f"{self.username} de HamAlert >",
            "Operation successful",
            json.dumps(payload),
        ]
        fake_telnet = FakeTelnet(responses)
        mock_telnet_ctor.return_value = fake_telnet

        # Subclass to raise SystemExit after processing one message
        class OneShotListener(TelnetListener):
            def process_data(self_inner, data):
                super(OneShotListener, self_inner).process_data(data)
                raise SystemExit

        listener = OneShotListener("fakehost", 1234, self.username, self.password, self.notifier)

        with self.assertRaises(SystemExit):
            listener.run()

        # Verify that our payload was turned into a Discord message
        expected = listener.message_builder(payload)
        self.notifier.send_message.assert_called_once_with(expected)


if __name__ == "__main__":
    unittest.main()
