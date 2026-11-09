"""Tests for accounts (app/accounts.py and app/database.py). No web server needed.

Save this file as: tests/test_accounts.py
Run from the backend folder with:  python -m pytest tests/test_accounts.py
"""

import pytest

from app import accounts as acc
from app.accounts import Accounts, LoginThrottle
from app.database import Database, DatabaseUnavailable
from app.schemas.calendar import SavedCalendar
from app.schemas.preferences import SavedPreferences

PASSWORD = "correct horse battery"

PREFS = {
    "name": "Alex",
    "majors": ["computer-science"],
    "interests": ["technology-coding:ai", "music"],
    "busy": [{"day": "mon", "start": "09:00", "end": "09:50"}],
}


class Clock:
    """A clock we can move forward by hand, so tests don't have to wait for 30 days."""

    def __init__(self):
        self.value = 1_800_000_000.0

    def __call__(self):
        return self.value


def make_accounts(tmp_path, clock=None):
    clock = clock or Clock()
    database = Database(url="", sqlite_path=tmp_path / "accounts.db")
    return Accounts(database, now=clock), clock


# ---- email and password rules ----


def test_emails_are_tidied():
    assert acc.normalize_email("  Alex@UGA.edu ") == "alex@uga.edu"


@pytest.mark.parametrize("bad", ["", "alex", "alex@", "@uga.edu", "alex@uga", "a b@uga.edu", None, 5])
def test_bad_emails_are_refused(bad):
    with pytest.raises(acc.InvalidInput):
        acc.normalize_email(bad)


def test_password_length_rules():
    assert acc.check_new_password("12345678") == "12345678"
    with pytest.raises(acc.InvalidInput, match="at least 8"):
        acc.check_new_password("1234567")
    with pytest.raises(acc.InvalidInput, match="at most 128"):
        acc.check_new_password("x" * 129)


def test_a_password_is_hashed_with_a_random_salt_and_checks_out():
    first, second = acc.hash_password(PASSWORD), acc.hash_password(PASSWORD)
    assert first != second  # different salts
    assert PASSWORD not in first
    assert acc.verify_password(PASSWORD, first)
    assert not acc.verify_password("wrong password", first)


def test_a_damaged_stored_hash_never_matches():
    assert not acc.verify_password(PASSWORD, "")
    assert not acc.verify_password(PASSWORD, "scrypt$oops")
    assert not acc.verify_password(PASSWORD, "md5$1$2$3$ab$cd")


# ---- sign up ----


def test_sign_up_gives_a_token_and_the_user(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    token, user = accounts.sign_up(" Alex@UGA.edu", PASSWORD)
    assert token and user.email == "alex@uga.edu" and user.preferences is None
    assert accounts.user_for_token(token).email == "alex@uga.edu"


def test_the_same_email_cannot_sign_up_twice_even_in_other_capitals(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    with pytest.raises(acc.EmailTaken, match="already exists"):
        accounts.sign_up("ALEX@uga.edu", "another password")


def test_sign_up_checks_the_email_and_password(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    with pytest.raises(acc.InvalidInput):
        accounts.sign_up("not an email", PASSWORD)
    with pytest.raises(acc.InvalidInput):
        accounts.sign_up("alex@uga.edu", "short")


def test_the_database_holds_neither_the_password_nor_the_token(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    token, _ = accounts.sign_up("alex@uga.edu", PASSWORD)
    stored = accounts.db.query("SELECT password_hash FROM users")[0][0]
    assert PASSWORD not in stored
    stored_token = accounts.db.query("SELECT token_hash FROM sessions")[0][0]
    assert stored_token != token and token not in stored_token


# ---- log in ----


def test_log_in_with_the_right_password(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    token, user = accounts.log_in("ALEX@uga.edu ", PASSWORD)
    assert user.email == "alex@uga.edu"
    assert accounts.user_for_token(token).email == "alex@uga.edu"


def test_a_wrong_password_and_an_unknown_email_look_the_same(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    with pytest.raises(acc.BadLogin) as wrong:
        accounts.log_in("alex@uga.edu", "not the password")
    with pytest.raises(acc.BadLogin) as unknown:
        accounts.log_in("nobody@uga.edu", PASSWORD)
    with pytest.raises(acc.BadLogin) as garbage:
        accounts.log_in("not an email", PASSWORD)
    assert str(wrong.value) == str(unknown.value) == str(garbage.value)


def test_each_log_in_is_its_own_session(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    first, _ = accounts.log_in("alex@uga.edu", PASSWORD)
    second, _ = accounts.log_in("alex@uga.edu", PASSWORD)
    assert first != second
    accounts.log_out(first)
    assert accounts.user_for_token(first) is None
    assert accounts.user_for_token(second) is not None  # the other device stays logged in


# ---- sessions ----


def test_unknown_and_empty_tokens_are_nobody(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    assert accounts.user_for_token("") is None
    assert accounts.user_for_token("made-up-token") is None


def test_a_session_ends_after_30_days(tmp_path):
    accounts, clock = make_accounts(tmp_path)
    token, _ = accounts.sign_up("alex@uga.edu", PASSWORD)
    clock.value += acc.SESSION_SECONDS - 60
    assert accounts.user_for_token(token) is not None
    clock.value += 120
    assert accounts.user_for_token(token) is None


def test_old_sessions_are_cleaned_up_on_the_next_log_in(tmp_path):
    accounts, clock = make_accounts(tmp_path)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    clock.value += acc.SESSION_SECONDS + 1
    accounts.log_in("alex@uga.edu", PASSWORD)
    assert len(accounts.db.query("SELECT * FROM sessions")) == 1


# ---- too many wrong passwords ----


def test_too_many_wrong_passwords_locks_the_email_for_a_while(tmp_path):
    clock = Clock()
    accounts, _ = make_accounts(tmp_path, clock)
    accounts.throttle = LoginThrottle(max_failures=3, window_seconds=600, now=clock)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    for _ in range(3):
        with pytest.raises(acc.BadLogin):
            accounts.log_in("alex@uga.edu", "wrong password")
    with pytest.raises(acc.TooManyAttempts):  # even the right password is refused now
        accounts.log_in("alex@uga.edu", PASSWORD)
    clock.value += 601
    accounts.log_in("alex@uga.edu", PASSWORD)  # the lock wore off


def test_a_good_log_in_resets_the_count(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    accounts.throttle = LoginThrottle(max_failures=3, window_seconds=600, now=accounts.now)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    for _ in range(2):
        with pytest.raises(acc.BadLogin):
            accounts.log_in("alex@uga.edu", "wrong password")
    accounts.log_in("alex@uga.edu", PASSWORD)
    for _ in range(2):  # would be the 3rd and 4th failure if the count had not reset
        with pytest.raises(acc.BadLogin):
            accounts.log_in("alex@uga.edu", "wrong password")


def test_one_email_being_locked_does_not_lock_the_others(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    accounts.throttle = LoginThrottle(max_failures=2, window_seconds=600, now=accounts.now)
    accounts.sign_up("alex@uga.edu", PASSWORD)
    accounts.sign_up("sam@uga.edu", PASSWORD)
    for _ in range(2):
        with pytest.raises(acc.BadLogin):
            accounts.log_in("alex@uga.edu", "wrong password")
    accounts.log_in("sam@uga.edu", PASSWORD)


# ---- saved preferences ----


def test_preferences_come_back_after_logging_in_again(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    _, user = accounts.sign_up("alex@uga.edu", PASSWORD)
    accounts.save_preferences(user.id, SavedPreferences(**PREFS))

    _, again = accounts.log_in("alex@uga.edu", PASSWORD)
    saved = again.preferences.model_dump(mode="json")
    assert saved["name"] == "Alex"
    assert saved["majors"] == ["computer-science"]
    assert saved["interests"] == ["technology-coding:ai", "music"]
    assert saved["busy"] == [{"day": "mon", "start": "09:00", "end": "09:50"}]  # "09:00", not "09:00:00"


def test_saving_again_replaces_the_old_preferences(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    token, user = accounts.sign_up("alex@uga.edu", PASSWORD)
    accounts.save_preferences(user.id, SavedPreferences(**PREFS))
    accounts.save_preferences(user.id, SavedPreferences(majors=["undecided"], interests=["music"]))
    now = accounts.user_for_token(token).preferences
    assert now.majors == ["undecided"] and now.interests == ["music"] and now.busy == [] and now.name == ""


def test_each_account_keeps_its_own_preferences(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    _, alex = accounts.sign_up("alex@uga.edu", PASSWORD)
    sam_token, _ = accounts.sign_up("sam@uga.edu", PASSWORD)
    accounts.save_preferences(alex.id, SavedPreferences(**PREFS))
    assert accounts.user_for_token(sam_token).preferences is None


def test_preferences_that_no_longer_fit_the_questionnaire_are_ignored(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    token, user = accounts.sign_up("alex@uga.edu", PASSWORD)
    # Pretend an interest was renamed after this was saved.
    accounts.db.execute(
        "UPDATE users SET preferences = ? WHERE id = ?",
        ('{"majors": ["computer-science"], "interests": ["old-removed-interest"]}', user.id),
    )
    assert accounts.user_for_token(token).preferences is None
    accounts.db.execute("UPDATE users SET preferences = ? WHERE id = ?", ("not json at all", user.id))
    assert accounts.user_for_token(token).preferences is None


# ---- saved calendar ----

CALENDAR = {
    "saved": [
        {
            "id": "e1", "title": "Guitar Circle", "description": None, "start": "2026-11-12T18:00:00-05:00",
            "end": "2026-11-12T19:00:00-05:00", "end_is_estimated": True, "location": "Tate Plaza",
            "organizer": "Guitar Club", "url": None, "interest_tags": ["music:guitar"],
            "reason": "Matches your interest", "match_kind": "interest", "conflicts_with": ["e2"],  # not kept
        }
    ],
    "personal": [{"id": "p1", "title": "Study group", "date": "2026-11-11", "time": "15:30", "end_time": ""}],
}


def test_a_new_account_has_no_calendar(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    _, user = accounts.sign_up("alex@uga.edu", PASSWORD)
    assert user.calendar is None


def test_the_calendar_comes_back_after_logging_in_again(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    _, user = accounts.sign_up("alex@uga.edu", PASSWORD)
    accounts.save_calendar(user.id, SavedCalendar(**CALENDAR))

    _, again = accounts.log_in("alex@uga.edu", PASSWORD)
    saved = again.calendar.model_dump(mode="json")
    assert saved["personal"] == CALENDAR["personal"]
    assert saved["saved"][0]["title"] == "Guitar Circle"
    assert saved["saved"][0]["start"].startswith("2026-11-12T18:00:00")
    assert "conflicts_with" not in saved["saved"][0] and "reason" not in saved["saved"][0]


def test_saving_the_calendar_again_replaces_it(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    token, user = accounts.sign_up("alex@uga.edu", PASSWORD)
    accounts.save_calendar(user.id, SavedCalendar(**CALENDAR))
    accounts.save_calendar(user.id, SavedCalendar(saved=[], personal=[]))
    now = accounts.user_for_token(token).calendar
    assert now.saved == [] and now.personal == []
    assert len(accounts.db.query("SELECT * FROM calendars")) == 1  # updated in place, not added


def test_each_account_keeps_its_own_calendar(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    _, alex = accounts.sign_up("alex@uga.edu", PASSWORD)
    sam_token, _ = accounts.sign_up("sam@uga.edu", PASSWORD)
    accounts.save_calendar(alex.id, SavedCalendar(**CALENDAR))
    assert accounts.user_for_token(sam_token).calendar is None


def test_an_unreadable_saved_calendar_is_ignored(tmp_path):
    accounts, _ = make_accounts(tmp_path)
    token, user = accounts.sign_up("alex@uga.edu", PASSWORD)
    accounts.db.execute("INSERT INTO calendars (user_id, data, updated_at) VALUES (?, ?, ?)", (user.id, "not json", 1))
    assert accounts.user_for_token(token).calendar is None


# ---- the database ----


def test_the_tables_can_be_made_more_than_once(tmp_path):
    database = Database(url="", sqlite_path=tmp_path / "sub" / "accounts.db")  # folder is created too
    database.create_tables()
    database.create_tables()
    assert (tmp_path / "sub" / "accounts.db").is_file()


def test_the_accounts_survive_a_restart(tmp_path):
    first, clock = make_accounts(tmp_path)
    first.sign_up("alex@uga.edu", PASSWORD)
    second, _ = make_accounts(tmp_path, clock)  # a "new" server reading the same file
    second.log_in("alex@uga.edu", PASSWORD)


def test_postgres_gets_its_own_placeholders():
    assert Database(url="postgresql://x/y")._sql("a = ? AND b = ?") == "a = %s AND b = %s"
    assert Database(url="")._sql("a = ? AND b = ?") == "a = ? AND b = ?"


def test_an_unreachable_database_gives_a_clear_error(tmp_path):
    database = Database(url="postgresql://nobody:wrong@127.0.0.1:1/nothing", sqlite_path=tmp_path / "x.db")
    with pytest.raises(DatabaseUnavailable):
        database.query("SELECT 1")
