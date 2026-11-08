"""Tests for the AI tagger, using a fake AI so they are fast and need no Ollama.

Save this file as: tests/test_tagger.py
Run from the backend folder with:  python -m pytest
"""

import json

import pytest

from app import taxonomy
from app.ai.llm_client import LLMError, LLMRateLimited, LLMUnavailable
from app.tagging import tagger as tagger_module
from app.tagging.tagger import MAX_TEXT_CHARS, TagInput, Tagger

ENGINEERING_CHILDREN = [c["id"] for c in taxonomy.children_of("engineering-making")]


class FakeLLM:
    """Pretends to be the AI. By default it answers from `plan` and obeys the schema.

    plan:   {event id: {"categories": [...], "colleges": [...], "specialties": [...]}}
    script: answers to use for the first calls, in order. A string is returned as
            the raw reply, an Exception is raised, None means "answer normally".
    """

    def __init__(self, plan=None, script=None, model="fake-model"):
        self.plan = plan or {}
        self.script = list(script or [])
        self.model = model
        self.calls = []

    def complete_json(self, prompt, schema):
        self.calls.append((prompt, schema))
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            if step is not None:
                return step
        fields = schema["properties"]["results"]["items"]["properties"]
        results = []
        for event_id in fields["id"]["enum"]:
            entry = {"id": event_id}
            for name in fields:
                if name != "id":
                    entry[name] = self.plan.get(event_id, {}).get(name, [])
            results.append(entry)
        return json.dumps({"results": results})


def make_tagger(llm, tmp_path, batch_size=2):
    return Tagger(llm, batch_size=batch_size, cache_path=tmp_path / "tag_cache.json")


def one(event_id="a", text="Guitar night with the music club"):
    return [TagInput(event_id, text)]


MUSIC_PLAN = {"a": {"categories": ["music"], "colleges": ["franklin"], "specialties": ["music:guitar"]}}


# ---- what comes out ----


def test_specialties_replace_their_category_and_bare_categories_stay(tmp_path):
    plan = {"a": {"categories": ["music", "technology-coding"], "colleges": ["franklin"],
                  "specialties": ["music:guitar"]}}
    outcome = make_tagger(FakeLLM(plan), tmp_path).tag(one())
    result = outcome.tags["a"]
    assert result.interest_tags == ["music:guitar", "technology-coding"]
    assert result.relevant_colleges == ["franklin"]
    assert outcome.failed == {}


def test_an_event_with_no_categories_skips_step_two(tmp_path):
    llm = FakeLLM({"a": {"categories": [], "colleges": []}})
    outcome = make_tagger(llm, tmp_path).tag(one())
    assert outcome.tags["a"].interest_tags == [] and outcome.tags["a"].relevant_colleges == []
    assert len(llm.calls) == 1


def test_made_up_ids_and_mismatched_specialties_are_dropped(tmp_path):
    plan = {"a": {"categories": ["music", "made-up"], "colleges": ["not-a-college", "terry"],
                  "specialties": ["music:guitar", "technology-coding:ai", "music:kazoo"]}}
    result = make_tagger(FakeLLM(plan), tmp_path).tag(one()).tags["a"]
    # technology-coding:ai is real but its category was not chosen for this event.
    assert result.interest_tags == ["music:guitar"]
    assert result.relevant_colleges == ["terry"]


def test_categories_and_colleges_are_capped_at_three(tmp_path):
    plan = {"a": {"categories": ["music", "technology-coding", "career-leadership", "engineering-making"],
                  "colleges": ["franklin", "terry", "computing", "engineering"]}}
    result = make_tagger(FakeLLM(plan), tmp_path).tag(one()).tags["a"]
    assert result.interest_tags == ["music", "technology-coding", "career-leadership"]
    assert result.relevant_colleges == ["franklin", "terry", "computing"]


def test_specialties_are_capped_at_four(tmp_path):
    plan = {"a": {"categories": ["engineering-making"], "colleges": [], "specialties": ENGINEERING_CHILDREN[:6]}}
    result = make_tagger(FakeLLM(plan), tmp_path).tag(one()).tags["a"]
    assert result.interest_tags == ENGINEERING_CHILDREN[: tagger_module.MAX_SPECIALTIES]


def test_blank_text_is_not_sent_to_the_ai(tmp_path):
    llm = FakeLLM()
    outcome = make_tagger(llm, tmp_path).tag([TagInput("a", "  \n ")])
    assert outcome.tags["a"].interest_tags == [] and llm.calls == []


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        make_tagger(FakeLLM(), tmp_path).tag([TagInput("a", "x"), TagInput("a", "y")])


# ---- the prompts and schemas ----


def test_step_one_lists_the_choices_before_the_events(tmp_path):
    llm = FakeLLM()
    make_tagger(llm, tmp_path).tag(one(text="Unique flyer words here"))
    prompt = llm.calls[0][0]
    assert prompt.index("CATEGORIES:") < prompt.index("COLLEGES:") < prompt.index("EVENTS:")
    assert prompt.index("EVENTS:") < prompt.index("Unique flyer words here")
    assert "music: Music" in prompt and "computing: School of Computing" in prompt


def test_long_flyer_text_is_cut_before_it_is_sent(tmp_path):
    llm = FakeLLM()
    make_tagger(llm, tmp_path).tag(one(text="x" * (MAX_TEXT_CHARS + 500)))
    prompt = llm.calls[0][0]
    assert "x" * MAX_TEXT_CHARS in prompt and "x" * (MAX_TEXT_CHARS + 1) not in prompt


def test_step_two_only_offers_specialties_of_the_chosen_categories(tmp_path):
    llm = FakeLLM(MUSIC_PLAN)
    make_tagger(llm, tmp_path).tag(one())
    prompt, schema = llm.calls[1]
    allowed = schema["properties"]["results"]["items"]["properties"]["specialties"]["items"]["enum"]
    assert "music:guitar" in prompt and "technology-coding:ai" not in prompt
    assert "music:guitar" in allowed and "technology-coding:ai" not in allowed
    assert "(categories: music)" in prompt


def test_the_schema_only_allows_real_ids(tmp_path):
    llm = FakeLLM()
    make_tagger(llm, tmp_path).tag(one())
    fields = llm.calls[0][1]["properties"]["results"]["items"]["properties"]
    assert fields["categories"]["items"]["enum"] == taxonomy.CATEGORY_IDS
    assert fields["colleges"]["items"]["enum"] == taxonomy.COLLEGE_IDS
    assert fields["id"]["enum"] == ["a"]


# ---- batching ----


def test_events_are_sent_in_batches(tmp_path):
    llm = FakeLLM()
    items = [TagInput(f"e{n}", f"event number {n}") for n in range(5)]
    outcome = make_tagger(llm, tmp_path, batch_size=2).tag(items)
    assert len(llm.calls) == 3  # 2 + 2 + 1 events, and none got a category so no step 2
    assert set(outcome.tags) == {f"e{n}" for n in range(5)}


# ---- the cache ----


def test_a_second_run_uses_the_cache_and_asks_nothing(tmp_path):
    first = FakeLLM(MUSIC_PLAN)
    make_tagger(first, tmp_path).tag(one())
    second = FakeLLM(MUSIC_PLAN)
    outcome = make_tagger(second, tmp_path).tag(one())
    assert second.calls == []
    assert outcome.from_cache == 1 and outcome.tags["a"].interest_tags == ["music:guitar"]
    assert outcome.cached_ids == ["a"]


def test_changed_text_or_a_different_model_is_asked_again(tmp_path):
    make_tagger(FakeLLM(MUSIC_PLAN), tmp_path).tag(one())
    changed_text = FakeLLM(MUSIC_PLAN)
    make_tagger(changed_text, tmp_path).tag(one(text="Different flyer text"))
    assert changed_text.calls
    other_model = FakeLLM(MUSIC_PLAN, model="another-model")
    make_tagger(other_model, tmp_path).tag(one())
    assert other_model.calls


def test_use_cache_false_asks_again(tmp_path):
    make_tagger(FakeLLM(MUSIC_PLAN), tmp_path).tag(one())
    llm = FakeLLM(MUSIC_PLAN)
    make_tagger(llm, tmp_path).tag(one(), use_cache=False)
    assert llm.calls


def test_a_broken_cache_file_is_ignored(tmp_path):
    (tmp_path / "tag_cache.json").write_text("{not json", encoding="utf-8")
    outcome = make_tagger(FakeLLM(MUSIC_PLAN), tmp_path).tag(one())
    assert outcome.tags["a"].interest_tags == ["music:guitar"]


# ---- when the AI misbehaves ----


def test_an_unusable_reply_is_retried_once(tmp_path):
    llm = FakeLLM(MUSIC_PLAN, script=["this is not json"])
    outcome = make_tagger(llm, tmp_path).tag(one())
    assert outcome.tags["a"].interest_tags == ["music:guitar"]
    assert len(llm.calls) == 3  # step 1 twice, step 2 once


def test_two_unusable_replies_mean_failed_and_not_cached(tmp_path):
    llm = FakeLLM(MUSIC_PLAN, script=["nope", "still nope"])
    outcome = make_tagger(llm, tmp_path).tag(one())
    assert "a" not in outcome.tags and "not valid JSON" in outcome.failed["a"]
    # Next run tries again instead of remembering the failure.
    retry = make_tagger(FakeLLM(MUSIC_PLAN), tmp_path).tag(one())
    assert retry.tags["a"].interest_tags == ["music:guitar"] and retry.from_cache == 0


def test_a_reply_without_the_results_list_is_unusable(tmp_path):
    llm = FakeLLM(script=['{"answer": 1}', '{"answer": 2}'])
    assert "results" in make_tagger(llm, tmp_path).tag(one()).failed["a"]


def test_a_skipped_event_in_step_two_is_a_failure(tmp_path):
    llm = FakeLLM(MUSIC_PLAN, script=[None, '{"results": []}'])
    outcome = make_tagger(llm, tmp_path).tag(one())
    assert "skipped" in outcome.failed["a"] and "a" not in outcome.tags


def test_a_skipped_event_gets_its_own_second_try(tmp_path):
    plan = {"a": {"categories": []}, "b": {"categories": ["music"], "specialties": ["music:guitar"]}}
    only_a = json.dumps({"results": [{"id": "a", "categories": [], "colleges": []}]})
    llm = FakeLLM(plan, script=[only_a])
    items = [TagInput("a", "first event"), TagInput("b", "second event")]
    outcome = make_tagger(llm, tmp_path, batch_size=2).tag(items)
    assert outcome.failed == {}
    assert outcome.tags["a"].interest_tags == [] and outcome.tags["b"].interest_tags == ["music:guitar"]
    assert len(llm.calls) == 3  # the pair, then b alone (step 1 and step 2)


def test_a_model_error_on_a_batch_falls_back_to_one_event_at_a_time(tmp_path):
    llm = FakeLLM(script=[LLMError("timed out")])
    items = [TagInput("a", "first"), TagInput("b", "second")]
    outcome = make_tagger(llm, tmp_path, batch_size=2).tag(items)
    assert outcome.failed == {} and set(outcome.tags) == {"a", "b"}


def test_a_model_error_on_a_single_event_is_reported_not_raised(tmp_path):
    outcome = make_tagger(FakeLLM(script=[LLMError("timed out")]), tmp_path).tag(one())
    assert outcome.failed == {"a": "timed out"}


def test_an_unreachable_model_stops_the_run(tmp_path):
    llm = FakeLLM(script=[LLMUnavailable("Ollama is not running")])
    with pytest.raises(LLMUnavailable, match="not running"):
        make_tagger(llm, tmp_path).tag(one())


def test_hitting_a_rate_limit_stops_the_run_but_keeps_finished_work(tmp_path):
    llm = FakeLLM(script=[None, LLMRateLimited("free-tier limit reached")])
    items = [TagInput("a", "first"), TagInput("b", "second"), TagInput("c", "third")]
    with pytest.raises(LLMRateLimited, match="limit"):
        make_tagger(llm, tmp_path, batch_size=1).tag(items)
    assert len(llm.calls) == 2  # it stopped; it did not keep hammering the service
    assert len(json.loads((tmp_path / "tag_cache.json").read_text(encoding="utf-8"))) == 1


def test_progress_is_saved_after_every_batch(tmp_path):
    # Batch 1 works, then the model goes away during batch 2.
    llm = FakeLLM(script=[None, LLMUnavailable("down")])
    items = [TagInput("a", "first"), TagInput("b", "second")]
    with pytest.raises(LLMUnavailable):
        make_tagger(llm, tmp_path, batch_size=1).tag(items)
    saved = json.loads((tmp_path / "tag_cache.json").read_text(encoding="utf-8"))
    assert len(saved) == 1