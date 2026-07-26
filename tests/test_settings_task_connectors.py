from __future__ import annotations

from config.settings import Settings


def test_task_connectors_defaults_off(monkeypatch):
    monkeypatch.delenv("HYPERIUM_TASK_CONNECTORS", raising=False)
    assert Settings.load().task_connectors is False


def test_task_connectors_can_be_enabled(monkeypatch):
    monkeypatch.setenv("HYPERIUM_TASK_CONNECTORS", "1")
    assert Settings.load().task_connectors is True
    monkeypatch.setenv("HYPERIUM_TASK_CONNECTORS", "true")
    assert Settings.load().task_connectors is True
    monkeypatch.setenv("HYPERIUM_TASK_CONNECTORS", "0")
    assert Settings.load().task_connectors is False
