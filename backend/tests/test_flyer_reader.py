"""Tests for the flyer reader. No real OCR calls: the network request is replaced with a fake.

Save this file as: tests/test_flyer_reader.py
Run from the project root with:  python -m pytest
"""

import io
import json
import os
import threading
from datetime import date

import pytest
from PIL import Image

from app.ingestion import flyer_reader
from app.schemas.flyer import FlyerEntry

YEAR = date.today().year


# ---- helpers ----


def write_manifest(tmp_path, items):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return str(path)


def make_entry(tmp_path, name="flyer.png", flyer_id="f1"):
    image_path = tmp_path / name
    Image.new("RGB", (60, 60), "white").save(image_path)
    return FlyerEntry(flyer_id=flyer_id, path=str(image_path), year=YEAR)


def ocr_payload(text):
    """What OCR.space sends back for a successful read."""
    return {
        "OCRExitCode": 1,
        "IsErroredOnProcessing": False,
        "ParsedResults": [{"ParsedText": text}],
    }


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def install_fake_post(monkeypatch, responses):
    """Replace requests.post. Answers come from `responses` in order; the last one repeats."""
    calls = []
    queue = list(responses)

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(flyer_reader.requests, "post", fake_post)
    monkeypatch.setattr(flyer_reader.time, "sleep", lambda seconds: None)  # no waiting in tests
    return calls


# ---- manifest ----


def test_load_manifest_accepts_valid_entries(tmp_path):
    manifest = write_manifest(tmp_path, [{"flyer_id": "a", "path": "x.png", "year": YEAR}])
    entries = flyer_reader.load_manifest(manifest)
    assert [e.flyer_id for e in entries] == ["a"]


def test_load_manifest_rejects_duplicate_ids(tmp_path):
    item = {"flyer_id": "a", "path": "x.png", "year": YEAR}
    manifest = write_manifest(tmp_path, [item, item])
    with pytest.raises(ValueError, match="duplicate"):
        flyer_reader.load_manifest(manifest)


def test_load_manifest_rejects_bad_year(tmp_path):
    manifest = write_manifest(tmp_path, [{"flyer_id": "a", "path": "x.png", "year": 1999}])
    with pytest.raises(ValueError, match="year"):
        flyer_reader.load_manifest(manifest)


# ---- images ----


def test_hash_is_same_for_same_bytes_and_differs_otherwise():
    assert flyer_reader.hash_image(b"abc") == flyer_reader.hash_image(b"abc")
    assert flyer_reader.hash_image(b"abc") != flyer_reader.hash_image(b"abd")


def test_prepare_image_shrinks_large_images():
    buffer = io.BytesIO()
    Image.new("RGB", (4000, 3000), "white").save(buffer, format="PNG")
    prepared = flyer_reader.prepare_image(buffer.getvalue())
    with Image.open(io.BytesIO(prepared)) as img:
        assert max(img.size) <= flyer_reader.MAX_SIDE_PX
        assert img.format == "JPEG"


def test_prepare_image_handles_transparent_png():
    buffer = io.BytesIO()
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(buffer, format="PNG")
    prepared = flyer_reader.prepare_image(buffer.getvalue())
    with Image.open(io.BytesIO(prepared)) as img:
        assert img.getpixel((50, 50)) == (255, 255, 255)  # transparent became white


def test_prepare_image_stays_under_the_upload_limit():
    # Random noise is the worst case for JPEG: it can't be compressed well.
    noise = Image.frombytes("RGB", (1500, 1500), os.urandom(1500 * 1500 * 3))
    buffer = io.BytesIO()
    noise.save(buffer, format="PNG")

    prepared = flyer_reader.prepare_image(buffer.getvalue())

    assert len(prepared) <= flyer_reader.MAX_UPLOAD_BYTES
    with Image.open(io.BytesIO(prepared)) as img:
        assert img.format == "JPEG"


# ---- reading OCR.space's reply ----


def test_extract_text_returns_only_the_parsed_text():
    payload = {
        "OCRExitCode": 1,
        "IsErroredOnProcessing": False,
        "ProcessingTimeInMilliseconds": "812",
        "ParsedResults": [{"ParsedText": "Startup Panel\nOct 28, 7pm", "FileParseExitCode": 1}],
    }
    assert flyer_reader._extract_text(payload) == "Startup Panel\nOct 28, 7pm"


def test_extract_text_cleans_line_endings_and_blank_gaps():
    payload = ocr_payload("Title  \r\n\r\n\r\n\r\nOct 28\r\n")
    assert flyer_reader._extract_text(payload) == "Title\n\nOct 28"


def test_extract_text_with_no_results_is_empty():
    assert flyer_reader._extract_text({"OCRExitCode": 1, "ParsedResults": None}) == ""


def test_extract_text_raises_when_ocr_space_reports_an_error_list():
    payload = {"IsErroredOnProcessing": True, "ErrorMessage": ["File size exceeds limit", "Bad"]}
    with pytest.raises(RuntimeError, match="File size exceeds limit"):
        flyer_reader._extract_text(payload)


def test_extract_text_raises_when_ocr_space_reports_an_error_string():
    payload = {"OCRExitCode": 3, "IsErroredOnProcessing": True, "ErrorMessage": "Invalid API key"}
    with pytest.raises(RuntimeError, match="Invalid API key"):
        flyer_reader._extract_text(payload)


# ---- talking to OCR.space ----


def test_image_to_text_sends_the_expected_request(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "test-key")
    monkeypatch.delenv("OCR_SPACE_ENGINE", raising=False)
    monkeypatch.delenv("OCR_SPACE_LANGUAGE", raising=False)
    calls = install_fake_post(monkeypatch, [FakeResponse(200, ocr_payload("Hello flyer"))])

    text = flyer_reader.image_to_text(b"fake-image-bytes")

    assert text == "Hello flyer"
    url, kwargs = calls[0]
    assert url == flyer_reader.OCR_URL
    assert "test-key" not in url  # the key travels in the body, never in the URL
    assert kwargs["data"]["apikey"] == "test-key"
    assert kwargs["data"]["OCREngine"] == "2"
    assert kwargs["data"]["language"] == "eng"
    assert kwargs["data"]["isOverlayRequired"] == "false"
    assert kwargs["files"]["file"][1] == b"fake-image-bytes"


def test_image_to_text_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("OCR_SPACE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OCR_SPACE_API_KEY"):
        flyer_reader.image_to_text(b"x")


def test_image_to_text_rejects_an_unknown_engine(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "test-key")
    monkeypatch.setenv("OCR_SPACE_ENGINE", "9")
    with pytest.raises(RuntimeError, match="OCR_SPACE_ENGINE"):
        flyer_reader.image_to_text(b"x")


def test_image_to_text_retries_server_errors_then_succeeds(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "test-key")
    calls = install_fake_post(
        monkeypatch, [FakeResponse(503), FakeResponse(200, ocr_payload("Worked"))]
    )

    assert flyer_reader.image_to_text(b"x") == "Worked"
    assert len(calls) == 2


def test_image_to_text_gives_up_after_three_attempts(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "test-key")
    calls = install_fake_post(monkeypatch, [FakeResponse(500)])

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        flyer_reader.image_to_text(b"x")
    assert len(calls) == 3


def test_image_to_text_does_not_retry_errors_ocr_space_reports(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "bad-key")
    error = {"IsErroredOnProcessing": True, "ErrorMessage": "Invalid API key"}
    calls = install_fake_post(monkeypatch, [FakeResponse(200, error)])

    with pytest.raises(RuntimeError, match="Invalid API key"):
        flyer_reader.image_to_text(b"x")
    assert len(calls) == 1  # retrying a bad key would only waste the daily limit


# ---- cache ----


def test_cache_key_changes_when_the_engine_changes(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_ENGINE", "2")
    key_engine_2 = flyer_reader._cache_key("abc123")
    monkeypatch.setenv("OCR_SPACE_ENGINE", "3")
    key_engine_3 = flyer_reader._cache_key("abc123")
    assert key_engine_2 != key_engine_3


# ---- reading one flyer ----


def test_second_read_uses_cache_and_skips_ocr(tmp_path, monkeypatch):
    entry = make_entry(tmp_path)
    calls = []

    def fake_ocr(image_bytes):
        calls.append(1)
        return "Startup Panel\nOct 28, 7pm"

    monkeypatch.setattr(flyer_reader, "image_to_text", fake_ocr)
    cache, lock = {}, threading.Lock()

    first = flyer_reader.read_flyer(entry, cache, lock)
    second = flyer_reader.read_flyer(entry, cache, lock)

    assert first.status == "ok"
    assert second.text == first.text
    assert len(calls) == 1  # OCR was only called once


def test_no_text_is_marked_empty_and_not_cached(tmp_path, monkeypatch):
    entry = make_entry(tmp_path)
    monkeypatch.setattr(flyer_reader, "image_to_text", lambda b: "")
    cache, lock = {}, threading.Lock()

    result = flyer_reader.read_flyer(entry, cache, lock)

    assert result.status == "empty"
    assert cache == {}


def test_missing_file_gives_failed_result_instead_of_crashing(tmp_path):
    entry = FlyerEntry(flyer_id="gone", path=str(tmp_path / "nope.png"), year=YEAR)
    result = flyer_reader.read_flyer(entry, {}, threading.Lock())
    assert result.status == "failed"
    assert "not found" in result.error


def test_ocr_error_gives_failed_result(tmp_path, monkeypatch):
    entry = make_entry(tmp_path)

    def broken_ocr(image_bytes):
        raise RuntimeError("OCR down")

    monkeypatch.setattr(flyer_reader, "image_to_text", broken_ocr)
    result = flyer_reader.read_flyer(entry, {}, threading.Lock())
    assert result.status == "failed"
    assert "OCR down" in result.error