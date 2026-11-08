"""Gives each event interest tags and the colleges it is meant for, using an AI model.

How it works (the plan is to ask as little as possible, as rarely as possible):

  1. Events whose text we have already tagged come straight from the cache.
  2. The rest go to the AI in small batches, in two short steps:
       step 1: pick interest CATEGORIES (48 to choose from) and COLLEGES (16)
       step 2: pick SPECIALTIES, but only from the categories chosen in step 1
  3. The AI's answer is never trusted. Every ID is checked against app/taxonomy.py,
     made-up IDs are dropped, and each list is capped.
  4. If the AI fails for an event, that event is reported as failed and is NOT
     cached, so the next run tries it again.

The AI only ever sees the event text. It never sees a student's profile.

Save this file as: app/tagging/tagger.py
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from app import taxonomy
from app.ai.llm_client import LLMClient, LLMError, LLMUnavailable

logger = logging.getLogger(__name__)

# app/tagging/tagger.py -> parents[2] is the project root (the backend folder).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = "data/cache/tag_cache.json"

# Change this whenever the prompts change, so old cached answers are not reused.
PROMPT_VERSION = "1"

DEFAULT_BATCH_SIZE = 5  # free tiers limit the NUMBER of requests, so send several events at once
MAX_TEXT_CHARS = 1500  # flyer text beyond this is cut off before it goes to the AI
MAX_CATEGORIES = 3
MAX_SPECIALTIES = 4
MAX_COLLEGES = 3


@dataclass
class TagInput:
    id: str  # your own ID for the event (for example the flyer_id)
    text: str  # everything we know about the event (flyer text, title, description)


@dataclass
class TagResult:
    # Specialties (which imply their category), plus any category that got no specialty.
    interest_tags: list[str] = field(default_factory=list)
    # Empty means "open to every college".
    relevant_colleges: list[str] = field(default_factory=list)


@dataclass
class TaggingOutcome:
    tags: dict[str, TagResult] = field(default_factory=dict)  # event id -> tags
    failed: dict[str, str] = field(default_factory=dict)  # event id -> why it failed
    from_cache: int = 0  # how many of `tags` came from the cache (no AI call)
    cached_ids: list[str] = field(default_factory=list)  # which events came from the cache


class _BadAnswer(Exception):
    """The AI's reply was not usable (not JSON, wrong shape)."""


# ---------------------------------------------------------------- prompts

_STEP1 = """You label University of Georgia campus events from their flyer text.

For each event, choose:
- categories: the interest categories the event belongs to (at most {max_categories}; none if nothing fits)
- colleges: the colleges the event is clearly aimed at (at most {max_colleges}). If the event is open to all students, return an empty list.

Use only IDs from the lists below. Base your answer only on the event text.

CATEGORIES:
{categories}

COLLEGES:
{colleges}

EVENTS:
{events}"""

_STEP2 = """You label University of Georgia campus events from their flyer text.

Each event below already has its interest categories. Choose the specific specialties that clearly apply to each event (at most {max_specialties}; none if no specialty clearly fits). Use only IDs from the list below. Base your answer only on the event text.

SPECIALTIES:
{specialties}

EVENTS:
{events}"""


def _clean(text: str) -> str:
    """One line of text, cut to a sensible length."""
    return " ".join(text.split())[:MAX_TEXT_CHARS]


def _id_list(values: list[str], max_items: int) -> dict:
    return {"type": "array", "items": {"type": "string", "enum": values}, "maxItems": max_items}


def _schema(ids: list[str], fields: dict) -> dict:
    """The shape the AI's answer must have: {"results": [{"id": ..., <fields>}, ...]}."""
    item = {
        "type": "object",
        "properties": {"id": {"type": "string", "enum": ids}, **fields},
        "required": ["id", *fields],
    }
    return {
        "type": "object",
        "properties": {"results": {"type": "array", "items": item}},
        "required": ["results"],
    }


@lru_cache(maxsize=1)
def _taxonomy_fingerprint() -> str:
    """Changes whenever the tag lists change, so old cached answers stop being reused."""
    basis = "\n".join(sorted(taxonomy.LABELS)) + "\n" + "\n".join(taxonomy.COLLEGE_IDS)
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- checking the AI's answers


def _valid_categories(values) -> list[str]:
    return taxonomy.keep_valid(values if isinstance(values, list) else [], taxonomy.CATEGORY_IDS)[:MAX_CATEGORIES]


def _valid_colleges(values) -> list[str]:
    return taxonomy.keep_valid(values if isinstance(values, list) else [], taxonomy.COLLEGE_IDS)[:MAX_COLLEGES]


def _valid_specialties(values, categories: list[str]) -> list[str]:
    kept = taxonomy.keep_valid(values if isinstance(values, list) else [], list(taxonomy.PARENTS))
    # A specialty only counts if its category was chosen for this same event.
    return [s for s in kept if taxonomy.PARENTS[s] in categories][:MAX_SPECIALTIES]


def _combine(categories: list[str], specialties: list[str], colleges: list[str]) -> TagResult:
    """Specialties already imply their category, so a category is kept only if it has none."""
    covered = {taxonomy.PARENTS[s] for s in specialties}
    return TagResult(
        interest_tags=specialties + [c for c in categories if c not in covered],
        relevant_colleges=colleges,
    )


def _parse(raw: str, ids: set[str]) -> dict[str, dict]:
    """Turn the AI's JSON text into {event id: its answer}. Unknown IDs are ignored."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise _BadAnswer(f"the reply was not valid JSON ({exc})") from exc
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise _BadAnswer('the reply had no "results" list')
    answers: dict[str, dict] = {}
    for item in results:
        if isinstance(item, dict) and item.get("id") in ids and item["id"] not in answers:
            answers[item["id"]] = item
    return answers


# ---------------------------------------------------------------- the tagger


class Tagger:
    def __init__(
        self,
        client: LLMClient,
        batch_size: int = DEFAULT_BATCH_SIZE,
        cache_path: Path | None = None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.client = client
        self.batch_size = batch_size
        self.cache_path = cache_path or PROJECT_ROOT / CACHE_PATH

    # ---- cache ----

    def _key(self, item: TagInput) -> str:
        """Same text + same prompts + same tag lists + same model = same answer."""
        basis = "|".join([PROMPT_VERSION, _taxonomy_fingerprint(), self.client.model, _clean(item.text)])
        return hashlib.sha256(basis.encode()).hexdigest()

    def _load_cache(self) -> dict[str, dict]:
        if not self.cache_path.is_file():
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            logger.warning("Tag cache file was unreadable, starting fresh")
            return {}

    def _save_cache(self, cache: dict[str, dict]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.cache_path.with_suffix(".tmp")  # write a temp file first so a crash can't corrupt the cache
        temp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        temp.replace(self.cache_path)

    # ---- asking the AI ----

    def _ask(self, prompt: str, schema: dict, ids: list[str]) -> dict[str, dict]:
        """Ask once; if the reply is unusable, ask one more time."""
        problem = ""
        for _attempt in range(2):
            answers = None
            raw = self.client.complete_json(prompt, schema)
            try:
                answers = _parse(raw, set(ids))
            except _BadAnswer as exc:
                problem = str(exc)
                logger.warning("Unusable AI reply (%s), trying again", problem)
            if answers is not None:
                return answers
        raise _BadAnswer(problem)

    def _tag_batch(self, batch: list[TagInput]) -> tuple[dict[str, TagResult], dict[str, str]]:
        """Tag a few events. Returns (results, errors); every event is in exactly one."""
        ids = [item.id for item in batch]
        results: dict[str, TagResult] = {}
        errors: dict[str, str] = {}
        try:
            # Step 1: categories and colleges. The long fixed lists come BEFORE the
            # events, so the model can reuse its work on them from call to call.
            prompt = _STEP1.format(
                max_categories=MAX_CATEGORIES,
                max_colleges=MAX_COLLEGES,
                categories=taxonomy.prompt_categories(),
                colleges=taxonomy.prompt_colleges(),
                events="\n".join(f"[id: {i.id}]\n{_clean(i.text)}\n" for i in batch),
            )
            schema = _schema(ids, {
                "categories": _id_list(taxonomy.CATEGORY_IDS, MAX_CATEGORIES),
                "colleges": _id_list(taxonomy.COLLEGE_IDS, MAX_COLLEGES),
            })
            step1 = self._ask(prompt, schema, ids)

            categories: dict[str, list[str]] = {}
            colleges: dict[str, list[str]] = {}
            for item in batch:
                answer = step1.get(item.id)
                if answer is None:
                    errors[item.id] = "the model skipped this event"
                    continue
                categories[item.id] = _valid_categories(answer.get("categories"))
                colleges[item.id] = _valid_colleges(answer.get("colleges"))

            # Step 2: specialties, but only for events that got at least one category,
            # and only from the specialties of the categories chosen in step 1.
            needs_step2 = [i for i in batch if categories.get(i.id)]
            specialties: dict[str, list[str]] = {}
            if needs_step2:
                chosen = list(dict.fromkeys(c for i in needs_step2 for c in categories[i.id]))
                lines = taxonomy.prompt_children(chosen)
                allowed = [child["id"] for c in chosen for child in taxonomy.children_of(c)]
                step2_ids = [i.id for i in needs_step2]
                prompt = _STEP2.format(
                    max_specialties=MAX_SPECIALTIES,
                    specialties=lines,
                    events="\n".join(
                        f"[id: {i.id}] (categories: {', '.join(categories[i.id])})\n{_clean(i.text)}\n"
                        for i in needs_step2
                    ),
                )
                schema = _schema(step2_ids, {"specialties": _id_list(allowed, MAX_SPECIALTIES)})
                step2 = self._ask(prompt, schema, step2_ids)
                for item in needs_step2:
                    answer = step2.get(item.id)
                    if answer is None:
                        errors[item.id] = "the model skipped this event in step 2"
                        continue
                    specialties[item.id] = _valid_specialties(answer.get("specialties"), categories[item.id])

            for item in batch:
                if item.id not in errors:
                    results[item.id] = _combine(
                        categories[item.id], specialties.get(item.id, []), colleges[item.id]
                    )
        except LLMUnavailable:
            raise  # nothing will work until the service is back, so stop the whole run
        except (_BadAnswer, LLMError) as exc:
            return {}, {item_id: str(exc) for item_id in ids}
        return results, errors

    # ---- the public method ----

    def tag(self, items: list[TagInput], use_cache: bool = True) -> TaggingOutcome:
        """Tag every event. Never raises for a single bad event: see `outcome.failed`.

        Raises LLMUnavailable if the AI service can't be reached at all.
        """
        ids = [item.id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Event ids must be unique.")

        outcome = TaggingOutcome()
        cache = self._load_cache()
        logger.info("Tag cache: %s (%d saved answers)", self.cache_path, len(cache))
        todo: list[TagInput] = []
        for item in items:
            if not _clean(item.text):
                outcome.tags[item.id] = TagResult()  # nothing to read, so nothing to tag
                continue
            cached = cache.get(self._key(item)) if use_cache else None
            if cached is not None:
                outcome.tags[item.id] = TagResult(**cached)
                outcome.from_cache += 1
                outcome.cached_ids.append(item.id)
            else:
                todo.append(item)

        batches = [todo[i : i + self.batch_size] for i in range(0, len(todo), self.batch_size)]
        for number, batch in enumerate(batches, start=1):
            logger.info("Tagging batch %d of %d (%d events)", number, len(batches), len(batch))
            results, errors = self._tag_batch(batch)
            if errors and len(batch) > 1:
                # One awkward event can spoil a batch, so give each failed one its own try.
                for item in [i for i in batch if i.id in errors]:
                    again, still_failed = self._tag_batch([item])
                    errors.pop(item.id)
                    results.update(again)
                    errors.update(still_failed)
            for item in batch:
                if item.id in results:
                    outcome.tags[item.id] = results[item.id]
                    cache[self._key(item)] = asdict(results[item.id])
            outcome.failed.update(errors)
            self._save_cache(cache)  # after every batch: a long run keeps its progress if it stops
        return outcome