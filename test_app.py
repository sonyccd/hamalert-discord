import json
import time
import unittest
from unittest.mock import MagicMock, patch

# Import the classes from your main application file (adjust the module name as needed)
from app import DiscordNotifier, TelnetListener

# A fake Telnet class to simulate the Telnet connection and handshake.
class FakeTelnet:
    def __init__(self, responses):
        self.responses = responses  # List of responses to simulate
        self.index = 0
        self.last_written = None
        # Create a fake socket with a sendall method.
        self.sock = MagicMock()

    def read_until(self, match, timeout=30):
        if self.index < len(self.responses):
            # Simulate a response (each response should be a string).
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
        # Simulate a successful post (HTTP 204 No Content).
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
        # Simulate a failure (e.g. HTTP 500).
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        self.notifier.send_message("Test message")
        mock_post.assert_called_once()


class TestTelnetListener(unittest.TestCase):
    def setUp(self):
        # Username must be capital letters (per the comment in parse_arguments).
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

    def test_process_data_valid_json_without_sota(self):
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        data_dict = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "TestSource"
        }
        json_data = json.dumps(data_dict)
        listener.process_data(json_data)
        self.notifier.send_message.assert_called_once()
        sent_message = self.notifier.send_message.call_args[0][0]
        self.assertIn("Spotted", sent_message)
        self.assertIn(data_dict["fullCallsign"], sent_message)
        self.assertIn(data_dict["frequency"], sent_message)
        # Without SOTA fields, the message should not be prefixed with "SOTA"
        self.assertFalse(sent_message.startswith("SOTA"))

    def test_process_data_valid_json_with_sota(self):
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        data_dict = {
            "fullCallsign": "K1ABC",
            "callsign": "K1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "spotter": "Spotter1",
            "time": "123456",
            "source": "TestSource",
            "summitName": "Mount Test",
            "summitRef": "MT-001",
            "summitPoints": "10",
            "summitHeight": "1000"
        }
        json_data = json.dumps(data_dict)
        listener.process_data(json_data)
        self.notifier.send_message.assert_called_once()
        sent_message = self.notifier.send_message.call_args[0][0]
        # The message should be prefixed with "SOTA " when SOTA fields are present.
        self.assertTrue(sent_message.startswith("SOTA Spotted"))
        self.assertIn("Mount Test", sent_message)

    def test_initialize_connection(self):
        # Simulate handshake responses.
        responses = [
            f"Hello {self.username}, this is HamAlert",
            f"{self.username} de HamAlert >",
            "Operation successful"
        ]
        fake_telnet = FakeTelnet(responses)
        listener = TelnetListener("fakehost", 1234, self.username, self.password, self.notifier)
        result = listener.initialize_connection(fake_telnet)
        self.assertTrue(result)
        # Verify that the "set/json\n" command was sent.
        self.assertEqual(fake_telnet.last_written, b"set/json\n")


if __name__ == "__main__":
    unittest.main()
