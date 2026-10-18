#!/usr/bin/env python3
"""Collect real public project screenshots; every result still needs visual review."""
import argparse
import base64
import hashlib
import html
import io
import ipaddress
import json
import re
import socket
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 12 * 1024 * 1024
HTTP_TIMEOUT = 15
Image = None


class MissingDependency(RuntimeError):
    pass


@lru_cache(maxsize=512)
def public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Only public HTTP(S) URLs are supported")
    if parts.username or parts.password:
        raise ValueError("URLs containing credentials are not supported")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Local or private network URLs are not supported")
    return url


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, public_url(newurl))


def fetch(url):
    request = Request(public_url(url), headers={"User-Agent": "GitHub-Treasure-Screenshots/1.0"})
    with build_opener(PublicRedirect()).open(request, timeout=HTTP_TIMEOUT) as response:
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("Download exceeds 12 MiB")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Download exceeds 12 MiB")
        return data, response.url


def inspect_image(data):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as picture:
            width, height = picture.size
            suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "GIF": ".gif"}.get(picture.format)
            if not suffix or width < 240 or height < 120:
                raise ValueError("Not a supported screenshot (PNG/JPEG/WebP/GIF, minimum 240×120)")
            picture.verify()
        with Image.open(io.BytesIO(data)) as picture:
            picture.load()
    return width, height, suffix


def readme_images(repo):
    data, _ = fetch(f"https://api.github.com/repos/{repo}/readme")
    info = json.loads(data)
    base = info.get("download_url")
    if not base:
        raise ValueError("README has no download_url")
    if info.get("encoding") == "base64" and info.get("content"):
        markdown = base64.b64decode(info["content"]).decode("utf-8", errors="replace")
    else:
        markdown = fetch(base)[0].decode("utf-8", errors="replace")
    definitions = dict((m[0].strip().lower(), m[1].strip("<>")) for m in re.findall(
        r'^\s{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)', markdown, re.M))
    images = [(alt, target.strip("<>")) for alt, target in re.findall(
        r'!\[([^\]]*)\]\(\s*(<[^>]+>|[^\s)]+)(?:[^)]*)\)', markdown)]
    for alt, key in re.findall(r'!\[([^\]]*)\]\[([^\]]*)\]', markdown):
        if (key or alt).strip().lower() in definitions:
            images.append((alt, definitions[(key or alt).strip().lower()]))
    for alt in re.findall(r'!\[([^\]]+)\](?![\[(])', markdown):
        if alt.strip().lower() in definitions:
            images.append((alt, definitions[alt.strip().lower()]))
    for tag in re.findall(r'<img\b[^>]*>', markdown, re.I):
        attrs = {key.lower(): value for key, _, value in re.findall(r'([\w-]+)\s*=\s*([\x22\x27])(.*?)\2', tag)}
        if attrs.get("src"):
            images.append((attrs.get("alt", ""), attrs["src"]))
    candidates = []
    seen = set()
    for alt, target in images:
        url = urljoin(base, html.unescape(target))
        parts = urlsplit(url)
        if parts.scheme not in ("https", "http"):
            continue
        if parts.hostname == "github.com" and "/blob/" in parts.path:
            url = "https://raw.githubusercontent.com" + parts.path.replace("/blob/", "/", 1)
        description = (alt + " " + url).lower()
        if re.search(r'shields\.io|badgen\.|badge|(?:^|[/_\s-])(logo|icon|avatar|sponsor|star-history)(?:[./_\s-]|$)', description):
            continue
        if url in seen:
            continue
        seen.add(url)
        score = sum(word in description for word in ("screenshot", "screen-shot", "preview", "demo", "interface", "截图", "界面"))
        candidates.append((score, url))
    return [url for _, url in sorted(candidates, key=lambda item: -item[0])][:3]


def capture_demo(url, selector, channel):
    public_url(url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise MissingDependency("Install browser fallback: python -m pip install playwright; python -m playwright install chromium") from exc
    try:
        with sync_playwright() as playwright:
            options = {"headless": True}
            if channel:
                options["channel"] = channel
            with playwright.chromium.launch(**options) as browser:
                context = browser.new_context(viewport={"width": 1440, "height": 900}, service_workers="block", accept_downloads=False)
                def route_request(route):
                    try:
                        public_url(route.request.url)
                    except (ValueError, OSError):
                        route.abort()
                    else:
                        route.continue_()
                context.route("**/*", route_request)
                page = context.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=25000)
                if response is not None and response.status >= 400:
                    raise ValueError(f"Demo returned HTTP {response.status}; no screenshot taken")
                page.wait_for_timeout(750)
                title = page.title()
                if re.search(r'captcha|verify.*human|sign.?in|log.?in|登录|安全验证', title, re.I) or page.locator('input[type="password"]').count():
                    raise ValueError("Demo requires login or verification; no screenshot taken")
                if page.locator('iframe[src*="captcha"], iframe[src*="challenges.cloudflare.com"]').count():
                    raise ValueError("Demo contains a verification challenge; no screenshot taken")
                if selector:
                    data = page.locator(selector).first.screenshot(timeout=12000)
                else:
                    data = page.screenshot(full_page=False, timeout=12000)
                return data, page.url
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "distribution" in str(exc) and "not found" in str(exc):
            raise MissingDependency("Browser unavailable. Install selected Chrome/Edge or run: python -m playwright install chromium") from exc
        raise


def collect(item, output, refresh, channel):
    started = time.monotonic()
    result = {"repo": item["repo"], "status": "failed", "source_kind": None, "source_url": None, "image_path": None,
              "width": None, "height": None, "elapsed_seconds": 0, "error": None, "needs_visual_review": True}
    key = hashlib.sha256(json.dumps({**item, "channel": channel}, sort_keys=True).encode()).hexdigest()[:16]
    stem = item["repo"].replace("/", "--") + "-" + key
    cache = output / (stem + ".json")
    errors = []
    try:
        if not refresh and cache.exists():
            try:
                saved = json.loads(cache.read_text(encoding="utf-8"))
                path = Path(saved["image_path"])
                if path.resolve().parent != output or path.stat().st_size > MAX_BYTES:
                    raise ValueError("Invalid cached image path or size")
                width, height, _ = inspect_image(path.read_bytes())
                result.update(saved, status="cached", width=width, height=height, error=None)
                return result
            except Exception:
                pass
        candidates = [item["image_url"]] if item.get("image_url") else []
        if not candidates:
            try:
                candidates = readme_images(item["repo"])
            except Exception as exc:
                errors.append("README: " + str(exc))
        payload = None
        source_kind = "official_image"
        for url in candidates:
            try:
                data, source = fetch(url)
                dimensions = inspect_image(data)
                payload = data, source, dimensions
                break
            except Exception as exc:
                errors.append(f"Image {url}: {exc}")
        if payload is None and item.get("demo_url"):
            data, source = capture_demo(item["demo_url"], item.get("selector"), channel)
            payload = data, source, inspect_image(data)
            source_kind = "demo_capture"
        if payload is None:
            raise ValueError("; ".join(errors) or "No usable README screenshot found; provide image_url or demo_url")
        data, source, (width, height, suffix) = payload
        path = output / (stem + suffix)
        path.write_bytes(data)
        result.update(status="captured" if source_kind == "demo_capture" else "downloaded", source_kind=source_kind,
                      source_url=source, image_path=str(path), width=width, height=height)
        cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except MissingDependency as exc:
        result.update(status="dependency_error", error=str(exc))
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["needs_visual_review"] = True
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON array of {repo, image_url?, demo_url?, selector?}")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=3, help="Concurrent projects (default: 3)")
    parser.add_argument("--refresh", action="store_true", help="Ignore validated local image cache")
    parser.add_argument("--browser-channel", choices=("chrome", "msedge"), help="Optional installed browser; otherwise Playwright Chromium")
    args = parser.parse_args()
    try:
        items = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if not isinstance(items, list) or not items or not 1 <= args.workers <= 16:
            raise ValueError("Input must be a nonempty array; workers must be 1–16")
        seen = set()
        for item in items:
            if not isinstance(item, dict) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', item.get("repo", "")):
                raise ValueError("Each item needs repo in owner/repository format")
            if item["repo"].lower() in seen:
                raise ValueError("Duplicate repositories are not supported")
            seen.add(item["repo"].lower())
            for key in ("image_url", "demo_url", "selector"):
                if key in item and (not isinstance(item[key], str) or not item[key].strip()):
                    raise ValueError(f"{key} must be a nonempty string when provided")
            if item.get("selector") and not item.get("demo_url"):
                raise ValueError("selector requires demo_url")
            for key in ("image_url", "demo_url"):
                if item.get(key):
                    parts = urlsplit(item[key])
                    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
                        raise ValueError(f"{key} must be a public HTTP(S) URL without credentials")
        global Image
        try:
            from PIL import Image
        except ImportError as exc:
            raise MissingDependency("Install required image validation: python -m pip install Pillow") from exc
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        marker = output / ".github-treasure-work"
        if not marker.exists() and not any(output.iterdir()):
            marker.write_text("GitHub Treasure generated work files\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, MissingDependency) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(lambda item: collect(item, output, args.refresh, args.browser_channel), items))
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest_path": str(manifest), "results": results}, ensure_ascii=False, indent=2))
    return 2 if any(r["status"] == "dependency_error" for r in results) else int(any(r["status"] == "failed" for r in results))


if __name__ == "__main__":
    sys.exit(main())
