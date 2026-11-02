"""HTTP server that receives eTranslation REST API v2 callbacks.

Specification: APIspecification/callback.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Union

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).with_name("callback_server.json")


class CallbackStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class CallbackPayloadError(ValueError):
    """The callback body does not match the documented schema."""


class CallbackConfigError(ValueError):
    """The callback server configuration file is invalid."""


@dataclass(frozen=True)
class CallbackServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    callback_path: str = "/callback"

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host:
            raise CallbackConfigError("'host' must be a non-empty string")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 0 <= self.port <= 65535:
            raise CallbackConfigError("'port' must be an integer between 0 and 65535")
        if not isinstance(self.callback_path, str) or not self.callback_path.startswith("/"):
            raise CallbackConfigError("'callback_path' must be a string starting with '/'")

    @classmethod
    def from_file(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> CallbackServerConfig:
        config_path = Path(path)
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CallbackConfigError(f"Config file not found: {config_path}") from exc
        except ValueError as exc:
            raise CallbackConfigError(f"{config_path}: invalid JSON ({exc})") from exc
        if not isinstance(data, dict):
            raise CallbackConfigError(f"{config_path}: expected a JSON object")
        known = {field.name for field in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise CallbackConfigError(f"{config_path}: unknown keys {sorted(unknown)}")
        return cls(**data)


@dataclass(frozen=True)
class TextTranslationCallback:
    request_id: int
    target_language: str
    status: CallbackStatus
    translated_text: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class DocumentTranslationCallback:
    request_id: int
    target_language: str
    status: CallbackStatus
    document_id: int | None = None
    error_message: str | None = None


CallbackEvent = Union[TextTranslationCallback, DocumentTranslationCallback]


def _required(payload: Mapping[str, Any], key: str, types: type | tuple[type, ...]) -> Any:
    if key not in payload:
        raise CallbackPayloadError(f"missing field '{key}'")
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, types):
        raise CallbackPayloadError(f"field '{key}' has an invalid type")
    return value


def _optional(payload: Mapping[str, Any], key: str, types: type | tuple[type, ...]) -> Any:
    if payload.get(key) is None:
        return None
    return _required(payload, key, types)


def parse_callback(payload: Mapping[str, Any]) -> CallbackEvent:
    request_id = int(_required(payload, "requestId", (int, float)))
    target_language = _required(payload, "targetLanguage", str)
    raw_status = _required(payload, "status", str)

    try:
        status = CallbackStatus(raw_status)
    except ValueError:
        raise CallbackPayloadError(f"invalid status '{raw_status}': must be SUCCESS or ERROR")

    error_message = _optional(payload, "errorMessage", str)

    if "documentId" in payload:
        raw_doc_id = payload.get("documentId")
        document_id = None
        if raw_doc_id is not None:
            if isinstance(raw_doc_id, bool) or not isinstance(raw_doc_id, (int, float)):
                raise CallbackPayloadError("field 'documentId' must be an integer")
            document_id = int(raw_doc_id)
        return DocumentTranslationCallback(
            request_id=request_id,
            target_language=target_language,
            status=status,
            document_id=document_id,
            error_message=error_message,
        )

    translated_text = _optional(payload, "translatedText", str)
    return TextTranslationCallback(
        request_id=request_id,
        target_language=target_language,
        status=status,
        translated_text=translated_text,
        error_message=error_message,
    )


@dataclass
class CallbackHandlers:
    """Application callbacks invoked for each received event. ``None`` means acknowledge only."""

    on_text_callback: Callable[[TextTranslationCallback], None] | None = None
    on_document_callback: Callable[[DocumentTranslationCallback], None] | None = None
    on_callback: Callable[[CallbackEvent], None] | None = None

    def handle(self, event: CallbackEvent) -> None:
        if isinstance(event, TextTranslationCallback) and self.on_text_callback is not None:
            self.on_text_callback(event)
        elif isinstance(event, DocumentTranslationCallback) and self.on_document_callback is not None:
            self.on_document_callback(event)
        if self.on_callback is not None:
            self.on_callback(event)


def _make_request_handler(
    callback_path: str,
    handlers: CallbackHandlers,
) -> type[BaseHTTPRequestHandler]:
    class CallbackRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            req_path = self.path.split("?", 1)[0]
            if req_path != callback_path:
                self._respond(404)
                return

            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length))
            except ValueError:
                logger.warning("Rejected %s: body is not valid JSON", self.path)
                self._respond(400)
                return

            if not isinstance(payload, dict):
                logger.warning("Rejected %s: body is not a JSON object", self.path)
                self._respond(400)
                return

            try:
                event = parse_callback(payload)
            except CallbackPayloadError as exc:
                logger.warning("Rejected %s: %s", self.path, exc)
                self._respond(400)
                return

            try:
                handlers.handle(event)
            except Exception:
                # HTTP 500 tells eTranslation the callback was not processed
                logger.exception("Handler failed for %s", self.path)
                self._respond(500)
                return

            self._respond(200)

        def _respond(self, status: int) -> None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            logger.info("%s - %s", self.address_string(), format % args)

    return CallbackRequestHandler


class CallbackServer:
    """HTTP server exposing the callback endpoint defined in APIspecification/callback.yaml."""

    def __init__(self, handlers: CallbackHandlers, config: CallbackServerConfig | None = None) -> None:
        self.config = config or CallbackServerConfig()
        handler_cls = _make_request_handler(self.config.callback_path, handlers)
        self._httpd = ThreadingHTTPServer((self.config.host, self.config.port), handler_cls)
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    def start(self) -> None:
        """Serve requests in a background thread."""
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def serve_forever(self) -> None:
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join()

    def __enter__(self) -> CallbackServer:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


def _print_event(event: CallbackEvent) -> None:
    data = dict(event.__dict__)
    if isinstance(data.get("status"), CallbackStatus):
        data["status"] = data["status"].value
    data["type"] = type(event).__name__
    print(json.dumps(data, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Receive eTranslation REST API v2 callbacks.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="JSON config file")
    parser.add_argument("--host", help="overrides 'host' from the config file")
    parser.add_argument("--port", type=int, help="overrides 'port' from the config file")
    parser.add_argument("--path", dest="callback_path", help="overrides 'callback_path' from the config file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = CallbackServerConfig.from_file(args.config)
        overrides = {
            key: value
            for key, value in (("host", args.host), ("port", args.port), ("callback_path", args.callback_path))
            if value is not None
        }
        config = replace(config, **overrides)
    except CallbackConfigError as exc:
        parser.error(str(exc))

    handlers = CallbackHandlers(on_callback=_print_event)
    server = CallbackServer(handlers, config)
    logger.info("Listening on http://%s:%d%s", config.host, server.port, config.callback_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
