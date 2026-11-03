"""Unit and integration test suite for eTranslation API call with glossary (Test 01).

Tests the request composition, glossary handling, and client integration based on:
- API specification: APIspecification/eTranslation-RestV2.yaml
- Client implementation: implementation/etranslation_client.py
"""

from __future__ import annotations

import base64
import json
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
    inline_document,
)


class TestETranslationGlossary(unittest.TestCase):
    def setUp(self) -> None:
        self.glossary_path = TEST_DIR / "glossary.tsv"
        self.text = "Validatore dei file turtle (.ttl)"
        self.source_language = "IT"
        self.target_languages = ["EN", "DE"]

    def test_glossary_file_exists_and_content(self) -> None:
        """Verify that the glossary file exists and contains 'turtle' for IT, EN, and DE."""
        self.assertTrue(self.glossary_path.is_file(), f"Missing {self.glossary_path}")
        content = self.glossary_path.read_text(encoding="utf-8").strip()
        lines = [line.split("\t") for line in content.splitlines() if line.strip()]

        self.assertGreaterEqual(len(lines), 1, "Glossary must have at least one line")
        # Find turtle row
        turtle_row = next((row for row in lines if row[0] == "turtle"), None)
        self.assertIsNotNone(turtle_row, "Glossary should contain a row starting with 'turtle'")
        # Ensure it has mappings for at least 3 columns (IT, EN, DE)
        self.assertGreaterEqual(len(turtle_row), 3, "Glossary row must have entries for IT, EN, and DE")
        self.assertEqual(turtle_row[0], "turtle")  # IT
        self.assertEqual(turtle_row[1], "turtle")  # EN
        self.assertEqual(turtle_row[2], "turtle")  # DE

    def test_glossary_inline_document_structure(self) -> None:
        """Verify the inline_document Base64 encoding and format metadata."""
        raw_bytes = self.glossary_path.read_bytes()
        glossary_source = inline_document(raw_bytes, "tsv", filename="glossary.tsv")

        self.assertIn("document", glossary_source)
        doc = glossary_source["document"]
        self.assertEqual(doc["format"], "tsv")
        self.assertEqual(doc["filename"], "glossary.tsv")

        # Decode base64 to ensure it matches original content
        decoded = base64.b64decode(doc["content"]).decode("utf-8")
        self.assertIn("turtle\tturtle\tturtle", decoded)

    @patch("requests.Session.request")
    def test_translate_text_with_glossary_payload(self, mock_request: MagicMock) -> None:
        """Verify that ETranslationClient.translate_text constructs the exact expected JSON body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"requestId": 12345678}
        mock_request.return_value = mock_response

        glossary_source = inline_document(self.glossary_path.read_bytes(), "tsv", filename="glossary.tsv")

        client = ETranslationClient("test_app", "test_pass")
        req_id = client.translate_text(
            source_language=self.source_language,
            target_languages=self.target_languages,
            text=self.text,
            glossary=glossary_source,
        )

        self.assertEqual(req_id, 12345678)
        mock_request.assert_called_once()

        # Check call arguments
        method, url = mock_request.call_args[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, f"{DEFAULT_BASE_URL}/askTranslate")

        # Check JSON payload sent
        body = mock_request.call_args[1]["json"]
        self.assertEqual(body["textToTranslate"], self.text)
        self.assertEqual(body["sourceLanguage"], "IT")
        self.assertEqual(body["targetLanguages"], ["EN", "DE"])
        self.assertEqual(body["glossary"], glossary_source)

    @patch("requests.Session.request")
    def test_translate_text_error_handling(self, mock_request: MagicMock) -> None:
        """Verify that HTTP 400 responses with an errorCode raise ETranslationError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "errorCode": -10418,
            "errorMessage": "GLOSSARY_NOT_SUPPORTED_WITH_SNIPPET",
        }
        mock_request.return_value = mock_response

        client = ETranslationClient("test_app", "test_pass")
        glossary_source = inline_document(b"turtle\tturtle\tturtle", "tsv")

        with self.assertRaises(ETranslationError) as ctx:
            client.translate_text(
                source_language=self.source_language,
                target_languages=self.target_languages,
                text=self.text,
                glossary=glossary_source,
            )

        self.assertEqual(ctx.exception.error_code, -10418)
        self.assertIn("GLOSSARY_NOT_SUPPORTED_WITH_SNIPPET", ctx.exception.error_message)


if __name__ == "__main__":
    unittest.main()
