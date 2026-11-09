"""Where accounts are stored.

Two options, chosen by one line in .env (or in the Render dashboard):

  - Nothing set (the default, for working on your own computer):
        a small file, data/accounts.db. It needs no setup. NEVER commit it: it holds
        people's emails.
  - DATABASE_URL=postgresql://...  (for the live website):
        a free Postgres database from Neon. The live site needs this because Render's free
        plan wipes the server's files every time it restarts, which would delete every account.

The rest of the backend just calls execute() and query(); it does not care which one is used.
Write SQL with "?" for values, like  query("SELECT * FROM users WHERE email = ?", (email,)).

Save this file as: app/database.py
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # the API process may not have read .env yet

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # the backend folder
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "accounts.db"

log = logging.getLogger("dawgmatch.database")


class DatabaseUnavailable(Exception):
    """The accounts database can't be reached. The message is fine to show the user."""


def database_url() -> str:
    """The DATABASE_URL from .env, or "" when we should use the local file."""
    return os.getenv("DATABASE_URL", "").strip()


class Database:
    def __init__(self, url: str | None = None, sqlite_path: Path | None = None):
        # `url` of None means "read DATABASE_URL"; "" means "use the local file".
        self.url = database_url() if url is None else url
        self.sqlite_path = Path(sqlite_path or DEFAULT_SQLITE_PATH)

    @property
    def is_postgres(self) -> bool:
        return bool(self.url)

    @contextmanager
    def _connection(self):
        """Open a connection for one piece of work, then close it. Every statement is saved
        right away (autocommit), so there is nothing to commit by hand."""
        try:
            if self.is_postgres:
                import psycopg  # only needed (and only imported) when DATABASE_URL is set

                connection = psycopg.connect(
                    self.url,
                    autocommit=True,
                    connect_timeout=20,  # a sleeping free database can take a few seconds to wake
                    prepare_threshold=None,  # keeps Neon's connection pooler happy
                )
            else:
                self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(self.sqlite_path, timeout=10, isolation_level=None)
        except ImportError as exc:
            log.error("DATABASE_URL is set but psycopg is not installed: %s", exc)
            raise DatabaseUnavailable(
                "Accounts are not available: the database driver is missing. Run: pip install -r requirements.txt"
            ) from exc
        except Exception as exc:  # a wrong password, a typo in the URL, no internet...
            log.error("Could not connect to the accounts database: %s", exc)
            raise DatabaseUnavailable(
                "Accounts are not available right now (could not reach the database). Please try again in a minute."
            ) from exc
        try:
            yield connection
        finally:
            connection.close()

    def _sql(self, sql: str) -> str:
        # SQLite writes the placeholder as "?", Postgres as "%s". We write "?" everywhere.
        return sql.replace("?", "%s") if self.is_postgres else sql

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Run INSERT / UPDATE / DELETE / CREATE. Returns how many rows changed."""
        with self._connection() as connection:
            return connection.execute(self._sql(sql), params).rowcount

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Run a SELECT and return all rows as tuples."""
        with self._connection() as connection:
            return connection.execute(self._sql(sql), params).fetchall()

    def create_tables(self) -> None:
        """Make the tables if they are not there yet. Safe to run every time the server starts."""
        self.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id TEXT PRIMARY KEY,
                   email TEXT NOT NULL UNIQUE,
                   password_hash TEXT NOT NULL,
                   preferences TEXT,
                   created_at BIGINT NOT NULL
               )"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS calendars (
                   user_id TEXT PRIMARY KEY,
                   data TEXT NOT NULL,
                   updated_at BIGINT NOT NULL
               )"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                   token_hash TEXT PRIMARY KEY,
                   user_id TEXT NOT NULL,
                   created_at BIGINT NOT NULL,
                   expires_at BIGINT NOT NULL
               )"""
        )
