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


def isolate_events(tmp_path, monkeypatch):
    """Point the API at files in tmp_path and ignore .env, so the result doesn't depend on the
    developer's own settings (for example INCLUDE_DEMO_EVENTS=true or a real data/events.json)."""
    monkeypatch.setattr(event_store, "EVENTS_PATH", tmp_path / "events.json")
    monkeypatch.setattr(event_store, "DEMO_EVENTS_PATH", tmp_path / "demo_events.json")
    monkeypatch.setenv("INCLUDE_DEMO_EVENTS", "false")


def save_one_event(tmp_path, monkeypatch):
    from datetime import datetime

    from app.schemas.event import Event

    event = Event(id="e1", title="AI Club Kickoff", start=datetime.fromisoformat("2999-01-08T18:00:00-05:00"),
                  interest_tags=["technology-coding:ai"])
    isolate_events(tmp_path, monkeypatch)
    event_store.save_events([event], path=tmp_path / "events.json")


def test_schedules_says_so_when_the_weekly_job_has_not_run(tmp_path, monkeypatch):
    isolate_events(tmp_path, monkeypatch)  # nothing saved in tmp_path
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


def test_schedules_can_use_the_demo_events_when_switched_on(tmp_path, monkeypatch):
    from datetime import datetime

    from app.schemas.event import Event

    isolate_events(tmp_path, monkeypatch)
    demo = Event(id="fake_01", title="Demo event", start=datetime.fromisoformat("2999-01-08T18:00:00-05:00"),
                 interest_tags=["technology-coding:ai"])
    event_store.save_events([demo], path=tmp_path / "demo_events.json")
    body = {**PROFILE, "week_start": "2999-01-07"}
    assert client.post("/api/schedules", json=body).status_code == 503  # off by default: no real events yet
    monkeypatch.setenv("INCLUDE_DEMO_EVENTS", "true")
    response = client.post("/api/schedules", json=body)
    assert response.status_code == 200
    assert [e["id"] for e in response.json()["events"]] == ["fake_01"]