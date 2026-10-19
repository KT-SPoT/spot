import unittest
from http.client import RemoteDisconnected
from unittest.mock import Mock
from urllib.error import HTTPError

from src.scouts.quant_sbiz365 import Sbiz365Error, _request_text


class TransportFailureTests(unittest.TestCase):
    def test_disconnects_are_safe_provider_failures(self):
        for failure in (RemoteDisconnected("certKey=private-token"),
                        ConnectionResetError("certKey=private-token")):
            with self.subTest(failure=type(failure).__name__):
                opener = Mock()
                opener.open.side_effect = failure
                with self.assertRaises(Sbiz365Error) as caught:
                    _request_text(opener, "https://example.com/?certKey=private-token", {})
                self.assertNotIn("private-token", str(caught.exception))
                self.assertIn("네트워크 연결 실패", str(caught.exception))

    def test_http_status_errors_keep_existing_handling(self):
        failure = HTTPError("https://example.com", 503, "unavailable", {}, None)
        opener = Mock()
        opener.open.side_effect = failure
        with self.assertRaises(HTTPError) as caught:
            _request_text(opener, "https://example.com", {})
        self.assertIs(caught.exception, failure)
