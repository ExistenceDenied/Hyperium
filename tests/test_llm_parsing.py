from __future__ import annotations

from core.llm_parsing import extract_json_object


def test_extracts_object_from_surrounding_prose():
    assert extract_json_object('Sure — {"a": 1, "b": "x"} done') == {"a": 1, "b": "x"}


def test_strips_a_complete_think_block():
    assert extract_json_object('<think>hmm</think>{"ok": true}') == {"ok": True}


def test_strips_reasoning_before_a_lone_closing_tag():
    assert extract_json_object('Okay, deciding...</think>\n{"category": "reply"}') == {
        "category": "reply"
    }


def test_none_when_there_is_no_object():
    assert extract_json_object("no json here") is None
    assert extract_json_object("") is None
    assert extract_json_object(None) is None


def test_none_on_invalid_json():
    assert extract_json_object('{"a": }') is None


def test_none_on_a_non_object_value():
    assert extract_json_object("[1, 2, 3]") is None
