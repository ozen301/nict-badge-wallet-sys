import os
import unittest
from unittest.mock import patch

from nictbw.blockchain.api import ChainClient


class DummyResponse:
    def __init__(self, json_data=None, content: bytes = b""):
        self._json = json_data
        if json_data is not None and not content:
            import json as _json

            content = _json.dumps(json_data).encode()
        self.content = content

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


class DummySession:
    def __init__(self, response: DummyResponse):
        self.response = response
        self.calls = []

    def request(
        self,
        method,
        url,
        headers=None,
        params=None,
        json=None,
        data=None,
        files=None,
        timeout=None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "json": json,
                "data": data,
                "files": files,
                "timeout": timeout,
            }
        )
        return self.response


class TestChainClient(unittest.TestCase):
    @patch("nictbw.blockchain.api.open_session")
    @patch("nictbw.blockchain.api.load_dotenv")
    def test_requires_fqdn(self, mock_load_dotenv, mock_open_session):
        # Ensure environment variable is not set and no network call is made
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                ChainClient()
        mock_open_session.assert_not_called()

    @patch("nictbw.blockchain.api.get_jwt_token", return_value="jwt-token")
    @patch("nictbw.blockchain.api.open_session")
    def test_init_sets_base_url_and_tokens(self, mock_open_session, mock_get_jwt):
        session = DummySession(DummyResponse(json_data={}))
        mock_open_session.return_value = (session, "csrf-token")
        client = ChainClient(base_fqdn="api.example.com")
        self.assertEqual(client.base_url, "https://api.example.com")
        self.assertEqual(client.csrf, "csrf-token")
        self.assertEqual(client.jwt, "jwt-token")

    @patch("nictbw.blockchain.api.get_jwt_token", return_value="jwt-token")
    @patch("nictbw.blockchain.api.open_session")
    def test_request_returns_expected_formats(self, mock_open_session, mock_get_jwt):
        json_response = DummyResponse(json_data={"a": 1})
        session = DummySession(json_response)
        mock_open_session.return_value = (session, "csrf")
        client = ChainClient(base_fqdn="host")

        # JSON by default
        result = client._request("GET", "/path")
        self.assertEqual(result, {"a": 1})
        self.assertEqual(session.calls[0]["url"], "https://host/path")

        # Raw bytes when return_in_json is False
        byte_response = DummyResponse(content=b"data")
        session.response = byte_response
        result_bytes = client._request("GET", "/raw", return_in_json=False)
        self.assertEqual(result_bytes, b"data")

    @patch("nictbw.blockchain.api.get_jwt_token")
    @patch("nictbw.blockchain.api.open_session")
    def test_init_reports_session_error(self, mock_open_session, mock_get_jwt):
        mock_open_session.side_effect = RuntimeError("network unreachable")
        with self.assertRaises(RuntimeError) as ctx:
            ChainClient(base_fqdn="api.example.com")
        self.assertIn("network unreachable", str(ctx.exception))
        mock_get_jwt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
