"""Tests for QRZ API integration."""
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET

from qrz import QRZClient, CallsignInfo


class TestCallsignInfo(unittest.TestCase):
    """Test CallsignInfo class."""

    def test_display_name_with_first_name(self):
        """Test display name when first name is available."""
        info = CallsignInfo(callsign="K1ABC", first_name="John", last_name="Doe")
        self.assertEqual(info.display_name, "K1ABC (John)")

    def test_display_name_without_first_name(self):
        """Test display name when first name is not available."""
        info = CallsignInfo(callsign="K1ABC", first_name=None, last_name="Doe")
        self.assertEqual(info.display_name, "K1ABC")

    def test_qrz_url(self):
        """Test QRZ URL generation."""
        info = CallsignInfo(callsign="K1ABC")
        self.assertEqual(info.qrz_url, "https://www.qrz.com/db/K1ABC")


class TestQRZClient(unittest.TestCase):
    """Test QRZ client functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = QRZClient("testuser", "testpass")

    def test_init_without_credentials(self):
        """Test initialization without credentials."""
        client = QRZClient()
        self.assertIsNone(client.username)
        self.assertIsNone(client.password)

    def test_is_session_valid(self):
        """Test session validity checking."""
        # No session key
        self.assertFalse(self.client._is_session_valid())

        # Expired session
        self.client.session_key = "test_key"
        self.client.session_expires = time.time() - 100
        self.assertFalse(self.client._is_session_valid())

        # Valid session
        self.client.session_expires = time.time() + 100
        self.assertTrue(self.client._is_session_valid())

    @patch("qrz.requests.get")
    def test_authenticate_success(self, mock_get):
        """Test successful authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Key>test_session_key</Key>
        <Count>1</Count>
        <SubExp>Fri Sep 29 14:13:57 2034</SubExp>
        <GMTime>Sat Sep 27 19:09:23 2025</GMTime>
        <Remark>cpu: 0.094s</Remark>
        </Session>
        </QRZDatabase>"""
        mock_get.return_value = mock_response

        result = self.client._authenticate()

        self.assertTrue(result)
        self.assertEqual(self.client.session_key, "test_session_key")
        self.assertGreater(self.client.session_expires, time.time())

    @patch("qrz.requests.get")
    def test_authenticate_failure(self, mock_get):
        """Test authentication failure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Error>Invalid username/password</Error>
        </Session>
        </QRZDatabase>"""
        mock_get.return_value = mock_response

        result = self.client._authenticate()

        self.assertFalse(result)
        self.assertIsNone(self.client.session_key)

    @patch("qrz.requests.get")
    def test_authenticate_no_credentials(self, mock_get):
        """Test authentication without credentials."""
        client = QRZClient()
        result = client._authenticate()

        self.assertFalse(result)
        mock_get.assert_not_called()

    def test_cache_functionality(self):
        """Test caching functionality."""
        callsign = "K1ABC"
        info = CallsignInfo(callsign=callsign, first_name="John")

        # Cache the result
        self.client._cache_result(callsign, info)

        # Retrieve from cache
        cached = self.client._get_from_cache(callsign)
        self.assertEqual(cached, info)

        # Test cache expiry
        # Manually set cache time to expired
        self.client._cache[callsign] = (info, time.time() - self.client.CACHE_TIMEOUT - 1)
        expired = self.client._get_from_cache(callsign)
        self.assertIsNone(expired)

    @patch("qrz.requests.get")
    def test_lookup_callsign_api_success(self, mock_get):
        """Test successful API callsign lookup."""
        # Mock authentication
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.text = """<?xml version="1.0" encoding="utf-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Key>test_session_key</Key>
        <Count>1</Count>
        <SubExp>Fri Sep 29 14:13:57 2034</SubExp>
        <GMTime>Sat Sep 27 19:09:23 2025</GMTime>
        <Remark>cpu: 0.094s</Remark>
        </Session>
        </QRZDatabase>"""

        # Mock lookup response
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.text = """<?xml version="1.0" encoding="utf-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Callsign>
        <call>K1ABC</call>
        <fname>John</fname>
        <name>Doe</name>
        </Callsign>
        </QRZDatabase>"""

        mock_get.side_effect = [auth_response, lookup_response]

        result = self.client._lookup_callsign_api("K1ABC")

        self.assertIsNotNone(result)
        self.assertEqual(result.callsign, "K1ABC")
        self.assertEqual(result.first_name, "John")
        self.assertEqual(result.last_name, "Doe")

    @patch("qrz.requests.get")
    def test_lookup_callsign_api_not_found(self, mock_get):
        """Test API lookup when callsign not found."""
        # Mock authentication
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.text = """<?xml version="1.0" encoding="UTF-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Key>test_session_key</Key>
        </Session>
        </QRZDatabase>"""

        # Mock lookup response with no callsign data
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.text = """<?xml version="1.0" encoding="UTF-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Error>Not found: K1NOTFOUND</Error>
        </Session>
        </QRZDatabase>"""

        mock_get.side_effect = [auth_response, lookup_response]

        result = self.client._lookup_callsign_api("K1NOTFOUND")
        self.assertIsNone(result)

    @patch("qrz.requests.get")
    def test_lookup_callsign_session_timeout(self, mock_get):
        """Test handling of session timeout during lookup."""
        # Set up initial session
        self.client.session_key = "expired_key"
        self.client.session_expires = time.time() + 100

        # Mock session timeout response
        timeout_response = Mock()
        timeout_response.status_code = 200
        timeout_response.text = """<?xml version="1.0" encoding="UTF-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Error>Session Timeout</Error>
        </Session>
        </QRZDatabase>"""

        # Mock re-authentication
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.text = """<?xml version="1.0" encoding="UTF-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Key>new_session_key</Key>
        </Session>
        </QRZDatabase>"""

        # Mock successful lookup after re-auth
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.text = """<?xml version="1.0" encoding="UTF-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Callsign>
        <call>K1ABC</call>
        <fname>John</fname>
        </Callsign>
        </QRZDatabase>"""

        mock_get.side_effect = [timeout_response, auth_response, lookup_response]

        result = self.client._lookup_callsign_api("K1ABC")

        self.assertIsNotNone(result)
        self.assertEqual(result.callsign, "K1ABC")
        self.assertEqual(result.first_name, "John")
        self.assertEqual(self.client.session_key, "new_session_key")

    def test_lookup_callsign_fallback(self):
        """Test lookup fallback when no credentials provided."""
        client = QRZClient()  # No credentials
        result = client.lookup_callsign("K1ABC")

        self.assertEqual(result.callsign, "K1ABC")
        self.assertIsNone(result.first_name)
        self.assertIsNone(result.last_name)

    @patch.object(QRZClient, '_lookup_callsign_api')
    def test_lookup_callsign_with_cache(self, mock_api_lookup):
        """Test lookup using cache."""
        # Pre-populate cache
        callsign = "K1ABC"
        cached_info = CallsignInfo(callsign=callsign, first_name="John")
        self.client._cache_result(callsign, cached_info)

        result = self.client.lookup_callsign(callsign)

        self.assertEqual(result, cached_info)
        mock_api_lookup.assert_not_called()

    @patch.object(QRZClient, '_lookup_callsign_api')
    def test_lookup_callsign_api_success_with_cache(self, mock_api_lookup):
        """Test API lookup with successful result gets cached."""
        api_result = CallsignInfo(callsign="K1ABC", first_name="John")
        mock_api_lookup.return_value = api_result

        result = self.client.lookup_callsign("K1ABC")

        self.assertEqual(result, api_result)
        # Verify it was cached
        cached = self.client._get_from_cache("K1ABC")
        self.assertEqual(cached, api_result)

    def test_cache_cleanup(self):
        """Test cache cleanup when it gets too large."""
        # Fill cache beyond limit
        for i in range(1001):
            callsign = f"K{i}ABC"
            info = CallsignInfo(callsign=callsign)
            self.client._cache_result(callsign, info)

        # Cache should be cleaned up
        self.assertEqual(len(self.client._cache), 1000)

    @patch("qrz.requests.get")
    def test_network_error_handling(self, mock_get):
        """Test handling of network errors during API calls."""
        mock_get.side_effect = Exception("Network error")

        result = self.client._lookup_callsign_api("K1ABC")
        self.assertIsNone(result)

    @patch("qrz.requests.get")
    def test_malformed_xml_response(self, mock_get):
        """Test handling of malformed XML responses."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "This is not valid XML"
        mock_get.return_value = mock_response

        result = self.client._lookup_callsign_api("K1ABC")
        self.assertIsNone(result)

    def test_callsign_normalization(self):
        """Test that callsigns are properly normalized."""
        # Test various callsign formats - QRZ client normalizes to uppercase
        test_cases = [
            ("k1abc", "K1ABC"),
            ("K1ABC", "K1ABC"),
            ("ve3xyz", "VE3XYZ"),
            ("W1AW", "W1AW"),
        ]

        for input_call, expected_normalized in test_cases:
            with patch.object(self.client, '_lookup_callsign_api') as mock_api, \
                 patch.object(self.client, '_get_from_cache', return_value=None):
                mock_api.return_value = CallsignInfo(callsign=expected_normalized)

                result = self.client.lookup_callsign(input_call)

                # Should have called API with normalized callsign
                mock_api.assert_called_with(expected_normalized)
                self.assertEqual(result.callsign, expected_normalized)

    @patch("qrz.requests.get")
    def test_http_error_handling(self, mock_get):
        """Test handling of HTTP errors."""
        mock_get.side_effect = Exception("HTTP 500 Error")

        result = self.client._authenticate()
        self.assertFalse(result)

    def test_session_key_expiry_edge_cases(self):
        """Test edge cases for session key expiry."""
        import time

        # Test exactly at expiry time
        self.client.session_key = "test_key"
        self.client.session_expires = time.time()
        self.assertFalse(self.client._is_session_valid())

        # Test just before expiry
        self.client.session_expires = time.time() + 0.1
        self.assertTrue(self.client._is_session_valid())

    @patch("qrz.requests.get")
    def test_empty_callsign_response(self, mock_get):
        """Test handling when callsign data is empty."""
        # Mock authentication
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.text = """<?xml version="1.0" encoding="UTF-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Session>
        <Key>test_session_key</Key>
        </Session>
        </QRZDatabase>"""

        # Mock lookup response with empty callsign data
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.text = """<?xml version="1.0" encoding="UTF-8" ?>
        <QRZDatabase version="1.36" xmlns="http://xmldata.qrz.com">
        <Callsign>
        <call>K1ABC</call>
        </Callsign>
        </QRZDatabase>"""

        mock_get.side_effect = [auth_response, lookup_response]

        result = self.client._lookup_callsign_api("K1ABC")

        self.assertIsNotNone(result)
        self.assertEqual(result.callsign, "K1ABC")
        self.assertIsNone(result.first_name)
        self.assertIsNone(result.last_name)

    def test_multiple_concurrent_lookups(self):
        """Test that cache works correctly with concurrent-style lookups."""
        callsign = "K1ABC"

        # Simulate two "concurrent" lookups
        info1 = self.client.lookup_callsign(callsign)
        info2 = self.client.lookup_callsign(callsign)

        # Should return the same cached result
        self.assertEqual(info1, info2)
        self.assertEqual(info1.callsign, callsign)


if __name__ == "__main__":
    unittest.main()