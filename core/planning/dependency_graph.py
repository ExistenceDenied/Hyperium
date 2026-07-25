from __future__ import annotations

from collections import deque

from core.execution.activity import Activity


class DependencyError(ValueError):
    """
    Raised when the dependencies between activities cannot be satisfied.
    """


class CircularDependencyError(DependencyError):
    """
    Raised when activities form a cycle and no execution order exists.
    """


class UnknownDependencyError(DependencyError):
    """
    Raised when an activity depends on a key that no activity provides.
    """


def topological_order(activities: list[Activity]) -> list[Activity]:
    """
    Order activities so that every activity follows the ones it depends on.

    Ties are broken by the original ordering, which keeps a plan's output
    stable across runs. Raises rather than guessing: an unsatisfiable graph is
    a planning failure, not something to execute in arbitrary order.
    """
    by_key = _index(activities)
    _reject_unknown_dependencies(activities, by_key)

    outstanding = {
        activity.key: set(activity.depends_on) for activity in activities
    }

    dependents: dict[str, list[str]] = {activity.key: [] for activity in activities}

    for activity in activities:
        for dependency in activity.depends_on:
            dependents[dependency].append(activity.key)

    ready = deque(
        activity.key for activity in activities if not outstanding[activity.key]
    )

    ordered: list[Activity] = []

    while ready:
        key = ready.popleft()
        ordered.append(by_key[key])

        for dependent in dependents[key]:
            outstanding[dependent].discard(key)

            if not outstanding[dependent]:
                ready.append(dependent)

    if len(ordered) != len(activities):
        cycle = sorted(key for key, pending in outstanding.items() if pending)

        raise CircularDependencyError(
            "Activities form a circular dependency: " + ", ".join(cycle) + "."
        )

    return ordered


def _index(activities: list[Activity]) -> dict[str, Activity]:
    by_key: dict[str, Activity] = {}

    for activity in activities:
        if not activity.key:
            raise DependencyError(
                f"Activity '{activity.name}' has no key and cannot be ordered."
            )

        if activity.key in by_key:
            raise DependencyError(
                f"Duplicate activity key '{activity.key}'."
            )

        by_key[activity.key] = activity

    return by_key


def _reject_unknown_dependencies(
    activities: list[Activity],
    by_key: dict[str, Activity],
) -> None:
    for activity in activities:
        if activity.key in activity.depends_on:
            raise CircularDependencyError(
                f"Activity '{activity.key}' depends on itself."
            )

        for dependency in sorted(activity.depends_on):
            if dependency not in by_key:
                raise UnknownDependencyError(
                    f"Activity '{activity.key}' depends on unknown "
                    f"activity '{dependency}'."
                )
