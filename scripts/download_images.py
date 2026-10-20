"""
Bulk Image Downloader
=====================
Reads a locally saved HTML file or a publicly accessible URL,
extracts image URLs, and downloads them in parallel.

Usage:
    python scripts/download_images.py --html "path/to/saved_page.html" --out "data/images"

    python scripts/download_images.py --url "https://example.com/task-page" --out "data/images"
"""

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# CONFIG
MAX_WORKERS = 10
TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

IMAGE_EXTENSIONS = re.compile(
    r"\.(jpg|jpeg|png|gif|webp|bmp|tiff?)(\?.*)?$",
    re.IGNORECASE,
)


def load_html(html_path: str | None = None, url: str | None = None) -> tuple[str, str]:
    """Return (HTML content, base URL)."""

    if html_path:
        path = Path(html_path)

        if not path.exists():
            print(f"[ERROR] File not found: {html_path}")
            sys.exit(1)

        print(f"[INFO] Reading local HTML: {path.resolve()}")
        return path.read_text(encoding="utf-8", errors="ignore"), path.resolve().as_uri()

    if url:
        print(f"[INFO] Fetching URL: {url}")
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text, url

    print("[ERROR] Provide either --html or --url")
    sys.exit(1)


def extract_image_urls(html: str, base_url: str) -> list[str]:
    """Extract image URLs from HTML image tags, links, and raw HTML text."""

    soup = BeautifulSoup(html, "html.parser")
    urls = set()

    # Images in <img> tags
    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or tag.get("data-original")

        if src and not src.startswith("data:"):
            urls.add(urljoin(base_url, src))

    # Links that point directly to image files
    for tag in soup.find_all("a", href=True):
        href = tag["href"]

        if IMAGE_EXTENSIONS.search(href):
            urls.add(urljoin(base_url, href))

    # Image URLs written directly in the HTML source
    raw_pattern = (
        r"""https?://[^\s"'<>]+?\.(?:jpg|jpeg|png|gif|webp|bmp|tiff?)(?:\?[^\s"'<>]*)?"""
    )

    for match in re.findall(raw_pattern, html, re.IGNORECASE):
        urls.add(match.rstrip(".,);"))

    image_urls = sorted(urls)
    print(f"[INFO] Found {len(image_urls)} image URL(s)")
    return image_urls


def download_image(url: str, out_dir: Path, idx: int, total: int) -> str:
    """Download one image and return a status message."""

    try:
        parsed = urlparse(url)
        filename = Path(parsed.path).name

        if not filename or "." not in filename:
            filename = f"image_{idx:04d}.jpg"

        # Remove filename characters that are invalid on Windows
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        out_path = out_dir / filename

        if out_path.exists():
            return f"[SKIP] ({idx}/{total}) Already exists: {filename}"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            stream=True,
        )
        response.raise_for_status()

        # Avoid saving HTML error pages as images
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and not (
            content_type.startswith("image/")
            or content_type == "application/octet-stream"
        ):
            return f"[FAIL] ({idx}/{total}) Not an image response: {url}"

        with response, open(out_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)

        return f"[OK] ({idx}/{total}) {filename}"

    except Exception as exc:
        return f"[FAIL] ({idx}/{total}) {url} — {exc}"


def bulk_download(urls: list[str], out_dir: Path) -> None:
    """Download URLs in parallel and print a summary."""

    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(urls)
    success = 0
    failed = 0
    skipped = 0
    start = time.time()

    print(f"\n[START] Downloading {total} images -> {out_dir.resolve()}")
    print(f"Using {MAX_WORKERS} parallel threads\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_image, url, out_dir, index + 1, total): url
            for index, url in enumerate(urls)
        }

        for future in as_completed(futures):
            result = future.result()
            print(result)

            if result.startswith("[OK]"):
                success += 1
            elif result.startswith("[SKIP]"):
                skipped += 1
            else:
                failed += 1

    elapsed = time.time() - start

    print("\n" + "=" * 55)
    print(f"Downloaded : {success}")
    print(f"Skipped    : {skipped}")
    print(f"Failed     : {failed}")
    print(f"Time       : {elapsed:.1f}s")
    print(f"Saved to   : {out_dir.resolve()}")
    print("=" * 55)


def main() -> None:
    global MAX_WORKERS

    parser = argparse.ArgumentParser(
        description="Bulk image downloader from an HTML page"
    )
    parser.add_argument("--html", help="Path to a locally saved HTML file")
    parser.add_argument("--url", help="Public URL of a page that needs no login")
    parser.add_argument(
        "--out",
        default="data/images",
        help="Output directory (default: data/images)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help="Number of parallel downloads (default: 10)",
    )

    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be at least 1")

    MAX_WORKERS = args.workers

    html, base_url = load_html(html_path=args.html, url=args.url)
    urls = extract_image_urls(html, base_url)

    if not urls:
        print(
            "[WARN] No image URLs found. The page may require login "
            "or JavaScript rendering."
        )
        print(
            "Try saving the page with Ctrl+S and selecting "
            "'Complete Webpage', then use --html."
        )
        return

    bulk_download(urls, Path(args.out))


if __name__ == "__main__":
    main()
