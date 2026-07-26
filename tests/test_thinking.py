from __future__ import annotations

from infrastructure.llm.thinking import strip_thinking


def test_removes_a_complete_think_block():
    assert strip_thinking("<think>reasoning here</think>The answer.") == "The answer."


def test_removes_reasoning_before_a_lone_closing_tag():
    # qwen3 30b often emits reasoning then </think> with no opening tag.
    leaked = "Okay, the user asked. I used the tool.</think>\n\nThe deck is ready."
    assert strip_thinking(leaked) == "The deck is ready."


def test_leaves_clean_text_untouched():
    assert strip_thinking("Just a normal reply.") == "Just a normal reply."


def test_handles_multiple_blocks():
    text = "<think>a</think>First.<think>b</think> Second."
    assert "think" not in strip_thinking(text).lower()
    assert "Second." in strip_thinking(text)


def test_none_and_empty():
    assert strip_thinking(None) == ""
    assert strip_thinking("") == ""
