"""Unit test suite for eTranslation API /getDomains call (Test 00).

Tests the getDomains request composition, response parsing, and language pair
validation based on:
- API specification: APIspecification/eTranslation-RestV2.yaml (/getDomains)
- Client implementation: implementation/etranslation_client.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure implementation directory is in sys.path
TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parent.parent
IMPLEMENTATION_DIR = REPO_ROOT / "implementation"

if str(IMPLEMENTATION_DIR) not in sys.path:
    sys.path.insert(0, str(IMPLEMENTATION_DIR))

from etranslation_client import (  # type: ignore[import-not-found]
    DEFAULT_BASE_URL,
    ETranslationClient,
    ETranslationError,
)


class TestETranslationGetDomains(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_domains_payload = [
            {
                "domain": "GEN",
                "languagePairs": ["IT-EN", "IT-DE", "IT-FR", "EN-IT", "DE-IT", "BG-CS"],
            },
            {
                "domain": "SPD",
                "languagePairs": ["IT-EN", "EN-IT"],
            },
        ]

    @patch("requests.Session.request")
    def test_get_domains_request_url_and_method(self, mock_request: MagicMock) -> None:
        """Verify that get_domains performs a GET request to /getDomains with Basic Auth."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_domains_payload
        mock_request.return_value = mock_response

        client = ETranslationClient("test_app", "test_pass")
        result = client.get_domains()

        self.assertEqual(result, self.mock_domains_payload)
        mock_request.assert_called_once()

        method, url = mock_request.call_args[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, f"{DEFAULT_BASE_URL}/getDomains")

    @patch("requests.Session.request")
    def test_get_domains_contains_test01_language_pairs(self, mock_request: MagicMock) -> None:
        """Verify that the response contains IT-EN and IT-DE pairs needed for Test 01."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_domains_payload
        mock_request.return_value = mock_response

        client = ETranslationClient("test_app", "test_pass")
        domains_data = client.get_domains()

        # Find GEN domain
        gen_domain = None
        if isinstance(domains_data, list):
            gen_domain = next((d for d in domains_data if d.get("domain") == "GEN"), None)
        elif isinstance(domains_data, dict):
            gen_domain = domains_data.get("GEN")

        self.assertIsNotNone(gen_domain, "GEN domain should be present")
        pairs = gen_domain.get("languagePairs", [])
        self.assertIn("IT-EN", pairs, "IT-EN language pair should be supported in GEN domain")
        self.assertIn("IT-DE", pairs, "IT-DE language pair should be supported in GEN domain")

    @patch("requests.Session.request")
    def test_get_domains_handles_error(self, mock_request: MagicMock) -> None:
        """Verify that 400 error codes from getDomains are raised as ETranslationError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "errorCode": -90000,
            "errorMessage": "NOT_AUTHORIZED",
        }
        mock_request.return_value = mock_response

        client = ETranslationClient("test_app", "wrong_pass")
        with self.assertRaises(ETranslationError) as ctx:
            client.get_domains()

        self.assertEqual(ctx.exception.error_code, -90000)
        self.assertIn("NOT_AUTHORIZED", ctx.exception.error_message)


if __name__ == "__main__":
    unittest.main()
