"""Reads flyer images and turns them into plain text using OCR.space.

Save this file as: app/ingestion/flyer_reader.py
Run it from the project root with:  python -m app.ingestion.flyer_reader

Flow for each flyer:
    manifest entry -> load image -> hash it -> already read? use saved text
                   -> otherwise shrink image under 1 MB -> OCR.space reads it
                   -> keep only the text -> save to cache

OCR.space answers with its own JSON. We pull out just the text and wrap it in
our own FlyerText, so nothing else in the project ever sees OCR.space's format.

One bad flyer never stops the run. It comes back with status "failed".

Settings (put them in your .env file):
    OCR_SPACE_API_KEY=...        required (free key from ocr.space)
    OCR_SPACE_ENGINE=2           optional: 1, 2 or 3 (default 2)
    OCR_SPACE_LANGUAGE=eng       optional (default eng)
"""

import argparse
import hashlib
import io
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image, ImageOps
from pydantic import ValidationError

from app.schemas.flyer import FlyerEntry, FlyerText

load_dotenv()
logger = logging.getLogger(__name__)

# app/ingestion/flyer_reader.py -> parents[2] is the project root. Paths in the
# manifest are relative to it, so the code works from any folder.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

MANIFEST_PATH = "data/flyer_manifest.json"
CACHE_PATH = "data/cache/flyer_text_cache.json"

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg"}
MAX_FILE_MB = 20  # refuse huge source files
MAX_SIDE_PX = 1500  # shrink so the longest side is at most this
MIN_SIDE_PX = 600  # never shrink below this, text becomes unreadable
MAX_UPLOAD_BYTES = 1_000_000  # OCR.space free plan accepts files up to 1 MB
MAX_WORKERS = 2  # flyers read at the same time (kept low to be polite to a free service)

OCR_URL = "https://api.ocr.space/parse/image"
OCR_TIMEOUT_SEC = 60
OCR_ATTEMPTS = 3  # tries per flyer for network problems and server errors
OCR_RETRY_DELAY_SEC = 2
DEFAULT_ENGINE = "2"
DEFAULT_LANGUAGE = "eng"


# ---------------------------------------------------------------- manifest


def _resolve(path: str) -> Path:
    """Turn a manifest path into a real path (relative -> from project root)."""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def load_manifest(path: str = MANIFEST_PATH) -> list[FlyerEntry]:
    """Read and check the manifest. Reports ALL problems at once, not just the first."""
    manifest_file = _resolve(path)
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}")

    try:
        raw = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {exc}") from exc

    if not isinstance(raw, list):
        raise ValueError("Manifest must be a list of flyer entries")

    entries: list[FlyerEntry] = []
    problems: list[str] = []
    seen_ids: set[str] = set()

    for number, item in enumerate(raw, start=1):
        try:
            entry = FlyerEntry.model_validate(item)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            )
            problems.append(f"entry #{number}: {details}")
            continue

        if entry.flyer_id in seen_ids:
            problems.append(f"entry #{number}: duplicate flyer_id '{entry.flyer_id}'")
            continue
        seen_ids.add(entry.flyer_id)
        entries.append(entry)

    if problems:
        raise ValueError("Manifest has problems:\n  " + "\n  ".join(problems))
    return entries


# ------------------------------------------------------------------ images


def load_image(entry: FlyerEntry) -> bytes:
    """Read the image file, checking it exists, is a supported type, and isn't huge."""
    path = _resolve(entry.path)
    if not path.is_file():
        raise FileNotFoundError(f"{entry.flyer_id}: file not found at {entry.path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"{entry.flyer_id}: unsupported file type '{path.suffix}' "
            f"(use {', '.join(sorted(SUPPORTED_SUFFIXES))})"
        )
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise ValueError(f"{entry.flyer_id}: file is {size_mb:.1f} MB (max {MAX_FILE_MB})")
    return path.read_bytes()


def hash_image(image_bytes: bytes) -> str:
    """Fingerprint of the original file. Same image = same hash, whatever the filename."""
    return hashlib.sha256(image_bytes).hexdigest()


def _to_jpeg(img: Image.Image, quality: int) -> bytes:
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def _encode_under_limit(img: Image.Image) -> bytes:
    """Encode as JPEG, lowering quality and then size until it fits under 1 MB."""
    for quality in (90, 80, 70, 60):
        data = _to_jpeg(img, quality)
        if len(data) <= MAX_UPLOAD_BYTES:
            return data

    # Still too big: shrink the picture a little at a time.
    while max(img.size) > MIN_SIDE_PX:
        img = img.resize((int(img.width * 0.85), int(img.height * 0.85)))
        data = _to_jpeg(img, 70)
        if len(data) <= MAX_UPLOAD_BYTES:
            return data

    raise ValueError(
        f"image is still over {MAX_UPLOAD_BYTES // 1000} KB after shrinking "
        f"to {MIN_SIDE_PX}px"
    )


def prepare_image(image_bytes: bytes) -> bytes:
    """Shrink the image and convert to JPEG under the 1 MB upload limit."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img)  # fixes sideways phone photos

        if img.mode in ("RGBA", "LA", "P"):
            # Put transparent images on white so dark text can't vanish into black.
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, "white")
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert("RGB")

        img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))  # keeps shape, never enlarges
        return _encode_under_limit(img)


# ---------------------------------------------------------- text extraction


class _RetryableOCRError(Exception):
    """A temporary problem (like a server error) that is worth trying again."""


def _ocr_settings() -> tuple[str, str, str]:
    """Read OCR.space settings from the environment (.env) at the moment they're needed."""
    api_key = os.getenv("OCR_SPACE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OCR_SPACE_API_KEY is not set. Add it to your .env file.")
    engine = os.getenv("OCR_SPACE_ENGINE", DEFAULT_ENGINE).strip()
    if engine not in {"1", "2", "3"}:
        raise RuntimeError(f"OCR_SPACE_ENGINE must be 1, 2 or 3 (got '{engine}')")
    language = os.getenv("OCR_SPACE_LANGUAGE", DEFAULT_LANGUAGE).strip()
    return api_key, engine, language


def _clean_text(text: str) -> str:
    """Tidy OCR output: normal line endings, no trailing spaces, no big blank gaps."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _error_message(payload: dict) -> str:
    """OCR.space gives its error as either a string or a list of strings."""
    message = payload.get("ErrorMessage")
    if isinstance(message, list):
        message = "; ".join(str(m) for m in message)
    details = payload.get("ErrorDetails")
    return str(message or details or "unknown error")


def _extract_text(payload: dict) -> str:
    """Pull just the text out of OCR.space's JSON reply (or raise if it reports an error)."""
    if payload.get("IsErroredOnProcessing") or payload.get("OCRExitCode") in (3, 4):
        raise RuntimeError(f"OCR.space error: {_error_message(payload)}")
    results = payload.get("ParsedResults") or []
    text = "\n".join((result.get("ParsedText") or "") for result in results)
    return _clean_text(text)


def image_to_text(image_bytes: bytes) -> str:
    """THE swappable piece: the only function that knows how text is extracted.

    To switch to Tesseract or another service later, change only this function.
    The API key goes in the request body, never in the URL, so it can't end up
    in error messages or logs.
    """
    api_key, engine, language = _ocr_settings()
    payload = {
        "apikey": api_key,
        "language": language,
        "isOverlayRequired": "false",  # we only want the text, not word positions
        "OCREngine": engine,
    }
    files = {"file": ("flyer.jpg", image_bytes, "image/jpeg")}

    last_error: Exception | None = None
    for attempt in range(1, OCR_ATTEMPTS + 1):
        try:
            response = requests.post(OCR_URL, data=payload, files=files, timeout=OCR_TIMEOUT_SEC)
            if response.status_code >= 500:
                raise _RetryableOCRError(f"OCR.space server error (HTTP {response.status_code})")
            if response.status_code != 200:
                raise RuntimeError(f"OCR.space returned HTTP {response.status_code}")
            return _extract_text(response.json())
        except (requests.RequestException, _RetryableOCRError) as exc:
            last_error = exc
            logger.warning("OCR.space attempt %d/%d failed: %s", attempt, OCR_ATTEMPTS, exc)
            if attempt < OCR_ATTEMPTS:
                time.sleep(OCR_RETRY_DELAY_SEC * attempt)

    raise RuntimeError(f"OCR.space request failed after {OCR_ATTEMPTS} attempts: {last_error}")


# ------------------------------------------------------------------- cache


def _cache_key(image_hash: str) -> str:
    """Cache key = image + engine + language, so changing a setting re-reads the flyer."""
    engine = os.getenv("OCR_SPACE_ENGINE", DEFAULT_ENGINE).strip()
    language = os.getenv("OCR_SPACE_LANGUAGE", DEFAULT_LANGUAGE).strip()
    return f"{image_hash}|engine{engine}|{language}"


def load_cache() -> dict[str, str]:
    """Saved results: {cache_key: text}. A missing or broken file means an empty cache."""
    path = _resolve(CACHE_PATH)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        logger.warning("Flyer cache file was unreadable, starting fresh")
        return {}


def save_cache(cache: dict[str, str]) -> None:
    path = _resolve(CACHE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")  # write to a temp file first so a crash can't corrupt the cache
    temp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


# ------------------------------------------------------------- main logic


def _make_result(entry: FlyerEntry, text: str, image_hash: str) -> FlyerText:
    text = text.strip()
    status = "ok" if text else "empty"
    return FlyerText(
        flyer_id=entry.flyer_id,
        year=entry.year,
        status=status,
        text=text,
        image_hash=image_hash,
        read_at=datetime.now(timezone.utc),
    )


def read_flyer(entry: FlyerEntry, cache: dict[str, str], lock: threading.Lock) -> FlyerText:
    """Read one flyer. Never raises: problems come back as status 'failed'."""
    try:
        raw = load_image(entry)
        image_hash = hash_image(raw)
        key = _cache_key(image_hash)

        with lock:
            cached_text = cache.get(key)
        if cached_text is not None:
            logger.info("%s: using saved text", entry.flyer_id)
            return _make_result(entry, cached_text, image_hash)

        text = image_to_text(prepare_image(raw))
        result = _make_result(entry, text, image_hash)

        if result.status == "ok":  # only keep good results, so empty/failed ones get retried
            with lock:
                cache[key] = result.text
        return result

    except Exception as exc:  # noqa: BLE001 - on purpose: one bad flyer must not stop the rest
        logger.warning("%s: failed (%s)", entry.flyer_id, exc)
        return FlyerText(
            flyer_id=entry.flyer_id,
            year=entry.year,
            status="failed",
            error=str(exc),
            read_at=datetime.now(timezone.utc),
        )


def _log_summary(results: list[FlyerText]) -> None:
    counts = {"ok": 0, "empty": 0, "failed": 0}
    for result in results:
        counts[result.status] += 1
    logger.info(
        "Flyers read: %d ok, %d empty, %d failed",
        counts["ok"], counts["empty"], counts["failed"],
    )
    for result in results:
        if result.status == "failed":
            logger.info("  FAILED %s: %s", result.flyer_id, result.error)
        elif result.status == "empty":
            logger.info("  EMPTY  %s: no readable text found", result.flyer_id)


def read_all_flyers(manifest_path: str = MANIFEST_PATH, use_cache: bool = True) -> list[FlyerText]:
    """Read every flyer in the manifest. This is what the rest of the pipeline calls."""
    entries = load_manifest(manifest_path)
    cache = load_cache() if use_cache else {}
    lock = threading.Lock()

    if not os.getenv("OCR_SPACE_API_KEY", "").strip():
        logger.warning(
            "OCR_SPACE_API_KEY is not set: only flyers already in the cache can be read"
        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(lambda e: read_flyer(e, cache, lock), entries))

    if use_cache:
        save_cache(cache)
    _log_summary(results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Read every flyer in the manifest.")
    parser.add_argument(
        "--no-cache", action="store_true", help="re-read every flyer and ignore saved results"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = read_all_flyers(use_cache=not args.no_cache)
    for r in results:
        preview = r.text[:80].replace("\n", " | ")
        print(f"{r.flyer_id} [{r.status}] {preview or r.error or ''}")


if __name__ == "__main__":
    main()