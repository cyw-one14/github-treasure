"""Offline behavioral checks for the optional screenshot collector."""
import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project_screenshots.py"
SPEC = importlib.util.spec_from_file_location("project_screenshots", SCRIPT)
screenshots = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(screenshots)
screenshots.Image = Image


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (480, 270), "#254b7c").save(buffer, format="PNG")
    return buffer.getvalue()


class ScreenshotCollectorTests(unittest.TestCase):
    def setUp(self):
        self.network_guard = patch.object(screenshots.socket, "getaddrinfo", side_effect=AssertionError("Unexpected network access"))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)
        self.png = png_bytes()

    def readme_candidates(self, markdown):
        document = {
            "download_url": "https://raw.githubusercontent.com/example/tool/main/docs/README.md",
            "encoding": "base64",
            "content": base64.b64encode(markdown.encode()).decode(),
        }
        with patch.object(screenshots, "fetch", return_value=(json.dumps(document).encode(), "unused")) as fetch:
            result = screenshots.readme_images("example/tool")
            fetch.assert_called_once_with("https://api.github.com/repos/example/tool/readme")
            return result

    def test_readme_resolves_real_image_paths_and_filters_badges(self):
        markdown = """
![build](https://img.shields.io/github/actions/workflow/status/example/tool/ci.yml)
![logo](./assets/logo.png)
![screenshot](./assets/screen.png)
![preview][dashboard]
[dashboard]: ../media/reference.png "Dashboard"
<img alt='interface' src='images/html.png?one=1&amp;two=2'>
"""
        self.assertEqual(self.readme_candidates(markdown), [
            "https://raw.githubusercontent.com/example/tool/main/docs/assets/screen.png",
            "https://raw.githubusercontent.com/example/tool/main/media/reference.png",
            "https://raw.githubusercontent.com/example/tool/main/docs/images/html.png?one=1&two=2",
        ])

    def test_readme_accepts_collapsed_and_shortcut_image_references(self):
        for reference in ("![preview][]", "![preview]"):
            with self.subTest(reference=reference):
                self.assertEqual(self.readme_candidates(reference + "\n[preview]: ../shot.png"), [
                    "https://raw.githubusercontent.com/example/tool/main/shot.png",
                ])

    def test_image_validation_rejects_html_and_truncated_images(self):
        self.assertEqual(screenshots.inspect_image(self.png), (480, 270, ".png"))
        for payload in (b"<!doctype html><html>Access denied</html>", self.png[:len(self.png) // 2]):
            with self.subTest(payload=payload[:16]):
                with self.assertRaises((OSError, ValueError)):
                    screenshots.inspect_image(payload)

    def test_cache_skips_network_and_recovers_from_corrupted_image(self):
        item = {"repo": "example/tool", "image_url": "https://example.com/screenshot.png"}
        with tempfile.TemporaryDirectory(prefix="screenshots-cache-") as directory:
            output = Path(directory).resolve()
            with patch.object(screenshots, "fetch", return_value=(self.png, item["image_url"])) as fetch:
                first = screenshots.collect(item, output, False, None)
                self.assertEqual(first["status"], "downloaded", first)
                fetch.assert_called_once()
            with patch.object(screenshots, "fetch", side_effect=AssertionError("Cache hit must not fetch")) as fetch:
                cached = screenshots.collect(item, output, False, None)
                self.assertEqual(cached["status"], "cached", cached)
                fetch.assert_not_called()
                self.assertTrue(cached["needs_visual_review"])
            Path(first["image_path"]).write_bytes(b"corrupted cache")
            with patch.object(screenshots, "fetch", return_value=(self.png, item["image_url"])) as fetch:
                recovered = screenshots.collect(item, output, False, None)
                self.assertEqual(recovered["status"], "downloaded", recovered)
                fetch.assert_called_once()
                self.assertEqual(screenshots.inspect_image(Path(recovered["image_path"]).read_bytes()), (480, 270, ".png"))

    def test_one_failed_project_does_not_stop_batch(self):
        items = [
            {"repo": "example/broken", "image_url": "https://example.com/broken.png"},
            {"repo": "example/working", "image_url": "https://example.com/working.png"},
        ]
        def fake_fetch(url):
            if url.endswith("broken.png"):
                raise TimeoutError("simulated download timeout")
            return self.png, url
        with tempfile.TemporaryDirectory(prefix="screenshots-batch-") as directory:
            root = Path(directory)
            input_path = root / "projects.json"
            output = root / "screenshots"
            input_path.write_text(json.dumps(items), encoding="utf-8")
            argv = [str(SCRIPT), "--input", str(input_path), "--output-dir", str(output), "--workers", "2"]
            with patch.object(sys, "argv", argv), patch.object(screenshots, "fetch", side_effect=fake_fetch), redirect_stdout(io.StringIO()):
                code = screenshots.main()
            self.assertEqual(code, 1)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["status"] for item in manifest], ["failed", "downloaded"])
            self.assertIn("simulated download timeout", manifest[0]["error"])
            self.assertTrue(Path(manifest[1]["image_path"]).is_file())
            self.assertTrue(Path(manifest[1]["image_path"]).is_absolute())
            self.assertTrue(all(item["needs_visual_review"] for item in manifest))

    def test_demo_http_error_does_not_capture_error_page(self):
        manager = MagicMock()
        playwright = manager.__enter__.return_value
        browser = playwright.chromium.launch.return_value.__enter__.return_value
        page = browser.new_context.return_value.new_page.return_value
        page.goto.return_value.status = 404
        api = ModuleType("playwright.sync_api")
        api.sync_playwright = lambda: manager
        modules = {"playwright": ModuleType("playwright"), "playwright.sync_api": api}
        with patch.dict(sys.modules, modules), patch.object(screenshots, "public_url", side_effect=lambda url: url):
            with self.assertRaisesRegex(ValueError, "Demo returned HTTP 404"):
                screenshots.capture_demo("https://example.com/demo", None, None)
        page.screenshot.assert_not_called()
        page.wait_for_timeout.assert_not_called()
        playwright.chromium.launch.assert_called_once_with(headless=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
