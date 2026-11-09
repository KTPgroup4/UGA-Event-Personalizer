"""The account endpoints: sign up, log in, log out, "who am I", and saving preferences.

See docs/api_contract.md, section "Accounts". The browser keeps the session token it gets
from sign up / log in, and sends it back as the header  Authorization: Bearer <token>.

Save this file as: app/auth_routes.py
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app import accounts as accounts_module
from app.accounts import Accounts, User, get_accounts
from app.schemas.calendar import SavedCalendar
from app.schemas.preferences import SavedPreferences

router = APIRouter(prefix="/api")


class Credentials(BaseModel):
    email: str
    password: str


def user_json(user: User) -> dict:
    preferences = user.preferences.model_dump(mode="json") if user.preferences else None
    calendar = user.calendar.model_dump(mode="json") if user.calendar else None
    return {"email": user.email, "preferences": preferences, "calendar": calendar}


def bearer_token(authorization: str | None) -> str:
    """The token from an 'Authorization: Bearer <token>' header, or "" if there isn't one."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def current_token(authorization: str | None = Header(default=None)) -> str:
    return bearer_token(authorization)


def current_user(token: str = Depends(current_token), accounts: Accounts = Depends(get_accounts)) -> User:
    """Used by every endpoint that needs a logged-in student. Answers 401 if there isn't one."""
    user = accounts.user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in again.")
    return user


@router.post("/auth/signup")
def sign_up(credentials: Credentials, accounts: Accounts = Depends(get_accounts)):
    """Make an account and log it in."""
    try:
        token, user = accounts.sign_up(credentials.email, credentials.password)
    except accounts_module.AccountError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"token": token, "user": user_json(user)}


@router.post("/auth/login")
def log_in(credentials: Credentials, accounts: Accounts = Depends(get_accounts)):
    """Log in with an email and password."""
    try:
        token, user = accounts.log_in(credentials.email, credentials.password)
    except accounts_module.AccountError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"token": token, "user": user_json(user)}


@router.post("/auth/logout")
def log_out(token: str = Depends(current_token), accounts: Accounts = Depends(get_accounts)):
    """End this session. Always succeeds, even if the token was already expired."""
    if token:
        accounts.log_out(token)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    """The logged-in student and their saved preferences (used when the page reopens)."""
    return {"user": user_json(user)}


@router.put("/me/preferences")
def save_preferences(
    preferences: SavedPreferences,
    user: User = Depends(current_user),
    accounts: Accounts = Depends(get_accounts),
):
    """Remember the questionnaire answers for next time. A bad value gets a 422, like /api/schedules."""
    accounts.save_preferences(user.id, preferences)
    return {"preferences": preferences.model_dump(mode="json")}


@router.put("/me/calendar")
def save_calendar(
    calendar: SavedCalendar,
    user: User = Depends(current_user),
    accounts: Accounts = Depends(get_accounts),
):
    """Remember the student's saved UGA events and the events they added themselves.
    Send the whole calendar every time; it replaces the old one."""
    accounts.save_calendar(user.id, calendar)
    return {"calendar": calendar.model_dump(mode="json")}
