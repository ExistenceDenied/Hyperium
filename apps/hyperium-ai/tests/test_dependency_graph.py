import pytest

from core.execution.activity import Activity
from core.planning.dependency_graph import (
    CircularDependencyError,
    DependencyError,
    UnknownDependencyError,
    topological_order,
)


def activity(key: str, *depends_on: str) -> Activity:
    return Activity(key=key, name=key, depends_on=set(depends_on))


def keys(activities: list[Activity]) -> list[str]:
    return [item.key for item in activities]


def test_independent_activities_keep_their_original_order():
    given = [activity("a"), activity("b"), activity("c")]

    assert keys(topological_order(given)) == ["a", "b", "c"]


def test_dependencies_are_ordered_before_dependents():
    given = [
        activity("architecture", "requirements"),
        activity("test-plan", "architecture"),
        activity("requirements"),
    ]

    assert keys(topological_order(given)) == [
        "requirements",
        "architecture",
        "test-plan",
    ]


def test_a_diamond_resolves_with_the_join_last():
    given = [
        activity("requirements"),
        activity("security-review", "requirements"),
        activity("ux-design", "requirements"),
        activity("architecture", "security-review", "ux-design"),
    ]

    ordered = keys(topological_order(given))

    assert ordered[0] == "requirements"
    assert ordered[-1] == "architecture"
    assert set(ordered[1:3]) == {"security-review", "ux-design"}


def test_ordering_is_stable_across_runs():
    given = [
        activity("c", "a"),
        activity("b", "a"),
        activity("a"),
    ]

    assert keys(topological_order(given)) == keys(topological_order(given))


def test_rejects_a_cycle():
    given = [activity("a", "b"), activity("b", "a")]

    with pytest.raises(CircularDependencyError, match="circular"):
        topological_order(given)


def test_rejects_self_dependency():
    with pytest.raises(CircularDependencyError, match="depends on itself"):
        topological_order([activity("a", "a")])


def test_rejects_an_unknown_dependency():
    given = [activity("a", "does-not-exist")]

    with pytest.raises(UnknownDependencyError, match="does-not-exist"):
        topological_order(given)


def test_rejects_a_duplicate_key():
    with pytest.raises(DependencyError, match="Duplicate"):
        topological_order([activity("a"), activity("a")])


def test_rejects_an_activity_without_a_key():
    with pytest.raises(DependencyError, match="no key"):
        topological_order([Activity(name="nameless")])


def test_empty_plan_is_allowed():
    assert topological_order([]) == []
