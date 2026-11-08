"""Tests for the web endpoints, using FastAPI's built-in test client.

Save this file as: tests/test_api.py
Run from the backend folder with:  python -m pytest
(Needs httpx, which is listed in requirements.txt.)
"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import event_store, flyer_listing, taxonomy
from app.ingestion import flyer_reader
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_options_match_the_taxonomy():
    response = client.get("/api/options")
    assert response.status_code == 200
    assert response.json() == taxonomy.questionnaire_options()


def test_flyers_lists_the_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(flyer_reader, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(flyer_listing, "FLYERS_DIR", tmp_path / "data" / "flyers")
    (tmp_path / "data" / "flyers").mkdir(parents=True)
    (tmp_path / "data" / "flyers" / "a.png").write_bytes(b"fake")
    manifest = [{"flyer_id": "f1", "path": "data/flyers/a.png", "year": date.today().year}]
    (tmp_path / "data" / "flyer_manifest.json").write_text(json.dumps(manifest))

    response = client.get("/api/flyers")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["flyers"][0]["flyer_id"] == "f1"
    assert body["flyers"][0]["status"] == "not_read"


def test_a_missing_manifest_gives_a_clear_500(tmp_path, monkeypatch):
    monkeypatch.setattr(flyer_reader, "PROJECT_ROOT", tmp_path)
    response = client.get("/api/flyers")
    assert response.status_code == 500
    assert "Manifest not found" in response.json()["detail"]


def test_an_unknown_picture_is_a_404():
    assert client.get("/api/flyer-images/does-not-exist.png").status_code == 404


# ---- POST /api/schedules ----

PROFILE = {
    "week_start": "2026-11-09",
    "majors": ["computer-science"],
    "interests": ["technology-coding:ai", "music"],
    "busy": [{"day": "mon", "start": "09:00", "end": "09:50"}],
}


def save_one_event(tmp_path, monkeypatch):
    from datetime import datetime

    from app.schemas.event import Event

    event = Event(id="e1", title="AI Club Kickoff", start=datetime.fromisoformat("2999-01-08T18:00:00-05:00"),
                  interest_tags=["technology-coding:ai"])
    path = tmp_path / "events.json"
    event_store.save_events([event], path=path)
    monkeypatch.setattr(event_store, "EVENTS_PATH", path)


def test_schedules_says_so_when_the_weekly_job_has_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(event_store, "EVENTS_PATH", tmp_path / "missing.json")
    response = client.post("/api/schedules", json=PROFILE)
    assert response.status_code == 503
    assert "scripts.build_events" in response.json()["detail"]


def test_schedules_returns_a_deck_in_the_contract_shape(tmp_path, monkeypatch):
    save_one_event(tmp_path, monkeypatch)
    # A Monday far in the future, so the event never counts as "already started".
    response = client.post("/api/schedules", json={**PROFILE, "week_start": "2999-01-07"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"week_start", "target_picks", "events"}
    assert body["target_picks"] == 5
    assert [e["id"] for e in body["events"]] == ["e1"]
    assert body["events"][0]["match_kind"] == "interest" and body["events"][0]["conflicts_with"] == []


def test_schedules_rejects_a_bad_profile_with_422(tmp_path, monkeypatch):
    save_one_event(tmp_path, monkeypatch)
    response = client.post("/api/schedules", json={**PROFILE, "majors": ["not-a-major"]})
    assert response.status_code == 422
    assert client.post("/api/schedules", json={**PROFILE, "name": "Alex"}).status_code == 422