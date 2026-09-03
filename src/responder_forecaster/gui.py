from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
import statistics
import threading
from typing import Any
from urllib.parse import urlparse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .memory import AuditMemory
from .orchestrator import run_forecast
from .paths import data_root, default_memory_path
from .retrieval import validate_passages


WEB_ROOT = Path(__file__).resolve().parent / "web"
DATA_ROOT = data_root()
SHOWCASE_ROOT = DATA_ROOT / "synthetic" / "showcase"
KNOWLEDGE_PATH = DATA_ROOT / "public" / "authoritative_guidance.json"
MEMORY_PATH = default_memory_path("gui_audit_memory.sqlite3")
MAX_REQUEST_BYTES = 64 * 1024
MAX_CONCURRENT_REQUESTS = 16

SHOWCASE_DESCRIPTIONS = {
    "01_routine_monitoring": "Routine workload, strong staffing, and no weather alert.",
    "02_low_guard_reserve_conflict": "Low overall strain with one fictional availability conflict.",
    "03_moderate_overnight_pressure": "Overnight calls and reduced availability raise recovery concerns.",
    "04_moderate_long_shift": "A longer shift and incident load create moderate strain.",
    "05_moderate_staffing_and_heat": "Reduced staffing overlaps with a hypothetical heat alert.",
    "06_moderate_heat_after_overnight_calls": "Overnight disruption and hypothetical heat interact.",
    "07_high_staffing_recovery_pressure": "Low availability, overnight calls, and long shifts combine.",
    "08_high_heat_training_pressure": "High strain with hypothetical heat and outdoor training.",
    "09_high_staffing_guard_weather": "Staffing, fictional Guard or Reserve conflicts, and weather overlap.",
    "10_high_combined_factors": "All major synthetic strain factors are active.",
    "11_high_winter_weather": "A future hypothetical winter alert overlaps with high workload.",
    "12_moderate_no_weather": "Moderate operational strain without a weather alert.",
    "13_stale_heat_alert": "An expired hypothetical alert should trigger safe human review.",
    "14_alert_missing_expiration": "An incomplete alert window should trigger safe human review.",
    "15_missing_staffing_guardrail": "A required staffing value is intentionally missing.",
    "16_private_data_flag_guardrail": "A synthetic privacy flag intentionally stops the run.",
}


def _title_from_id(value: str) -> str:
    words = value.replace("_", " ").replace("-", " ").split()
    if words and words[0].isdigit():
        words = words[1:]
    return " ".join(word.capitalize() for word in words)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_showcase_presets() -> list[dict[str, Any]]:
    presets: list[dict[str, Any]] = []
    paths = sorted(SHOWCASE_ROOT.glob("*.json"))
    if not paths:
        raise ValueError("showcase_presets_unavailable")
    seen_ids: set[str] = set()
    for path in paths:
        try:
            scenario = _load_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"showcase_preset_unreadable: {path.name}") from error
        if not isinstance(scenario, dict):
            raise ValueError(f"showcase_preset_must_be_an_object: {path.name}")
        if path.stem in seen_ids:
            raise ValueError(f"duplicate_showcase_preset_id: {path.stem}")
        seen_ids.add(path.stem)
        if scenario.get("scenario_status") != "Synthetic test data; not a statement of current local conditions":
            raise ValueError(f"showcase_preset_must_be_explicitly_synthetic: {path.name}")
        presets.append(
            {
                "id": path.stem,
                "label": _title_from_id(path.stem),
                "description": SHOWCASE_DESCRIPTIONS.get(path.stem, "Synthetic team-level demonstration case."),
                "scenario": scenario,
            }
        )
    return presets


def run_showcase(
    passages: list[dict[str, Any]],
    memory_path: Path = MEMORY_PATH,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for preset in load_showcase_presets():
        result = run_forecast(preset["scenario"], passages, memory_path)
        results.append(
            {
                "id": preset["id"],
                "label": preset["label"],
                "decision": result["decision"],
                "strain": result["strain"],
                "risk_score": result["risk_score"],
                "confidence": result["confidence"],
                "human_review_required": result["human_review_required"],
                "latency_ms": result["latency_ms"],
                "escalations": result["escalations"],
            }
        )

    latencies = [float(item["latency_ms"]) for item in results]
    ordered = sorted(latencies)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1) if ordered else 0
    return {
        "synthetic_only": True,
        "case_count": len(results),
        "decision_distribution": dict(Counter(item["decision"] for item in results)),
        "strain_distribution": dict(Counter(item["strain"] for item in results)),
        "mean_latency_ms": round(statistics.fmean(latencies), 2) if latencies else None,
        "p95_latency_ms": round(ordered[p95_index], 2) if ordered else None,
        "cases": results,
        "limitations": [
            "These are deterministic synthetic behavior demonstrations, not predictive accuracy results.",
            "Scores and action effects are illustrative and require local expert calibration.",
            "No recommendation may bypass authorized human review or incident command.",
        ],
    }


@dataclass(frozen=True)
class AppContext:
    passages: list[dict[str, Any]]
    memory_path: Path
    host: str
    port: int


class ForecasterServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        context: AppContext,
        *,
        max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS,
    ):
        self.context = context
        self.request_slots = threading.BoundedSemaphore(max_concurrent_requests)
        super().__init__(address, ForecasterHandler)

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self.request_slots.acquire(blocking=False):
            body = b'{"error":"server_busy"}'
            response = (
                b"HTTP/1.1 429 Too Many Requests\r\n"
                b"Content-Type: application/json; charset=utf-8\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Cache-Control: no-store\r\n"
                + b"Retry-After: 1\r\n"
                + b"Connection: close\r\n\r\n"
                + body
            )
            try:
                request.sendall(response)
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()


class ForecasterHandler(BaseHTTPRequestHandler):
    server: ForecasterServer
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self._response_started = False

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[gui] {self.address_string()} - {format % args}")

    def _security_headers(self, content_type: str, content_length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )

    def _send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        *,
        cache_control: str = "no-store",
        close_connection: bool = False,
    ) -> None:
        self._response_started = True
        self.send_response(status)
        self._security_headers(content_type, len(body))
        self.send_header("Cache-Control", cache_control)
        if close_connection:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: Any, *, close_connection: bool = False) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self._send_bytes(
            status,
            body,
            "application/json; charset=utf-8",
            close_connection=close_connection,
        )

    def _host_is_allowed(self) -> bool:
        host = self.headers.get("Host", "")
        try:
            parsed = urlparse(f"//{host}")
            port = parsed.port or 80
        except ValueError:
            return False
        return (
            parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and port == self.server.server_address[1]
        )

    def _origin_is_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        try:
            port = parsed.port or 80
        except ValueError:
            return False
        return (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and port == self.server.server_address[1]
        )

    def _guard_request(self, *, require_origin: bool = False) -> bool:
        if not self._host_is_allowed():
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {"error": "local_host_required"},
                close_connection=True,
            )
            return False
        if require_origin and not self._origin_is_allowed():
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {"error": "same_origin_required"},
                close_connection=True,
            )
            return False
        return True

    def _read_json_body(self) -> Any:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("content_type_must_be_application_json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid_content_length") from error
        if length <= 0:
            raise ValueError("request_body_required")
        if length > MAX_REQUEST_BYTES:
            raise OverflowError("request_body_too_large")
        payload = self.rfile.read(length)
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid_json") from error

    def _handle_unexpected_failure(self, error: Exception) -> None:
        self.log_error("Unhandled request failure: %s", type(error).__name__)
        if self._response_started:
            self.close_connection = True
            return
        try:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "unexpected_server_failure"},
                close_connection=True,
            )
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True

    def do_GET(self) -> None:
        try:
            self._do_GET()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as error:
            self._handle_unexpected_failure(error)

    def _do_GET(self) -> None:
        if not self._guard_request():
            return
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "Responder Readiness and Recovery Forecaster",
                    "synthetic_only": True,
                    "check": "liveness_and_static_readiness",
                    "preset_count": len(load_showcase_presets()),
                    "evidence_count": len(self.server.context.passages),
                },
            )
            return
        if path == "/api/presets":
            self._send_json(
                HTTPStatus.OK,
                {
                    "synthetic_only": True,
                    "presets": load_showcase_presets(),
                },
            )
            return

        static_map = {
            "/": (WEB_ROOT / "index.html", "text/html; charset=utf-8"),
            "/assets/styles.css": (WEB_ROOT / "styles.css", "text/css; charset=utf-8"),
            "/assets/app.js": (WEB_ROOT / "app.js", "text/javascript; charset=utf-8"),
            "/favicon.svg": (WEB_ROOT / "favicon.svg", "image/svg+xml"),
        }
        target = static_map.get(path)
        if target is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        file_path, content_type = target
        try:
            body = file_path.read_bytes()
        except OSError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "interface_asset_unavailable"})
            return
        self._send_bytes(HTTPStatus.OK, body, content_type, cache_control="no-cache")

    def do_POST(self) -> None:
        try:
            self._do_POST()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as error:
            self._handle_unexpected_failure(error)

    def _do_POST(self) -> None:
        if not self._guard_request(require_origin=True):
            return
        path = self.path.split("?", 1)[0]
        if path == "/api/forecast":
            try:
                body = self._read_json_body()
            except OverflowError as error:
                self._send_json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {"error": str(error)},
                    close_connection=True,
                )
                return
            except ValueError as error:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": str(error)},
                    close_connection=True,
                )
                return
            if not isinstance(body, dict):
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "request_body_must_be_an_object"},
                    close_connection=True,
                )
                return
            raw_scenario = body.get("scenario", body)
            result = run_forecast(raw_scenario, self.server.context.passages, self.server.context.memory_path)
            self._send_json(HTTPStatus.OK, result)
            return
        if path == "/api/showcase":
            content_length = self.headers.get("Content-Length")
            if content_length not in {None, "0"}:
                try:
                    self._read_json_body()
                except (ValueError, OverflowError) as error:
                    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE if isinstance(error, OverflowError) else HTTPStatus.BAD_REQUEST
                    self._send_json(status, {"error": str(error)}, close_connection=True)
                    return
            self._send_json(
                HTTPStatus.OK,
                run_showcase(self.server.context.passages, self.server.context.memory_path),
            )
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def build_server(host: str = "127.0.0.1", port: int = 8765, memory_path: Path = MEMORY_PATH) -> ForecasterServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("gui_host_must_be_loopback")
    required_assets = ("index.html", "styles.css", "app.js", "favicon.svg")
    missing_assets = [name for name in required_assets if not (WEB_ROOT / name).is_file()]
    if missing_assets:
        raise ValueError(f"interface_assets_missing: {', '.join(missing_assets)}")
    passages = validate_passages(_load_json(KNOWLEDGE_PATH))
    load_showcase_presets()
    resolved_memory_path = Path(memory_path)
    with AuditMemory(resolved_memory_path):
        pass
    context = AppContext(passages=passages, memory_path=resolved_memory_path, host=host, port=port)
    return ForecasterServer((host, port), context)


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the local responder-readiness web interface.")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost", "::1"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--memory", type=Path, default=MEMORY_PATH)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the interface in the default browser.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    server = build_server(args.host, args.port, args.memory)
    display_host = "localhost" if args.host in {"127.0.0.1", "::1"} else args.host
    url = f"http://{display_host}:{args.port}"
    print(f"Responder Readiness GUI running at {url}")
    print("Synthetic demonstration only. Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nStopping the GUI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
