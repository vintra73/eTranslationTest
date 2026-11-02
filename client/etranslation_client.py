"""Python client for the eTranslation REST API v2.

Specification: APIspecification/eTranslation-RestV2.yaml
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import requests

DEFAULT_BASE_URL = "https://language-tools.ec.europa.eu/etranslation/api"
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")
TEXT_MAX_LENGTH = 5000
LLM_MODELS = ("model1", "model2", "model3")
FILE_SOURCE_KEYS = ("ftp", "sftp", "http", "document")
NOTIFICATION_PROTOCOLS = ("http", "ftp", "sftp")
NOTIFICATION_KEYS = ("success", "failure")
_LANGUAGE_RE = re.compile(r"^[A-Z]{2}$")


class ETranslationError(Exception):
    """The service rejected the request with a negative errorCode (HTTP 400)."""

    def __init__(self, error_code: int, error_message: str) -> None:
        super().__init__(f"{error_code} {error_message}")
        self.error_code = error_code
        self.error_message = error_message


def inline_document(data: bytes, file_format: str, filename: str | None = None) -> dict[str, Any]:
    """Build a file source with an inline Base64 document, ready for ``translate_document``."""
    document: dict[str, Any] = {
        "content": base64.b64encode(data).decode("ascii"),
        "format": file_format,
    }
    if filename is not None:
        document["filename"] = filename
    return {"document": document}


def _check_language(code: str, *, allow_ld: bool = False) -> None:
    if allow_ld and code == "LD":
        return
    if not _LANGUAGE_RE.match(code):
        raise ValueError(f"Invalid language code {code!r}: expected two uppercase letters (ISO 639-1)")


def _check_targets(target_languages: Sequence[str]) -> None:
    if not target_languages:
        raise ValueError("At least one target language is required")
    for code in target_languages:
        _check_language(code)


def _check_file_source(file_source: Mapping[str, Any]) -> None:
    unknown = set(file_source) - set(FILE_SOURCE_KEYS)
    if unknown:
        raise ValueError(f"Unsupported file source keys: {sorted(unknown)}")
    if len(file_source) != 1:
        raise ValueError("Exactly one of ftp, sftp, http or document must be provided")


def _check_notifications(notifications: Mapping[str, Any]) -> None:
    unknown = set(notifications) - set(NOTIFICATION_KEYS)
    if unknown:
        raise ValueError(f"Unsupported notification keys: {sorted(unknown)}")
    for key, endpoint in notifications.items():
        _check_single_protocol(f"notifications.{key}", endpoint, exactly_one=True)


def _check_deliveries(deliveries: Mapping[str, Any]) -> None:
    _check_single_protocol("deliveries", deliveries, exactly_one=False)


def _check_single_protocol(name: str, endpoint: Mapping[str, Any], *, exactly_one: bool) -> None:
    unknown = set(endpoint) - set(NOTIFICATION_PROTOCOLS)
    if unknown:
        raise ValueError(f"{name}: unsupported protocols {sorted(unknown)}")
    present = [key for key in NOTIFICATION_PROTOCOLS if endpoint.get(key)]
    if exactly_one and len(present) != 1:
        raise ValueError(f"{name}: exactly one of http, ftp or sftp is required")
    if not exactly_one and not present:
        raise ValueError(f"{name}: at least one of http, ftp or sftp is required")


def _check_llm(llm: Mapping[str, Any]) -> None:
    if "enabled" not in llm:
        raise ValueError("llm.enabled is required")
    model = llm.get("model")
    if model is not None and model not in LLM_MODELS:
        raise ValueError(f"llm.model must be one of {LLM_MODELS}")


def _compact(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class ETranslationClient:
    """Client for the eTranslation REST API v2.

    Translation requests are asynchronous: the service returns a request ID and
    delivers results to the notification and delivery endpoints you provide.
    """

    def __init__(
        self,
        application: str,
        password: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.auth = (application, password)
        self._session.headers["Accept"] = "application/json"

    @classmethod
    def from_config(
        cls,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        **kwargs: Any,
    ) -> ETranslationClient:
        """Create a client using the ``username`` and ``password`` stored in a JSON config file.

        Extra keyword arguments (``base_url``, ``timeout``, ``session``) are passed to the constructor.
        """
        path = Path(config_path)
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Config file not found: {path}. Copy config.example.json to config.json and fill it in."
            ) from exc
        if not isinstance(config, dict):
            raise ValueError(f"{path}: expected a JSON object")
        for key in ("username", "password"):
            if not config.get(key):
                raise ValueError(f"{path}: '{key}' is missing or empty")
        return cls(config["username"], config["password"], **kwargs)

    def __enter__(self) -> ETranslationClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    def translate_text(
        self,
        *,
        source_language: str,
        target_languages: Sequence[str],
        text: str,
        notifications: Mapping[str, Any] | None = None,
        deliveries: Mapping[str, Any] | None = None,
        domain: str | None = None,
        caller_information: Mapping[str, str] | None = None,
        glossary: Mapping[str, Any] | None = None,
        llm: Mapping[str, Any] | None = None,
    ) -> int:
        """Submit a text-snippet translation and return its request ID.

        For text snippets the translated text is returned in the success notification.
        ``source_language`` may be ``"LD"`` to request automatic language detection.
        """
        _check_language(source_language, allow_ld=True)
        _check_targets(target_languages)
        if not 1 <= len(text) <= TEXT_MAX_LENGTH:
            raise ValueError(f"text must be between 1 and {TEXT_MAX_LENGTH} characters")
        if notifications is not None:
            _check_notifications(notifications)
        if deliveries is not None:
            _check_deliveries(deliveries)
        if glossary is not None:
            _check_file_source(glossary)
        if llm is not None:
            _check_llm(llm)

        body = _compact(
            {
                "callerInformation": caller_information,
                "textToTranslate": text,
                "glossary": glossary,
                "sourceLanguage": source_language,
                "targetLanguages": list(target_languages),
                "domain": domain,
                "llm": llm,
                "notifications": notifications,
                "deliveries": deliveries,
            }
        )
        return self._submit(body)

    def translate_document(
        self,
        *,
        source_language: str,
        target_languages: Sequence[str],
        document: Mapping[str, Any],
        notifications: Mapping[str, Any],
        deliveries: Mapping[str, Any],
        domain: str | None = None,
        caller_information: Mapping[str, str] | None = None,
        glossary: Mapping[str, Any] | None = None,
        output_format: str | None = None,
        with_quality_estimate: bool | None = None,
        preserve_tags: bool | None = None,
        add_disclaimer: bool | None = None,
        llm: Mapping[str, Any] | None = None,
    ) -> int:
        """Submit a document translation and return its request ID.

        ``document`` is a file source: exactly one of ``ftp``, ``sftp``, ``http`` or
        ``document`` (inline Base64, see ``inline_document``). Notifications and
        deliveries are required because the result is a file.
        """
        _check_language(source_language, allow_ld=True)
        _check_targets(target_languages)
        _check_file_source(document)
        _check_notifications(notifications)
        _check_deliveries(deliveries)
        if glossary is not None:
            _check_file_source(glossary)
        if llm is not None:
            _check_llm(llm)

        body = _compact(
            {
                "callerInformation": caller_information,
                "documentToTranslate": document,
                "glossary": glossary,
                "sourceLanguage": source_language,
                "targetLanguages": list(target_languages),
                "domain": domain,
                "outputFormat": output_format,
                "withQualityEstimate": with_quality_estimate,
                "preserveTags": preserve_tags,
                "addDisclaimer": add_disclaimer,
                "llm": llm,
                "notifications": notifications,
                "deliveries": deliveries,
            }
        )
        return self._submit(body)

    def get_domains(self) -> Any:
        """Return the language pairs available per domain (raw JSON from ``/getDomains``)."""
        return self._request("GET", "/getDomains")

    def get_status(self) -> dict[str, Any]:
        """Return the system status: ``level`` (0 normal, 1 heavy, 2 critical, 3 blocked) and ``message``."""
        return self._request("GET", "/status")

    def _submit(self, body: Mapping[str, Any]) -> int:
        response = self._request("POST", "/askTranslate", body)
        return int(response["requestId"])

    def _request(self, method: str, path: str, json_body: Mapping[str, Any] | None = None) -> Any:
        response = self._session.request(
            method,
            f"{self._base_url}{path}",
            json=json_body,
            timeout=self._timeout,
        )
        if response.status_code == 400:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict) and "errorCode" in payload:
                raise ETranslationError(int(payload["errorCode"]), str(payload.get("errorMessage", "")))
        response.raise_for_status()
        return response.json()
