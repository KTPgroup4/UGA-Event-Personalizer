"""The web server. Start it from the backend folder with:

    python -m uvicorn app.main:app --reload --port 3000

(Port 3000 is where the frontend's dev proxy in vite.config.ts looks for us.)
Then open http://localhost:3000/docs to try every endpoint in the browser.

Save this file as: app/main.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import auth_routes, event_store, flyer_listing, schedules_service, taxonomy
from app.database import DatabaseUnavailable
from app.schemas.user_profile import UserProfile

app = FastAPI(title="UGA Event Personalizer API")
app.include_router(auth_routes.router)  # sign up, log in, saved preferences


@app.exception_handler(DatabaseUnavailable)
def database_unavailable(request, exc: DatabaseUnavailable):
    """If the accounts database can't be reached, say so plainly instead of a vague 500."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    """Quick check that the server is running."""
    return {"status": "ok"}


@app.get("/api/options")
def options():
    """Every choice the questionnaire shows (see docs/api_contract.md)."""
    return taxonomy.questionnaire_options()


@app.post("/api/schedules")
def schedules(profile: UserProfile):
    """The student's swipe deck (see docs/api_contract.md). Reads the events saved by
    the weekly job, so no AI is called here. An invalid profile gets a 422 automatically."""
    try:
        events = event_store.load_events()
    except event_store.NoEventsYet as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return schedules_service.build_response(profile, events)


@app.get("/api/flyers")
def flyers():
    """TEMPORARY helper for frontend development: the flyers we have, their saved
    text, and where to load each picture from. Not part of the final product flow."""
    try:
        items = flyer_listing.list_flyers()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"count": len(items), "flyers": items}


# Serves the pictures in data/flyers/ at /api/flyer-images/<filename>.
# The folder must exist or every image request would crash, so make sure it does.
flyer_listing.FLYERS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    flyer_listing.IMAGE_URL_PREFIX,
    StaticFiles(directory=flyer_listing.FLYERS_DIR),
    name="flyer-images",
)
