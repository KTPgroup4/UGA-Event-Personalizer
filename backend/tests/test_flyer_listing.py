"""Tests for the list of flyers behind GET /api/flyers.

Save this file as: tests/test_flyer_listing.py
Run from the backend folder with:  python -m pytest
"""

import json
from datetime import date

import pytest

from app import flyer_listing
from app.ingestion import flyer_reader

YEAR = date.today().year  # the manifest only accepts this year or its neighbours


@pytest.fixture
def project(tmp_path, monkeypatch):
    """An empty fake project folder that the reader and the listing both use."""
    monkeypatch.setattr(flyer_reader, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(flyer_listing, "FLYERS_DIR", tmp_path / "data" / "flyers")
    (tmp_path / "data" / "flyers").mkdir(parents=True)
    return tmp_path


def add_flyer(project, flyer_id, filename, text=None, folder="data/flyers"):
    """Create a picture on disk, add it to the manifest, and optionally save its text."""
    image = project / folder / filename
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(f"fake image {flyer_id}".encode())

    manifest = project / "data" / "flyer_manifest.json"
    entries = json.loads(manifest.read_text()) if manifest.exists() else []
    entries.append({"flyer_id": flyer_id, "path": f"{folder}/{filename}", "year": YEAR})
    manifest.write_text(json.dumps(entries))

    if text is not None:
        cache = flyer_reader.load_cache()
        cache[flyer_reader._cache_key(flyer_reader.hash_image(image.read_bytes()))] = text
        flyer_reader.save_cache(cache)


def by_id(flyers):
    return {f["flyer_id"]: f for f in flyers}


def test_a_flyer_with_saved_text_comes_back_with_text_and_image_url(project):
    add_flyer(project, "f1", "club.png", text="Join us March 3 at 6pm")
    (flyer,) = flyer_listing.list_flyers(today=date(YEAR, 1, 1))
    assert flyer["flyer_id"] == "f1"
    assert flyer["year"] == YEAR
    assert flyer["status"] == "ok"
    assert flyer["text"] == "Join us March 3 at 6pm"
    assert flyer["image_url"] == "/api/flyer-images/club.png"


def test_date_status_follows_the_dates_printed_on_the_flyer(project):
    add_flyer(project, "f1", "a.png", text="March 3")
    add_flyer(project, "f2", "b.png", text="No date anywhere here")
    early = by_id(flyer_listing.list_flyers(today=date(YEAR, 1, 1)))
    late = by_id(flyer_listing.list_flyers(today=date(YEAR, 12, 31)))
    assert early["f1"]["date_status"] == "upcoming"
    assert late["f1"]["date_status"] == "past"
    assert early["f2"]["date_status"] == "unknown"


def test_a_picture_that_was_never_read_is_marked_not_read(project):
    add_flyer(project, "f1", "new.png")  # no saved text
    (flyer,) = flyer_listing.list_flyers()
    assert flyer["status"] == "not_read"
    assert flyer["text"] == ""
    assert flyer["image_url"] == "/api/flyer-images/new.png"


def test_a_manifest_entry_without_a_file_is_marked_missing(project):
    add_flyer(project, "f1", "gone.png")
    (project / "data" / "flyers" / "gone.png").unlink()
    (flyer,) = flyer_listing.list_flyers()
    assert flyer["status"] == "missing_image"
    assert flyer["image_url"] is None


def test_file_names_with_spaces_are_made_url_safe(project):
    add_flyer(project, "f1", "Club Night.png")
    (flyer,) = flyer_listing.list_flyers()
    assert flyer["image_url"] == "/api/flyer-images/Club%20Night.png"


def test_pictures_outside_the_flyers_folder_get_no_url(project):
    add_flyer(project, "f1", "x.png", folder="other")
    (flyer,) = flyer_listing.list_flyers()
    assert flyer["image_url"] is None


def test_order_follows_the_manifest(project):
    for number in (3, 1, 2):
        add_flyer(project, f"f{number}", f"{number}.png")
    assert [f["flyer_id"] for f in flyer_listing.list_flyers()] == ["f3", "f1", "f2"]


def test_a_missing_manifest_is_reported(project):
    with pytest.raises(FileNotFoundError, match="Manifest not found"):
        flyer_listing.list_flyers()


def test_an_edited_picture_is_not_matched_to_the_old_text(project):
    add_flyer(project, "f1", "a.png", text="old text")
    image = project / "data" / "flyers" / "a.png"
    image.write_bytes(b"a completely different picture, longer than before")
    (flyer,) = flyer_listing.list_flyers()
    assert flyer["status"] == "not_read"