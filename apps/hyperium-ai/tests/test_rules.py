from __future__ import annotations

from core.rules.rule import Condition, Decision, Rule, RuleSet
from infrastructure.rules_store import RuleStore


def test_startswith_is_case_insensitive_and_supports_alternatives():
    cond = Condition("sender", "startsWith", "kris.leunis, krisleunis")
    assert cond.test({"sender": "Kris.Leunis@hyperium.be"}) is True
    assert cond.test({"sender": "krisleunis1@gmail.com"}) is True
    assert cond.test({"sender": "someone@else.com"}) is False


def test_operators():
    assert Condition("c", "equals", "reply").test({"c": "reply"}) is True
    assert Condition("c", "in", "a, b, c").test({"c": "b"}) is True
    assert Condition("c", "contains", "quote").test({"c": "Your quote"}) is True
    assert Condition("n", "gte", "0.8").test({"n": "0.9"}) is True
    assert Condition("n", "gte", "0.8").test({"n": "0.5"}) is False
    assert Condition("s", "matches", r"^inv-\d+").test({"s": "INV-42"}) is True
    assert Condition("x", "any").test({}) is True


def test_all_conditions_must_hold():
    rule = Rule(
        name="r",
        conditions=[
            Condition("category", "equals", "reply"),
            Condition("sender", "startsWith", "kris"),
        ],
        outputs={"delivery": "send"},
    )
    assert rule.matches({"category": "reply", "sender": "kris@x"}) is True
    assert rule.matches({"category": "reply", "sender": "other@x"}) is False


def test_first_write_wins_per_output_and_records_fired_rules():
    rules = RuleSet(
        [
            Rule(
                name="trusted-send",
                conditions=[Condition("sender", "startsWith", "kris")],
                outputs={"delivery": "send"},
            ),
            Rule(name="always-attach", outputs={"attach_deliverables": "true"}),
            Rule(name="default-draft", outputs={"delivery": "draft"}),
        ]
    )

    decision = rules.decide({"sender": "kris@x", "category": "reply"})

    assert decision.get("delivery") == "send"  # specific rule wins over default
    assert decision.is_true("attach_deliverables") is True
    assert decision.fired == ["trusted-send", "always-attach", "default-draft"]


def test_default_rule_applies_when_specific_one_misses():
    rules = RuleSet(
        [
            Rule(
                name="trusted-send",
                conditions=[Condition("sender", "startsWith", "kris")],
                outputs={"delivery": "send"},
            ),
            Rule(name="default-draft", outputs={"delivery": "draft"}),
        ]
    )

    assert rules.decide({"sender": "stranger@x"}).get("delivery") == "draft"


def test_disabled_rule_never_fires():
    rule = Rule(name="off", outputs={"delivery": "send"}, enabled=False)
    assert RuleSet([rule]).decide({}).outputs == {}


def test_decision_truthiness():
    assert Decision({"x": "true"}).is_true("x") is True
    assert Decision({"x": "false"}).is_true("x") is False
    assert Decision({}).is_true("missing") is False


def test_store_round_trips_rules_and_the_kill_switch(tmp_path):
    store = RuleStore(tmp_path / "rules.json")
    rule = store.add(
        "trusted sender",
        [Condition("sender", "startsWith", "kris.leunis, krisleunis")],
        {"delivery": "send"},
    )

    reloaded = RuleStore(tmp_path / "rules.json")
    rules = reloaded.list()
    assert rules[0].name == "trusted sender"
    assert rules[0].conditions[0].op == "startsWith"
    assert rules[0].outputs == {"delivery": "send"}

    assert reloaded.sending_enabled is False
    reloaded.set_sending_enabled(True)
    assert RuleStore(tmp_path / "rules.json").sending_enabled is True

    reloaded.delete(rule.id)
    assert RuleStore(tmp_path / "rules.json").list() == []


def test_rule_set_from_store_evaluates(tmp_path):
    store = RuleStore(tmp_path / "rules.json")
    store.add(
        "trusted",
        [Condition("sender", "startsWith", "kris.leunis")],
        {"delivery": "send"},
    )

    decision = store.rule_set().decide({"sender": "kris.leunis@hyperium.be"})
    assert decision.get("delivery") == "send"
