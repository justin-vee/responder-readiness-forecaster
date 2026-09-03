from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from responder_forecaster.gui import MAX_CONCURRENT_REQUESTS, build_server, load_showcase_presets


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        memory_path = Path(self.temporary_directory.name) / "gui.sqlite3"
        self.server = build_server("127.0.0.1", 0, memory_path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def get_json(self, path: str):
        with closing(urlopen(f"{self.base_url}{path}", timeout=3)) as response:
            return response.status, dict(response.headers), json.loads(response.read())

    def post_json(self, path: str, payload: dict):
        request = Request(
            f"{self.base_url}{path}",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with closing(urlopen(request, timeout=5)) as response:
            return response.status, dict(response.headers), json.loads(response.read())

    def raw_request(
        self,
        method: str,
        path: str,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        *,
        skip_host: bool = False,
    ):
        host, port = self.server.server_address[:2]
        connection = http.client.HTTPConnection(host, port, timeout=5)
        try:
            connection.putrequest(method, path, skip_host=skip_host)
            for name, value in (headers or {}).items():
                connection.putheader(name, value)
            if body and not any(name.lower() == "content-length" for name in (headers or {})):
                connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            payload = json.loads(response.read())
            return response.status, dict(response.headers), payload
        finally:
            connection.close()

    def test_health_and_static_interface_are_available(self):
        status, headers, health = self.get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["preset_count"], 16)
        self.assertEqual(health["evidence_count"], 7)
        self.assertEqual(health["check"], "liveness_and_static_readiness")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

        with closing(urlopen(f"{self.base_url}/", timeout=3)) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Responder Readiness Forecaster", body)
            self.assertIn("Synthetic demonstration only", body)
            self.assertIn("Content-Security-Policy", response.headers)

    def test_gui_assets_and_usability_controls_are_served(self):
        expected = {
            "/": ("text/html", ("result-stale", "data-quick-preset", "run-preset-button", "showcase-ready-count")),
            "/assets/styles.css": ("text/css", ("quick-start-grid", "risk-scale", "table-action")),
            "/assets/app.js": ("text/javascript", ("markResultStale", "choosePreset", "Run again to download")),
            "/favicon.svg": ("image/svg+xml", ("<svg",)),
        }
        for path, (content_type, markers) in expected.items():
            with self.subTest(path=path), closing(urlopen(f"{self.base_url}{path}", timeout=3)) as response:
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertTrue(response.headers["Content-Type"].startswith(content_type))
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                for marker in markers:
                    self.assertIn(marker, body)

    def test_preset_can_be_forecast_through_the_api(self):
        _, _, preset_payload = self.get_json("/api/presets")
        self.assertEqual(len(preset_payload["presets"]), 16)
        scenario = preset_payload["presets"][0]["scenario"]
        status, _, result = self.post_json("/api/forecast", {"scenario": scenario})
        self.assertEqual(status, 200)
        self.assertEqual(result["decision"], "ADVISORY")
        self.assertEqual(result["strain"], "low")
        self.assertIn("safety_boundary", result)

    def test_invalid_scenario_fails_closed_with_stable_response(self):
        status, _, result = self.post_json("/api/forecast", {"scenario": {"location": "Synthetic"}})
        self.assertEqual(status, 200)
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertTrue(result["human_review_required"])
        self.assertEqual(result["recommendations"], [])
        self.assertIn("missing_required_fields", result["decision_reason"])

    def test_showcase_runs_all_synthetic_cases(self):
        request = Request(f"{self.base_url}/api/showcase", method="POST", data=b"")
        with closing(urlopen(request, timeout=10)) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["case_count"], 16)
        self.assertEqual(sum(payload["decision_distribution"].values()), 16)
        self.assertEqual(sum(payload["strain_distribution"].values()), 16)
        self.assertEqual(len(payload["cases"]), 16)
        self.assertGreaterEqual(payload["p95_latency_ms"], 0)
        self.assertTrue(payload["synthetic_only"])

    def test_every_preset_loads_through_the_http_workflow(self):
        _, _, preset_payload = self.get_json("/api/presets")
        presets = preset_payload["presets"]
        self.assertEqual(len({item["id"] for item in presets}), 16)
        decisions = []
        strains = []
        for preset in presets:
            with self.subTest(preset=preset["id"]):
                status, _, result = self.post_json("/api/forecast", {"scenario": preset["scenario"]})
                self.assertEqual(status, 200)
                self.assertIn(result["decision"], {"ADVISORY", "HUMAN_REVIEW_REQUIRED", "ABSTAIN"})
                self.assertIn(result["strain"], {"low", "moderate", "high", "unknown"})
                decisions.append(result["decision"])
                strains.append(result["strain"])
        self.assertEqual({decision: decisions.count(decision) for decision in set(decisions)}, {
            "ADVISORY": 2,
            "HUMAN_REVIEW_REQUIRED": 12,
            "ABSTAIN": 2,
        })
        self.assertEqual({strain: strains.count(strain) for strain in set(strains)}, {
            "low": 2,
            "moderate": 7,
            "high": 5,
            "unknown": 2,
        })

    def test_cross_origin_post_is_rejected(self):
        request = Request(
            f"{self.base_url}/api/forecast",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": "https://example.com"},
        )
        try:
            urlopen(request, timeout=3)
        except HTTPError as error:
            self.assertEqual(error.code, 403)
            error.close()
        else:
            self.fail("Expected a cross-origin request to be rejected")

    def test_other_loopback_port_is_not_treated_as_same_origin(self):
        request = Request(
            f"{self.base_url}/api/forecast",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:65534"},
        )
        try:
            urlopen(request, timeout=3)
        except HTTPError as error:
            self.assertEqual(error.code, 403)
            error.close()
        else:
            self.fail("Expected a different loopback origin to be rejected")

    def test_wrong_host_header_is_rejected(self):
        status, _, payload = self.raw_request(
            "GET",
            "/api/health",
            headers={"Host": "example.com"},
            skip_host=True,
        )
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "local_host_required")

    def test_unknown_and_path_traversal_routes_are_not_served(self):
        for path in ("/unknown", "/assets/../gui.py", "/%2e%2e/%2e%2e/etc/passwd"):
            with self.subTest(path=path):
                try:
                    urlopen(f"{self.base_url}{path}", timeout=3)
                except HTTPError as error:
                    payload = json.loads(error.read())
                    self.assertEqual(error.code, 404)
                    self.assertEqual(payload["error"], "not_found")
                    error.close()
                else:
                    self.fail("Expected an unapproved route to return 404")

    def test_oversized_request_is_rejected(self):
        body = json.dumps({"padding": "x" * (65 * 1024)}).encode("utf-8")
        status, headers, payload = self.raw_request(
            "POST",
            "/api/forecast",
            body,
            {"Content-Type": "application/json"},
        )
        self.assertEqual(status, 413)
        self.assertEqual(payload["error"], "request_body_too_large")
        self.assertEqual(headers["Connection"], "close")

    def test_malformed_requests_return_stable_errors(self):
        cases = [
            (b"{}", {"Content-Type": "text/plain"}, "content_type_must_be_application_json"),
            (b"{bad", {"Content-Type": "application/json"}, "invalid_json"),
            (b"[]", {"Content-Type": "application/json"}, "request_body_must_be_an_object"),
        ]
        for body, headers, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                status, _, payload = self.raw_request("POST", "/api/forecast", body, headers)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"], expected_error)

    def test_empty_and_invalid_content_lengths_are_rejected(self):
        cases = [
            ({"Content-Type": "application/json"}, "request_body_required"),
            ({"Content-Type": "application/json", "Content-Length": "-1"}, "request_body_required"),
            ({"Content-Type": "application/json", "Content-Length": "not-a-number"}, "invalid_content_length"),
        ]
        for headers, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                status, _, payload = self.raw_request("POST", "/api/forecast", b"", headers)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"], expected_error)

    def test_valid_same_origin_request_is_accepted(self):
        _, _, preset_payload = self.get_json("/api/presets")
        body = json.dumps({"scenario": preset_payload["presets"][0]["scenario"]}).encode("utf-8")
        status, _, result = self.raw_request(
            "POST",
            "/api/forecast",
            body,
            {"Content-Type": "application/json", "Origin": self.base_url},
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["decision"], "ADVISORY")

    def test_concurrent_forecasts_return_unique_runs(self):
        _, _, preset_payload = self.get_json("/api/presets")
        scenario = preset_payload["presets"][0]["scenario"]

        def run_once(_: int):
            return self.post_json("/api/forecast", {"scenario": scenario})[2]

        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(run_once, range(20)))
        self.assertTrue(all(result["decision"] == "ADVISORY" for result in results))
        self.assertEqual(len({result["run_id"] for result in results}), 20)

    def test_unexpected_forecast_failure_returns_stable_json(self):
        _, _, preset_payload = self.get_json("/api/presets")
        with patch("responder_forecaster.gui.run_forecast", side_effect=RuntimeError("synthetic failure")):
            try:
                self.post_json("/api/forecast", {"scenario": preset_payload["presets"][0]["scenario"]})
            except HTTPError as error:
                payload = json.loads(error.read())
                self.assertEqual(error.code, 500)
                self.assertEqual(payload["error"], "unexpected_server_failure")
                error.close()
            else:
                self.fail("Expected unexpected failures to return a stable 500 response")

    def test_concurrency_limit_returns_retryable_busy_response(self):
        acquired = 0
        try:
            for _ in range(MAX_CONCURRENT_REQUESTS):
                self.assertTrue(self.server.request_slots.acquire(blocking=False))
                acquired += 1
            try:
                urlopen(f"{self.base_url}/api/health", timeout=3)
            except HTTPError as error:
                payload = json.loads(error.read())
                self.assertEqual(error.code, 429)
                self.assertEqual(payload["error"], "server_busy")
                self.assertEqual(error.headers["Retry-After"], "1")
                error.close()
            else:
                self.fail("Expected the bounded server to return 429 when all request slots are occupied")
        finally:
            for _ in range(acquired):
                self.server.request_slots.release()

    def test_showcase_loader_fails_loudly_on_bad_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "01_bad.json").write_text("{not-json", encoding="utf-8")
            with patch("responder_forecaster.gui.SHOWCASE_ROOT", root):
                with self.assertRaisesRegex(ValueError, "showcase_preset_unreadable: 01_bad.json"):
                    load_showcase_presets()

    def test_showcase_loader_rejects_nonobject_and_unlabeled_cases(self):
        variants = [
            ("[]", "showcase_preset_must_be_an_object"),
            (json.dumps({"scenario_status": "Public team-level data"}), "showcase_preset_must_be_explicitly_synthetic"),
        ]
        for contents, expected in variants:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "01_bad.json").write_text(contents, encoding="utf-8")
                with patch("responder_forecaster.gui.SHOWCASE_ROOT", root):
                    with self.assertRaisesRegex(ValueError, expected):
                        load_showcase_presets()


if __name__ == "__main__":
    unittest.main()
