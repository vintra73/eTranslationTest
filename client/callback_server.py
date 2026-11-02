"""HTTP server that receives eTranslation REST API v2 callbacks.

The callback URLs are the ones the client sends in ``notifications`` and ``deliveries``
(see APIspecification/eTranslation-RestV2.yaml). Each callback must be acknowledged with HTTP 200.
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).with_name("callback_server.json")


class CallbackPayloadError(ValueError):
    """The callback body does not match the documented schema."""


class CallbackConfigError(ValueError):
    """The callback server configuration file is invalid."""


@dataclass(frozen=True)
class CallbackServerConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    success_path: str = "/etranslation/success"
    failure_path: str = "/etranslation/failure"
    delivery_path: str = "/etranslation/delivery"

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host:
            raise CallbackConfigError("'host' must be a non-empty string")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 0 <= self.port <= 65535:
            raise CallbackConfigError("'port' must be an integer between 0 and 65535")
        for name in ("success_path", "failure_path", "delivery_path"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.startswith("/"):
                raise CallbackConfigError(f"'{name}' must be a string starting with '/'")
        paths = [self.success_path, self.failure_path, self.delivery_path]
        if len(set(paths)) != len(paths):
            raise CallbackConfigError("success, failure and delivery paths must be different")

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
class SuccessNotification:
    request_id: int
    source_language: str
    target_language: str
    external_reference: str | None
    translated_text: str | None  # present only for text-snippet requests


@dataclass(frozen=True)
class FailureNotification:
    request_id: int
    target_languages: list[str]
    external_reference: str | None
    error_code: int
    error_message: str


@dataclass(frozen=True)
class Delivery:
    request_id: int
    source_language: str
    target_language: str
    external_reference: str | None
    output_format: str | None
    result: str  # translated text, or the translated file as a Base64 string


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


def parse_success(payload: Mapping[str, Any]) -> SuccessNotification:
    return SuccessNotification(
        request_id=int(_required(payload, "requestId", (int, float))),
        source_language=_required(payload, "sourceLanguage", str),
        target_language=_required(payload, "targetLanguage", str),
        external_reference=_optional(payload, "externalReference", str),
        translated_text=_optional(payload, "translatedText", str),
    )


def parse_failure(payload: Mapping[str, Any]) -> FailureNotification:
    target_languages = _required(payload, "targetLanguages", list)
    if not all(isinstance(language, str) for language in target_languages):
        raise CallbackPayloadError("field 'targetLanguages' must contain strings")
    return FailureNotification(
        request_id=int(_required(payload, "requestId", (int, float))),
        target_languages=list(target_languages),
        external_reference=_optional(payload, "externalReference", str),
        error_code=int(_required(payload, "errorCode", (int, float))),
        error_message=_required(payload, "errorMessage", str),
    )


def parse_delivery(payload: Mapping[str, Any]) -> Delivery:
    return Delivery(
        request_id=int(_required(payload, "requestId", (int, float))),
        source_language=_required(payload, "sourceLanguage", str),
        target_language=_required(payload, "targetLanguage", str),
        external_reference=_optional(payload, "externalReference", str),
        output_format=_optional(payload, "outputFormat", str),
        result=_required(payload, "result", str),
    )


@dataclass
class CallbackHandlers:
    """Application callbacks invoked for each received event. ``None`` means acknowledge only."""

    on_success: Callable[[SuccessNotification], None] | None = None
    on_failure: Callable[[FailureNotification], None] | None = None
    on_delivery: Callable[[Delivery], None] | None = None


def _make_request_handler(
    routes: Mapping[str, tuple[Callable[[Mapping[str, Any]], Any], Callable[[Any], None] | None]],
) -> type[BaseHTTPRequestHandler]:
    class CallbackRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            route = routes.get(self.path.split("?", 1)[0])
            if route is None:
                self._respond(404)
                return

            parser, handler = route
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
                event = parser(payload)
            except CallbackPayloadError as exc:
                logger.warning("Rejected %s: %s", self.path, exc)
                self._respond(400)
                return

            if handler is not None:
                try:
                    handler(event)
                except Exception:
                    # A non-2xx status tells eTranslation the callback was not processed.
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
    """HTTP server exposing the three eTranslation callback endpoints."""

    def __init__(self, handlers: CallbackHandlers, config: CallbackServerConfig | None = None) -> None:
        config = config or CallbackServerConfig()
        routes = {
            config.success_path: (parse_success, handlers.on_success),
            config.failure_path: (parse_failure, handlers.on_failure),
            config.delivery_path: (parse_delivery, handlers.on_delivery),
        }
        self._httpd = ThreadingHTTPServer((config.host, config.port), _make_request_handler(routes))
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


def _print_event(event: object) -> None:
    print(json.dumps(event.__dict__, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Receive eTranslation REST API v2 callbacks.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="JSON config file")
    parser.add_argument("--host", help="overrides 'host' from the config file")
    parser.add_argument("--port", type=int, help="overrides 'port' from the config file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = CallbackServerConfig.from_file(args.config)
        overrides = {key: value for key, value in (("host", args.host), ("port", args.port)) if value is not None}
        config = replace(config, **overrides)
    except CallbackConfigError as exc:
        parser.error(str(exc))

    handlers = CallbackHandlers(on_success=_print_event, on_failure=_print_event, on_delivery=_print_event)
    server = CallbackServer(handlers, config)
    logger.info("Listening on http://%s:%d", config.host, server.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
