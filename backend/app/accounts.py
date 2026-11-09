"""Student accounts: sign up, log in, log out, and remembering a student's preferences.

How it works, in plain words:
  - Sign up / log in with an email and a password. Passwords are never stored, only a
    salted scrypt "hash" of them (a scrambled fingerprint that can't be turned back).
  - A successful sign up or log in gives the browser a random "session token". The browser
    sends it back with every request ("Authorization: Bearer <token>") to prove who it is.
    We store only a hash of the token, so even someone who reads the database can't use it.
  - Tokens last 30 days, or until the student logs out.
  - Too many wrong passwords for one email in a short time are refused for a while.

This file knows nothing about the web. app/auth_routes.py turns it into endpoints.

Save this file as: app/accounts.py
"""

import hashlib
import hmac
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import cache
from typing import Callable

from pydantic import ValidationError

from app.database import Database
from app.schemas.calendar import SavedCalendar
from app.schemas.preferences import SavedPreferences

SESSION_SECONDS = 30 * 24 * 60 * 60  # stay logged in for 30 days
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 254
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# scrypt settings (about 50 ms per password check, using 16 MB of memory)
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


# ---------------------------------------------------------------- errors


class AccountError(Exception):
    """Something the student should be told about. `status_code` is the HTTP status to send."""

    status_code = 400


class InvalidInput(AccountError):
    status_code = 422


class EmailTaken(AccountError):
    status_code = 409


class BadLogin(AccountError):
    status_code = 401


class TooManyAttempts(AccountError):
    status_code = 429


# ---------------------------------------------------------------- email and password rules


def normalize_email(raw) -> str:
    """Tidy an email (no spaces, lowercase) or raise InvalidInput."""
    email = raw.strip().lower() if isinstance(raw, str) else ""
    if len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email):
        raise InvalidInput("Enter a valid email address, like name@uga.edu.")
    return email


def check_new_password(password) -> str:
    """A new password must be 8 to 128 characters. Spaces are allowed and kept as typed."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidInput(f"Your password needs at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise InvalidInput(f"Your password can be at most {MAX_PASSWORD_LENGTH} characters.")
    return password


# ---------------------------------------------------------------- password hashing


def hash_password(password: str) -> str:
    """Scramble a password. The result looks like  scrypt$n$r$p$salt$hash  and includes
    everything needed to check a password against it later."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """True when `password` matches a hash made by hash_password()."""
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)  # compares in constant time


@cache
def _dummy_hash() -> str:
    # Checked when the email is unknown, so "no such account" takes as long as "wrong password".
    return hash_password("not-a-real-password")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- slowing down password guessing


class LoginThrottle:
    """Refuses an email for a while after too many wrong passwords.

    Kept in the server's memory, so it resets when the server restarts. That is fine for
    slowing down guessing; it is not a security system for a bank.
    """

    def __init__(self, max_failures: int = 8, window_seconds: int = 15 * 60, now: Callable[[], float] = time.time):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.now = now
        self._failures: dict[str, deque] = defaultdict(deque)

    def _recent(self, key: str) -> deque:
        failures = self._failures[key]
        while failures and failures[0] <= self.now() - self.window_seconds:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)  # don't remember emails forever
            return deque()
        return failures

    def check(self, key: str) -> None:
        if len(self._recent(key)) >= self.max_failures:
            raise TooManyAttempts("Too many wrong passwords. Please wait a few minutes and try again.")

    def failed(self, key: str) -> None:
        self._recent(key)
        self._failures[key].append(self.now())

    def succeeded(self, key: str) -> None:
        self._failures.pop(key, None)


# ---------------------------------------------------------------- the accounts themselves


@dataclass
class User:
    id: str
    email: str
    preferences: SavedPreferences | None = None
    calendar: SavedCalendar | None = None


def _read_preferences(text: str | None) -> SavedPreferences | None:
    """Saved preferences from the database, or None if there are none or they are out of date
    (for example an interest was renamed since they were saved). The student just fills the
    questionnaire in again, and that saves a fresh copy."""
    if not text:
        return None
    try:
        return SavedPreferences.model_validate_json(text)
    except ValidationError:
        return None


def _read_calendar(text: str | None) -> SavedCalendar | None:
    """The saved calendar from the database, or None if there is none or it can't be read."""
    if not text:
        return None
    try:
        return SavedCalendar.model_validate_json(text)
    except ValidationError:
        return None


class Accounts:
    def __init__(self, database: Database | None = None, now: Callable[[], float] = time.time, throttle: LoginThrottle | None = None):
        self.db = database or Database()
        self.now = now
        self.throttle = throttle or LoginThrottle(now=now)
        self.db.create_tables()

    # ---- sessions ----

    def _start_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = int(self.now())
        self.db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))  # tidy up old ones
        self.db.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (hash_token(token), user_id, now, now + SESSION_SECONDS),
        )
        return token

    def user_for_token(self, token: str) -> User | None:
        """The logged-in user for a session token, or None if it is unknown or has expired."""
        if not token:
            return None
        rows = self.db.query(
            "SELECT u.id, u.email, u.preferences FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?",
            (hash_token(token), int(self.now())),
        )
        if not rows:
            return None
        user_id, email, preferences = rows[0]
        return User(id=user_id, email=email, preferences=_read_preferences(preferences), calendar=self._load_calendar(user_id))

    def log_out(self, token: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))

    # ---- sign up and log in ----

    def sign_up(self, email, password) -> tuple[str, User]:
        """Make an account and log it in. Returns (session token, user)."""
        email = normalize_email(email)
        password = check_new_password(password)
        user_id = uuid.uuid4().hex
        created = self.db.execute(
            "INSERT INTO users (id, email, password_hash, preferences, created_at) VALUES (?, ?, ?, NULL, ?) "
            "ON CONFLICT (email) DO NOTHING",
            (user_id, email, hash_password(password), int(self.now())),
        )
        if created == 0:
            raise EmailTaken("An account with this email already exists. Try logging in instead.")
        return self._start_session(user_id), User(id=user_id, email=email)

    def log_in(self, email, password) -> tuple[str, User]:
        """Check an email and password. Returns (session token, user) or raises BadLogin."""
        try:
            email = normalize_email(email)
        except InvalidInput:
            raise BadLogin("That email or password is not right.") from None
        self.throttle.check(email)

        rows = self.db.query("SELECT id, password_hash, preferences FROM users WHERE email = ?", (email,))
        stored = rows[0][1] if rows else _dummy_hash()
        good = verify_password(password if isinstance(password, str) else "", stored)
        if not rows or not good:
            self.throttle.failed(email)
            # The same message for "no such email" and "wrong password", so nobody can use
            # the login form to find out which emails have accounts.
            raise BadLogin("That email or password is not right.")

        self.throttle.succeeded(email)
        user_id, _, preferences = rows[0]
        user = User(id=user_id, email=email, preferences=_read_preferences(preferences), calendar=self._load_calendar(user_id))
        return self._start_session(user_id), user

    # ---- preferences ----

    def save_preferences(self, user_id: str, preferences: SavedPreferences) -> None:
        self.db.execute("UPDATE users SET preferences = ? WHERE id = ?", (preferences.model_dump_json(), user_id))

    # ---- calendar ----

    def _load_calendar(self, user_id: str) -> SavedCalendar | None:
        rows = self.db.query("SELECT data FROM calendars WHERE user_id = ?", (user_id,))
        return _read_calendar(rows[0][0]) if rows else None

    def save_calendar(self, user_id: str, calendar: SavedCalendar) -> None:
        """Replace the whole saved calendar (the frontend always sends all of it)."""
        self.db.execute(
            "INSERT INTO calendars (user_id, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (user_id, calendar.model_dump_json(), int(self.now())),
        )


@cache
def get_accounts() -> Accounts:
    """The one shared Accounts object for the running server, made on first use."""
    return Accounts()
