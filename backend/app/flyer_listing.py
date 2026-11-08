"""Builds the flyer list that GET /api/flyers returns.

It only READS what the flyer reader already saved (the manifest, the images, and
the text cache). It never calls the OCR service, so loading the page costs nothing
and needs no API key. To get text for a flyer, run the reader first:
    python -m app.ingestion.flyer_reader

Save this file as: app/flyer_listing.py
"""

from datetime import date
from pathlib import Path
from urllib.parse import quote

from app.ingestion import flyer_date_filter, flyer_reader

# Images are served from here (see main.py). It starts with /api so the frontend's
# dev proxy, which only forwards /api, passes image requests through too.
IMAGE_URL_PREFIX = "/api/flyer-images"
FLYERS_DIR = flyer_reader.PROJECT_ROOT / "data" / "flyers"

# Hashing an image means reading the whole file. Remember the result until the
# file changes, so repeated requests stay fast.
_hash_memo: dict[tuple, str] = {}


def _image_path(manifest_path: str) -> Path:
    path = Path(manifest_path)
    return path if path.is_absolute() else flyer_reader.PROJECT_ROOT / path


def _image_hash(path: Path) -> str:
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _hash_memo:
        _hash_memo[key] = flyer_reader.hash_image(path.read_bytes())
    return _hash_memo[key]


def _image_url(path: Path) -> str | None:
    """The URL the browser can load the picture from, or None if it isn't served."""
    try:
        relative = path.resolve().relative_to(FLYERS_DIR.resolve())
    except ValueError:  # the file is outside data/flyers/, so it is not served
        return None
    return f"{IMAGE_URL_PREFIX}/{quote(relative.as_posix())}"


def list_flyers(today: date | None = None) -> list[dict]:
    """One dictionary per manifest entry, in manifest order.

    status:
      "ok"             image found and its text was read earlier
      "not_read"       image found, but no saved text yet (run the flyer reader)
      "missing_image"  the manifest lists a file that isn't in data/flyers/
    date_status: "upcoming", "past" or "unknown" (from the dates printed on the flyer)

    Raises FileNotFoundError / ValueError if the manifest is missing or invalid.
    """
    entries = flyer_reader.load_manifest()
    cache = flyer_reader.load_cache()
    today = today or flyer_date_filter.get_today()

    flyers = []
    for entry in entries:
        path = _image_path(entry.path)
        item = {
            "flyer_id": entry.flyer_id,
            "year": entry.year,
            "image_url": None,
            "status": "missing_image",
            "text": "",
            "date_status": "unknown",
        }
        if path.is_file():
            item["image_url"] = _image_url(path)
            # _cache_key is the reader's own rule for "this image + these OCR settings".
            text = cache.get(flyer_reader._cache_key(_image_hash(path)))
            if text is None:
                item["status"] = "not_read"
            else:
                item["status"] = "ok"
                item["text"] = text.strip()
                dates = flyer_date_filter.find_dates(item["text"], entry.year)
                item["date_status"] = flyer_date_filter.classify(dates, today)
        flyers.append(item)
    return flyers