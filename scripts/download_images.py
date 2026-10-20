"""
Bulk Image Downloader
=====================
Reads a locally saved HTML file (your task email page),
extracts all image URLs, and downloads them all in parallel.

Usage:
    python scripts/download_images.py --html "path/to/your/saved_page.html" --out "data/images"

Or if you have a direct URL (no login needed):
    python scripts/download_images.py --url "https://example.com/task-page" --out "data/images"
"""

import os
import re
import sys
import time
import argparse
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MAX_WORKERS = 10          # parallel downloads at once
TIMEOUT     = 30          # seconds per request
HEADERS     = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ─────────────────────────────────────────────
# STEP 1 — Load HTML (local file or live URL)
# ─────────────────────────────────────────────
def load_html(html_path: str = None, url: str = None) -> tuple[str, str]:
    """Returns (html_content, base_url)."""
    if html_path:
        path = Path(html_path)
        if not path.exists():
            print(f"[ERROR] File not found: {html_path}")
            sys.exit(1)
        print(f"[INFO] Reading local HTML: {path.resolve()}")
        return path.read_text(encoding="utf-8", errors="ignore"), path.as_uri()
    elif url:
        print(f"[INFO] Fetching URL: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text, url
    else:
        print("[ERROR] Provide either --html or --url")
        sys.exit(1)


# ─────────────────────────────────────────────
# STEP 2 — Extract all image URLs from HTML
# ─────────────────────────────────────────────
def extract_image_urls(html: str, base_url: str) -> list[str]:
    """Parse HTML and collect every image src / anchor href that looks like an image."""
    soup = BeautifulSoup(html, "html.parser")
    urls = set()

    # <img src="...">
    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or tag.get("data-original")
        if src:
            urls.add(urljoin(base_url, src))

    # <a href="...jpg"> — clickable download links
    img_extensions = re.compile(r"\.(jpg|jpeg|png|gif|webp|bmp|tiff?)(\?.*)?$", re.IGNORECASE)
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if img_extensions.search(href):
            urls.add(urljoin(base_url, href))

    # Also scan raw text for blob: or https: image links (some email clients embed them)
    raw_links = re.findall(
        r'https?://[^\s\'"<>]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s\'"<>]*)?',
        html, re.IGNORECASE
    )
    urls.update(raw_links)

    image_urls = sorted(urls)
    print(f"[INFO] Found {len(image_urls)} image URL(s)")
    return image_urls


# ─────────────────────────────────────────────
# STEP 3 — Download a single image
# ─────────────────────────────────────────────
def download_image(url: str, out_dir: Path, idx: int, total: int) -> str:
    """Download one image. Returns status string."""
    try:
        # Derive filename from URL
        parsed   = urlparse(url)
        filename = Path(parsed.path).name
        if not filename or "." not in filename:
            filename = f"image_{idx:04d}.jpg"

        out_path = out_dir / filename

        # Skip if already downloaded
        if out_path.exists():
            return f"[SKIP] ({idx}/{total}) Already exists: {filename}"

        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()

        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        return f"[OK]   ({idx}/{total}) {filename}"

    except Exception as e:
        return f"[FAIL] ({idx}/{total}) {url} — {e}"


# ─────────────────────────────────────────────
# STEP 4 — Bulk parallel download
# ─────────────────────────────────────────────
def bulk_download(urls: list[str], out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    total    = len(urls)
    success  = 0
    failed   = 0
    skipped  = 0
    start    = time.time()

    print(f"\n[START] Downloading {total} images → {out_dir.resolve()}")
    print(f"        Using {MAX_WORKERS} parallel threads\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_image, url, out_dir, i + 1, total): url
            for i, url in enumerate(urls)
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
    print(f"\n{'='*55}")
    print(f"  ✅ Downloaded : {success}")
    print(f"  ⏭  Skipped   : {skipped}")
    print(f"  ❌ Failed     : {failed}")
    print(f"  ⏱  Time      : {elapsed:.1f}s")
    print(f"  📁 Saved to  : {out_dir.resolve()}")
    print(f"{'='*55}\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Bulk image downloader from HTML page")
    parser.add_argument("--html",    help="Path to locally saved HTML file")
    parser.add_argument("--url",     help="Live URL of the page (if no login needed)")
    parser.add_argument("--out",     default="data/images", help="Output folder (default: data/images)")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Parallel threads (default: 10)")
    args = parser.parse_args()

    global MAX_WORKERS
    MAX_WORKERS = args.workers

    html, base_url = load_html(html_path=args.html, url=args.url)
    urls = extract_image_urls(html, base_url)

    if not urls:
        print("[WARN] No image URLs found. The page may require login or use JavaScript rendering.")
        print("       Try: Save the page as 'Complete Webpage' (Ctrl+S in browser) and use --html")
        sys.exit(0)

    bulk_download(urls, Path(args.out))


if __name__ == "__main__":
    main()
