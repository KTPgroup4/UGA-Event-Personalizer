"""Tests for the account endpoints, using FastAPI's built-in test client.

Each test gets its own empty accounts database in a temporary folder, so nothing touches
your real data/accounts.db.

Save this file as: tests/test_auth_api.py
Run from the backend folder with:  python -m pytest tests/test_auth_api.py
"""

import pytest
from fastapi.testclient import TestClient

from app.accounts import Accounts, get_accounts
from app.database import Database
from app.main import app

EMAIL = "alex@uga.edu"
PASSWORD = "correct horse battery"
PREFS = {
    "name": "Alex",
    "majors": ["computer-science"],
    "interests": ["technology-coding:ai", "music"],
    "busy": [{"day": "mon", "start": "09:00", "end": "09:50"}],
}
CALENDAR = {
    "saved": [
        {
            "id": "e1", "title": "Guitar Circle", "description": "Bring a guitar.", "start": "2026-11-12T18:00:00-05:00",
            "end": "2026-11-12T19:00:00-05:00", "end_is_estimated": False, "location": "Tate Plaza",
            "organizer": "Guitar Club", "url": None, "interest_tags": ["music:guitar"],
        }
    ],
    "personal": [{"id": "p1", "title": "Study group", "date": "2026-11-11", "time": "15:30", "end_time": "16:30"}],
}


@pytest.fixture
def client(tmp_path):
    accounts = Accounts(Database(url="", sqlite_path=tmp_path / "accounts.db"))
    app.dependency_overrides[get_accounts] = lambda: accounts
    yield TestClient(app)
    app.dependency_overrides.clear()


def sign_up(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/auth/signup", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_sign_up_returns_a_token_and_the_user(client):
    response = sign_up(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"] == {"email": EMAIL, "preferences": None, "calendar": None}
    assert PASSWORD not in response.text


def test_sign_up_problems_have_readable_messages(client):
    assert sign_up(client, email="nope").status_code == 422
    short = sign_up(client, password="short")
    assert short.status_code == 422 and "at least 8" in short.json()["detail"]
    assert sign_up(client).status_code == 200
    again = sign_up(client, email="ALEX@uga.edu")
    assert again.status_code == 409 and "already exists" in again.json()["detail"]


def test_log_in(client):
    sign_up(client)
    good = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert good.status_code == 200 and good.json()["token"]
    bad = client.post("/api/auth/login", json={"email": EMAIL, "password": "wrong password"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@uga.edu", "password": PASSWORD})
    assert unknown.status_code == 401 and unknown.json() == bad.json()


def test_me_needs_a_valid_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=bearer("made-up")).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Basic abc"}).status_code == 401
    token = sign_up(client).json()["token"]
    response = client.get("/api/me", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == {"user": {"email": EMAIL, "preferences": None, "calendar": None}}


def test_log_out_ends_the_session(client):
    token = sign_up(client).json()["token"]
    assert client.post("/api/auth/logout", headers=bearer(token)).json() == {"ok": True}
    assert client.get("/api/me", headers=bearer(token)).status_code == 401
    assert client.post("/api/auth/logout").status_code == 200  # logging out twice is harmless


def test_preferences_are_saved_and_come_back_on_the_next_log_in(client):
    token = sign_up(client).json()["token"]
    saved = client.put("/api/me/preferences", json=PREFS, headers=bearer(token))
    assert saved.status_code == 200 and saved.json() == {"preferences": PREFS}

    assert client.get("/api/me", headers=bearer(token)).json()["user"]["preferences"] == PREFS
    again = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert again.json()["user"]["preferences"] == PREFS


def test_saving_preferences_needs_a_login_and_valid_answers(client):
    assert client.put("/api/me/preferences", json=PREFS).status_code == 401
    token = sign_up(client).json()["token"]
    for bad in (
        {**PREFS, "majors": ["not-a-major"]},
        {**PREFS, "interests": []},
        {**PREFS, "week_start": "2026-11-09"},  # the week is never saved
        {**PREFS, "email": "other@uga.edu"},
    ):
        assert client.put("/api/me/preferences", json=bad, headers=bearer(token)).status_code == 422
    assert client.get("/api/me", headers=bearer(token)).json()["user"]["preferences"] is None


def test_the_calendar_is_saved_and_comes_back_on_the_next_log_in(client):
    token = sign_up(client).json()["token"]
    saved = client.put("/api/me/calendar", json=CALENDAR, headers=bearer(token))
    assert saved.status_code == 200
    assert saved.json()["calendar"]["personal"] == CALENDAR["personal"]

    me = client.get("/api/me", headers=bearer(token)).json()["user"]["calendar"]
    assert me["saved"][0]["id"] == "e1" and me["personal"] == CALENDAR["personal"]
    again = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert again.json()["user"]["calendar"]["saved"][0]["title"] == "Guitar Circle"


def test_saving_the_calendar_needs_a_login_and_valid_events(client):
    assert client.put("/api/me/calendar", json=CALENDAR).status_code == 401
    token = sign_up(client).json()["token"]
    bad_time = {**CALENDAR, "personal": [{**CALENDAR["personal"][0], "time": "3:30 PM"}]}
    assert client.put("/api/me/calendar", json=bad_time, headers=bearer(token)).status_code == 422
    assert client.put("/api/me/calendar", json={"saved": [], "personal": [], "busy": []}, headers=bearer(token)).status_code == 422
    assert client.get("/api/me", headers=bearer(token)).json()["user"]["calendar"] is None


def test_the_other_endpoints_still_work_without_an_account(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/options").status_code == 200
