"""
Tarang Pharma Receipt Downloader (v7: NO clicking)

Why v7 exists: in your runs Chrome closed itself right after a receipt button
was clicked, so any click-based approach is unreliable. v7 never clicks.

How it works:
  1. Opens Chrome with a dedicated profile and your private assignment URL.
  2. You expand the "467 photos" section (do NOT click any receipt) and
     press ENTER.
  3. The script finds the REAL storage keys (uploads/<folder>/<fileuuid>-name)
     from the data the page already loaded: network responses, page HTML and
     the page's React data. Nothing is guessed.
  4. For each key it calls the page's own resolver endpoint (same session),
     gets a short-lived signed URL, downloads the image bytes from Python,
     checks them (image header, nonzero size, file really on disk) and only
     then records the file in manifest.csv.
  5. Signed URLs, tokens and cookies are never printed or saved.

Usage (PowerShell):
    python tarang_downloader.py --discover    # find keys only, download nothing
    python tarang_downloader.py --limit 3     # test with 3 images
    python tarang_downloader.py               # everything (resumable)
"""

import argparse
import csv
import hashlib
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


ALLOWED_SCHEME = "https"
ALLOWED_HOST = "atslite.interviewgod.ai"

OUT_DIR = Path("tarang-expense-receipts")
IMG_DIR = OUT_DIR / "images"
MANIFEST = OUT_DIR / "manifest.csv"
PROFILE_DIR = Path(".playwright-chrome-profile")

MAX_RECOVERIES = 3
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"}

FIELDS = [
    "index",
    "original_filename",
    "storage_key",
    "output_filename",
    "status",
    "resolve_http_status",
    "image_http_status",
    "file_size",
    "sha256",
    "note",
]

KEY_RE = re.compile(
    r"uploads/[^/\"'\\<>\s]+/[^\"'\\<>\s]+?\.(?:jpe?g|png|webp|gif|bmp|heic)",
    re.IGNORECASE,
)
UUID_PREFIX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}-"
)

# Walks the React fibers above every receipt button and collects any string
# that looks like a storage key (props and hook state). Read-only.
JS_FIBER_KEYS = r"""
() => {
  const KEYRE = /uploads\/[^\/"'\\<>\s]+\/[^"'\\<>\s]+?\.(?:jpe?g|png|webp|gif|bmp|heic)/i;
  const out = [], seenKeys = new Set(), seen = new WeakSet();
  let budget = 400000;
  const visit = (v, depth) => {
    if (budget-- <= 0 || v == null) return;
    const t = typeof v;
    if (t === 'string') {
      const m = v.match(KEYRE);
      if (m && !seenKeys.has(m[0])) { seenKeys.add(m[0]); out.push(m[0]); }
      return;
    }
    if (t !== 'object' || depth > 5) return;
    if (seen.has(v)) return;
    seen.add(v);
    try {
      if (v.$$typeof || v.nodeType || v === window) return;
      if (Array.isArray(v)) { for (const x of v) visit(x, depth + 1); return; }
      for (const k of Object.keys(v)) {
        if (k === '_owner' || k === '_store' || k === 'ref') continue;
        visit(v[k], depth + 1);
      }
    } catch (e) {}
  };
  const buttons = [...document.querySelectorAll('button')]
    .filter(b => /^\s*images\//i.test(b.innerText));
  for (const b of buttons) {
    const fk = Object.keys(b).find(k => k.startsWith('__reactFiber$'));
    let f = fk ? b[fk] : null;
    for (let up = 0; f && up < 14; up++, f = f.return) {
      try { visit(f.memoizedProps, 0); } catch (e) {}
      try {
        let h = f.memoizedState, hops = 0;
        while (h && typeof h === 'object' && hops++ < 60) {
          visit(h.memoizedState !== undefined ? h.memoizedState : h, 0);
          h = h.next;
        }
      } catch (e) {}
    }
  }
  return out;
}
"""

JS_BUTTON_NAMES = r"""
() => [...document.querySelectorAll('button')]
  .map(b => b.innerText.trim())
  .filter(t => /^images\//i.test(t))
"""

JS_RESOLVE = r"""
async ([endpoint, key]) => {
  try {
    const r = await fetch(endpoint + '?key=' + encodeURIComponent(key),
                          { credentials: 'same-origin' });
    let url = null;
    try { const j = await r.json(); if (j && typeof j.url === 'string') url = j.url; } catch (e) {}
    return { status: r.status, url: url };
  } catch (e) {
    return { status: 0, url: null };
  }
}
"""


# -- helpers ---------------------------------------------------------------

def looks_like_image(data: bytes) -> bool:
    return (
        data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        or data.startswith((b"GIF87a", b"GIF89a"))
        or data.startswith(b"BM")
        or data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1")
    )


def is_closed_error(exc: Exception) -> bool:
    return type(exc).__name__ == "TargetClosedError"


def key_filename(key: str) -> str:
    """<fileuuid>-IMG-....jpg"""
    return key.rsplit("/", 1)[-1]


def display_name(key: str) -> str:
    """IMG-....jpg (the name shown on the page)"""
    return UUID_PREFIX.sub("", key_filename(key))


def keys_from_text(text: str):
    return [m.group(0) for m in KEY_RE.finditer(text.replace("\\/", "/"))]


def mask_path(url: str) -> str:
    path = urlparse(url).path
    path = re.sub(r"eyJ[\w-]+\.[\w-]+\.[\w-]+", "<TOKEN>", path)
    return re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", "<UUID>", path)


def ensure_directories():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST.exists():
        with MANIFEST.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def write_manifest(rows):
    ensure_directories()

    def order(r):
        try:
            return int(r.get("index", 0))
        except (TypeError, ValueError):
            return 0

    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in sorted(rows.values(), key=order):
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def load_previous():
    """Verified rows from an earlier run, keyed by storage key."""
    rows = {}
    if not MANIFEST.exists():
        return rows
    try:
        with MANIFEST.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = row.get("storage_key", "")
                filename = row.get("output_filename", "")
                path = IMG_DIR / filename if filename else None
                if (
                    key
                    and row.get("status") in ("downloaded", "duplicate_content")
                    and path is not None
                    and path.is_file()
                    and path.stat().st_size > 0
                ):
                    rows[key] = row
    except (OSError, csv.Error):
        print("Warning: existing manifest could not be read.")
    return rows


def existing_files_by_keyname():
    """Files already in the images folder named NNN_<fileuuid>-name.jpg."""
    found = {}
    for p in IMG_DIR.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and p.stat().st_size > 0:
            m = re.match(r"^\d+_(.+)$", p.name)
            if m:
                found[m.group(1)] = p
    return found


# -- browser session -------------------------------------------------------

class Session:
    def __init__(self, playwright, task_url, channel, headless):
        self.pw = playwright
        self.task_url = task_url
        self.channel = channel
        self.headless = headless
        self.context = None
        self.page = None
        self.collecting = True
        self.requests = []
        self.responses = []

    def _on_request(self, r):
        if self.collecting and "/uploads/resolve" in r.url:
            self.requests.append(r.url)

    def _on_response(self, r):
        if self.collecting:
            try:
                self.responses.append((r.url, r.status, r.headers.get("content-type", ""), r))
            except Exception:
                pass

    def open(self, prompt=True):
        kwargs = dict(headless=self.headless, accept_downloads=True,
                      viewport={"width": 1400, "height": 900})
        if self.channel:
            kwargs["channel"] = self.channel
        self.context = self.pw.chromium.launch_persistent_context(str(PROFILE_DIR), **kwargs)
        self.context.on("request", self._on_request)
        self.context.on("response", self._on_response)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.goto(self.task_url, wait_until="domcontentloaded", timeout=60000)
        if prompt:
            input(
                "\nIn Chrome: log in if needed, then expand the '467 photos' section.\n"
                "Do NOT click any receipt. Then press ENTER here... "
            )
        else:
            self.page.wait_for_timeout(2500)

    def alive(self) -> bool:
        try:
            return (not self.page.is_closed()) and bool(self.context.pages)
        except Exception:
            return False

    def close_quietly(self):
        try:
            if self.context is not None:
                self.context.close()
        except Exception:
            pass


# -- discovery -------------------------------------------------------------

def discover_keys(session):
    page = session.page
    page.wait_for_timeout(1000)  # let queued browser events arrive

    sources = {"network": [], "html": [], "react": [], "resolver_requests": []}

    for url in session.requests:
        q = parse_qs(urlparse(url).query).get("key")
        if q:
            sources["resolver_requests"].append(q[0])

    for url, status, ctype, resp in session.responses:
        if status != 200 or urlparse(url).path.startswith("/_next/static"):
            continue
        if not any(t in ctype for t in ("json", "text", "javascript", "x-component")):
            continue
        try:
            body = resp.text()
        except Exception:
            continue
        if "uploads" in body:
            sources["network"].extend(keys_from_text(body))

    try:
        sources["html"] = keys_from_text(page.content())
    except Exception as exc:
        if is_closed_error(exc):
            raise

    try:
        sources["react"] = [k for k in page.evaluate(JS_FIBER_KEYS) if KEY_RE.fullmatch(k)]
    except Exception as exc:
        if is_closed_error(exc):
            raise

    ordered, seen = [], set()
    for name in ("network", "html", "react", "resolver_requests"):
        for k in sources[name]:
            if k not in seen:
                seen.add(k)
                ordered.append(k)

    return ordered, {n: len(set(v)) for n, v in sources.items()}


def reconcile(keys, button_names):
    """Pick the keys that belong to the receipt buttons on the page."""
    if not button_names:
        return list(keys), [], []
    allowed = Counter(n.split("/")[-1] for n in button_names)
    selected, extra = [], []
    for k in keys:
        n = display_name(k)
        if allowed[n] > 0:
            allowed[n] -= 1
            selected.append(k)
        else:
            extra.append(k)
    missing = [n for n, c in allowed.items() for _ in range(c)]
    return selected, extra, missing


def derive_endpoint(task_url, requests):
    for u in requests:
        path = urlparse(u).path
        if path.endswith("/uploads/resolve"):
            return path, "learned from the page"
    token = urlparse(task_url).path.split("/track/", 1)[1].strip("/")
    return f"/api/track/{token}/uploads/resolve", "derived from your URL"


def resolve(page, endpoint, key):
    res = page.evaluate(JS_RESOLVE, [endpoint, key])
    return res.get("status", 0), res.get("url")


# -- downloading -----------------------------------------------------------

def download_key(session, endpoint, key, position, seen_hashes, retries, adoptable):
    row = {
        "index": position,
        "original_filename": "images/" + display_name(key),
        "storage_key": key,
        "output_filename": "",
        "status": "failed",
        "resolve_http_status": "",
        "image_http_status": "",
        "file_size": 0,
        "sha256": "",
        "note": "",
    }

    # Reuse a valid file from an earlier run instead of downloading it again.
    old = adoptable.get(key_filename(key))
    if old is not None:
        try:
            data = old.read_bytes()
        except OSError:
            data = b""
        if data and looks_like_image(data):
            digest = hashlib.sha256(data).hexdigest()
            dup = digest in seen_hashes
            seen_hashes.add(digest)
            row.update(output_filename=old.name, file_size=len(data), sha256=digest,
                       status="duplicate_content" if dup else "downloaded",
                       note="adopted_existing_file")
            return row

    for attempt in range(1, retries + 1):
        try:
            status, signed = resolve(session.page, endpoint, key)
            row["resolve_http_status"] = status
            if status != 200:
                row["note"] = "resolver_http_error"
            elif not signed:
                row["note"] = "resolver_missing_url"
            else:
                # Signed URL is used immediately and never printed or saved.
                response = session.context.request.get(signed, timeout=60000)
                row["image_http_status"] = response.status
                if response.status != 200:
                    row["note"] = "image_http_error"
                else:
                    data = response.body()
                    if not data:
                        row["note"] = "empty_image_body"
                    elif not looks_like_image(data):
                        row["note"] = "response_not_image"
                    else:
                        name = f"{position:03d}_{key_filename(key)}"
                        name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
                        dest = IMG_DIR / name
                        tmp = dest.with_suffix(dest.suffix + ".part")
                        tmp.write_bytes(data)
                        tmp.replace(dest)
                        if not dest.is_file() or dest.stat().st_size != len(data):
                            row["note"] = "file_write_verification_failed"
                        else:
                            digest = hashlib.sha256(data).hexdigest()
                            dup = digest in seen_hashes
                            seen_hashes.add(digest)
                            row.update(
                                output_filename=name,
                                file_size=dest.stat().st_size,
                                sha256=digest,
                                status="duplicate_content" if dup else "downloaded",
                                note="same_content_as_prior_image" if dup else "",
                            )
                            return row
        except PlaywrightTimeoutError:
            row["note"] = "timeout"
        except Exception as exc:
            if is_closed_error(exc):
                raise
            row["note"] = f"{type(exc).__name__}_attempt_{attempt}"

        if attempt < retries:
            session.page.wait_for_timeout(700 * attempt)

    return row


# -- main ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Download receipt images (no clicking).")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only the first N receipts (test run); 0 = all.")
    parser.add_argument("--discover", action="store_true",
                        help="Only find the storage keys and report; download nothing.")
    parser.add_argument("--expected", type=int, default=467)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--channel", default="chrome",
                        help="Browser channel: chrome, msedge, or chromium.")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    if args.limit < 0 or args.retries < 1:
        parser.error("--limit must be >= 0 and --retries must be >= 1")
    channel = None if args.channel == "chromium" else args.channel

    ensure_directories()
    rows = load_previous()
    seen_hashes = {r.get("sha256", "") for r in rows.values() if r.get("sha256")}
    adoptable = existing_files_by_keyname()

    task_url = os.environ.get("TARANG_URL", "").strip() or input(
        "Paste your private Tarang Pharma assignment URL: ").strip()
    parsed = urlparse(task_url)
    if (parsed.scheme != ALLOWED_SCHEME or parsed.netloc != ALLOWED_HOST
            or "/track/" not in parsed.path):
        sys.exit("Invalid URL. Use your https://atslite.interviewgod.ai/track/... link.")

    session = None
    target = []
    recoveries = 0
    exit_code = 0

    try:
        with sync_playwright() as pw:
            session = Session(pw, task_url, channel, args.headless)
            session.open(prompt=True)

            keys, source_counts = discover_keys(session)
            button_names = session.page.evaluate(JS_BUTTON_NAMES)
            selected, extra, missing_names = reconcile(keys, button_names)
            session.collecting = False
            session.responses.clear()

            print("\n---------- DISCOVERY ----------")
            print(f"Receipt buttons on page       : {len(button_names)} (expected {args.expected})")
            print(f"Keys found by source          : {source_counts}")
            print(f"Unique storage keys found     : {len(keys)}")
            print(f"Keys matching a receipt button: {len(selected)}")
            print(f"Keys not matching any button  : {len(extra)}")
            print(f"Buttons with no key found     : {len(missing_names)}")

            if not selected:
                print("\nNo storage keys could be found in the page data.")
                print("Responses seen (paths only, secrets masked):")
                shown = set()
                for url, status, ctype, _ in session.responses or []:
                    pass
                print("Please send me this output; do not send URLs or tokens.")
                exit_code = 2
                return

            if args.discover:
                print("\n--discover given: nothing downloaded.")
                return

            target = selected[:args.limit] if args.limit else selected
            pending = [k for k in target if k not in rows]

            endpoint, how = derive_endpoint(task_url, session.requests)
            if pending:
                status, signed = resolve(session.page, endpoint, pending[0])
                if status != 200 or not signed:
                    print(f"\nResolver test failed (HTTP {status}); endpoint was {how}.")
                    print("Click ONE receipt in the Chrome window so I can learn the real "
                          "endpoint, then press ENTER (or Ctrl+C to stop).")
                    session.collecting = True
                    input()
                    session.page.wait_for_timeout(1500)
                    endpoint, how = derive_endpoint(task_url, session.requests)
                    status, signed = resolve(session.page, endpoint, pending[0])
                    if status != 200 or not signed:
                        print(f"Resolver still failing (HTTP {status}). Stopping.")
                        exit_code = 3
                        return
                print(f"Resolver check OK (endpoint {how}).")

            print(f"\n---------- DOWNLOADING {len(target)} ----------")
            pos = 0
            while pos < len(target):
                key = target[pos]
                position = pos + 1
                if key in rows:
                    print(f"[{position}/{len(target)}] already_verified {display_name(key)}")
                    pos += 1
                    continue
                try:
                    if not session.alive():
                        raise RuntimeError("session_not_alive")
                    row = download_key(session, endpoint, key, position,
                                       seen_hashes, args.retries, adoptable)
                    rows[key] = row
                    write_manifest(rows)
                    print(f"[{position}/{len(target)}] {row['status']:<17} "
                          f"{display_name(key)} ({row['file_size']} bytes)")
                    pos += 1
                except Exception as exc:
                    closed = is_closed_error(exc) or str(exc) == "session_not_alive"
                    if not closed or recoveries >= MAX_RECOVERIES:
                        raise
                    recoveries += 1
                    print(f"\nChrome/tab closed (recovery {recoveries}/{MAX_RECOVERIES}). Reopening...")
                    session.close_quietly()
                    session.open(prompt=False)

    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved; run again to resume.")
    except Exception as exc:
        print(f"\nStopped due to {type(exc).__name__}. Progress saved; run again to resume.")
        exit_code = 1
    finally:
        write_manifest(rows)
        if session is not None:
            session.close_quietly()

    if args.discover or not target:
        sys.exit(exit_code)

    verified = [rows[k] for k in target if k in rows
                and rows[k].get("status") in ("downloaded", "duplicate_content")]
    downloaded = sum(r["status"] == "downloaded" for r in verified)
    duplicates = sum(r["status"] == "duplicate_content" for r in verified)
    failed = sum(1 for k in target if k in rows and rows[k].get("status") == "failed")
    missing = len(target) - len(verified)

    # Count files that are really on disk and referenced by the manifest.
    really_on_disk = sum(
        1 for r in verified
        if (IMG_DIR / r["output_filename"]).is_file()
        and (IMG_DIR / r["output_filename"]).stat().st_size > 0
    )
    folder_files = sum(
        1 for p in IMG_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and p.stat().st_size > 0
    )

    print("\n========== VERIFIED RESULT ==========")
    print(f"Run target                    : {len(target)}")
    print(f"Downloaded unique images      : {downloaded}")
    print(f"Duplicate content (kept)      : {duplicates}")
    print(f"Failed                        : {failed}")
    print(f"Missing vs run target         : {missing}")
    print(f"Verified files on disk        : {really_on_disk}")
    print(f"All nonempty files in folder  : {folder_files}")
    print(f"Recoveries                    : {recoveries}")
    print(f"Manifest                      : {MANIFEST.resolve()}")
    print("Run the same command again to retry failures.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()