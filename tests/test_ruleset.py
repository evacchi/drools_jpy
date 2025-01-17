import json
import os
from unittest import mock

import pytest
import yaml

import drools
from drools.rule import Rule
from drools.ruleset import (
    Matches,
    Ruleset,
    RulesetCollection,
    assert_event,
    assert_fact,
    end_session,
    get_facts,
    get_pending_events,
    post,
    retract_fact,
)


def load_ast(filename: str) -> dict:
    test_dir = os.path.dirname(os.path.realpath(__file__))
    with open(f"{test_dir}/{filename}") as f:
        test_data = yaml.safe_load(f)
    return test_data


def test_bad_rulesets():
    with pytest.raises(RuntimeError, match="gobbledygook"):
        Ruleset(name="fred", serialized_ruleset="gobbledygook=xyz")


def test_assert_event():
    test_data = load_ast("asts/rules_with_assignment.yml")

    my_callback = mock.Mock()
    result = Matches(data={"first": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("assignment", my_callback))

    rs.assert_event(json.dumps(dict(i=67)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_assert_multiple_facts():
    test_data = load_ast("asts/multiple_hosts.yml")

    my_callback1 = mock.Mock()
    my_callback2 = mock.Mock()
    result1 = Matches(
        data={"m": {"os": "windows", "host": "B"}, "m_1": {"i": 1}}
    )
    result2 = Matches(
        data={"m": {"os": "linux", "host": "A"}, "m_1": {"i": 4}}
    )

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.assert_fact(json.dumps(dict(host="A", os="linux")))
    rs.assert_fact(json.dumps(dict(host="B", os="windows")))
    rs.assert_fact(json.dumps(dict(host="C", os="macos")))

    rs.add_rule(Rule("Host 1 rule", my_callback1))
    rs.add_rule(Rule("Host 2 rule", my_callback2))

    rs.assert_event(json.dumps(dict(i=1)))
    rs.assert_event(json.dumps(dict(i=4)))
    rs.end_session()
    my_callback1.assert_called_with(result1)
    my_callback2.assert_called_with(result2)


def test_multiple_rulesets():
    test_data = load_ast("asts/multiple_rule_ast.yml")
    fired_callbacks = []
    rulesets = []
    skipped_callbacks = []
    skipped_rule_names = ["should_not_fire"]

    for data in test_data:
        ruleset_data = data["RuleSet"]
        rs = Ruleset(
            name=ruleset_data["name"],
            serialized_ruleset=json.dumps(ruleset_data),
        )
        rulesets.append(rs)
        index = 0
        for rule_data in ruleset_data["rules"]:
            rule_name = rule_data["Rule"]["name"]
            if not rule_name:
                rule_name = f"r_{index}"

            my_callback = mock.Mock()
            rs.add_rule(Rule(rule_name, my_callback))

            if rule_name in skipped_rule_names:
                skipped_callbacks.append(my_callback)
            else:
                fired_callbacks.append(my_callback)

    rulesets[0].assert_event(json.dumps(dict(i=1)))
    rulesets[1].assert_event(json.dumps(dict(do_not_fire_rule=True)))

    rulesets[0].end_session()
    rulesets[1].end_session()

    for cb in fired_callbacks:
        assert cb.called

    for cb in skipped_callbacks:
        assert not cb.called


def test_assert_event_with_undefined():
    test_data = load_ast("asts/assert_event_is_not_defined.yml")

    my_callback1 = mock.Mock()
    my_callback2 = mock.Mock()
    result = Matches(data={"first": {"i": 67, "j": 56}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("fact check", my_callback1))
    rs.add_rule(Rule("not_defined_rule", my_callback2))

    rs.assert_event(json.dumps(dict(i=67, j=56)))
    rs.end_session()
    my_callback1.assert_called_with(result)
    assert not my_callback2.called


@pytest.mark.skip(reason="not supported anymore")
def test_assert_event_with_fact():
    test_data = load_ast("asts/fact_and_event.yml")

    my_callback = mock.Mock()
    result = Matches(data={"m": {"custom": {"index": 67}}, "first": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("fact check", my_callback))

    rs.assert_fact(json.dumps(dict(custom=dict(index=67))))
    rs.assert_event(json.dumps(dict(i=67)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_assert_fact():
    test_data = load_ast("asts/assert_fact.yml")

    my_callback = mock.Mock()
    result = Matches(data={"first": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("fact check", my_callback))

    rs.assert_fact(json.dumps(dict(i=67)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_and_single_result():
    test_data = load_ast("asts/rules_with_and.yml")

    my_callback = mock.Mock()
    result = Matches(data={"m": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )

    for rule_data in ruleset_data["rules"]:
        rule_name = rule_data["Rule"]["name"]
        my_callback = mock.Mock()
        rs.add_rule(Rule(rule_name, my_callback))

    rs.assert_event(json.dumps(dict(i=1)))
    rs.assert_event(json.dumps(dict(i=2)))
    rs.assert_event(json.dumps(dict(i=3)))
    rs.assert_event(json.dumps(dict(i=67)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_retract_fact():
    test_data = load_ast("asts/retract_fact.yml")

    my_callback = mock.Mock()
    result = Matches(data={"m": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("r_0", my_callback))

    rs.assert_fact(json.dumps(dict(i=67)))
    rs.assert_fact(json.dumps(dict(j=42)))
    assert not my_callback.called

    rs.retract_fact(json.dumps(dict(i=67)))

    my_callback.assert_called_with(result)
    response = rs.get_facts()[0]
    rs.end_session()
    assert "j" in response.keys()


def test_get_facts():
    test_data = load_ast("asts/assert_fact.yml")

    my_callback = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("fact check", my_callback))

    rs.assert_fact(json.dumps(dict(friend="Barney")))
    rs.assert_fact(json.dumps(dict(age=42)))

    response = rs.get_facts()
    rs.end_session()
    assert len(response) == 2


def test_assert_event_no_matching_rules():
    test_data = load_ast("asts/rules_with_assignment.yml")
    my_callback = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("assignment", my_callback))

    rs.assert_event(json.dumps(dict(i=7)))
    rs.end_session()
    assert (
        not my_callback.called
    ), "my_callback was called and should not have been"


def test_assert_event_without_assignment():
    test_data = load_ast("asts/rules_without_assignment.yml")
    my_callback = mock.Mock()
    result = Matches(data={"m": {"i": 57}})
    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("assignment", my_callback))

    rs.assert_event(json.dumps(dict(i=57)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_assert_event_multiple_conditions_any():
    test_data = load_ast(
        "asts/rules_with_multiple_conditions_any_assignment.yml"
    )
    my_callback = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]

    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("any condition", my_callback))

    result = Matches(data={"event": {"i": 1}})
    rs.assert_event(json.dumps(dict(i=9)))
    rs.assert_event(json.dumps(dict(i=1)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_assert_event_multiple_conditions_any_no_assignment():
    test_data = load_ast(
        "asts/rules_with_multiple_conditions_any_no_assignment.yml"
    )
    my_callback = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]

    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("any condition", my_callback))

    result = Matches(data={"m_1": {"i": 1}})
    rs.assert_event(json.dumps(dict(i=9)))
    rs.assert_event(json.dumps(dict(i=1)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_assert_event_multiple_conditions_all():
    test_data = load_ast(
        "asts/rules_with_multiple_conditions_all_assignment.yml"
    )
    my_callback = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]

    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("multiple conditions", my_callback))

    result = Matches(data={"first": {"i": 0}, "second": {"i": 1}})
    rs.assert_event(json.dumps(dict(i=8)))
    rs.assert_event(json.dumps(dict(i=1)))
    rs.assert_event(json.dumps(dict(i=0)))
    rs.end_session()
    my_callback.assert_called_with(result)


def test_assert_event_multiple_conditions_all_no_assignment():
    test_data = load_ast(
        "asts/rules_with_multiple_conditions_all_no_assignment.yml"
    )
    my_callback = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]

    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("multiple conditions", my_callback))

    result = Matches(data={"m": {"i": 0}, "m_1": {"i": 1}})
    rs.assert_event(json.dumps(dict(i=9)))
    rs.assert_event(json.dumps(dict(i=1)))
    rs.assert_event(json.dumps(dict(i=0)))
    rs.end_session()

    my_callback.assert_called_with(result)


def test_assert_event_multiple_rules():
    test_data = load_ast("asts/ruleset_with_multiple_rules.yml")
    my_callback1 = mock.Mock()
    my_callback2 = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]

    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("r_0", my_callback1))
    rs.add_rule(Rule("r_1", my_callback2))

    result1 = Matches(data={"m": {"i": 42}})

    rs.assert_event(json.dumps(dict(i=9)))
    rs.assert_event(json.dumps(dict(i=42)))
    rs.end_session()

    my_callback1.assert_called_with(result1)
    assert not my_callback2.called


def test_assert_fact_multiple_rules():
    test_data = load_ast("asts/ruleset_with_multiple_rules.yml")
    my_callback1 = mock.Mock()
    my_callback2 = mock.Mock()
    ruleset_data = test_data[0]["RuleSet"]

    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("r_0", my_callback1))
    rs.add_rule(Rule("r_1", my_callback2))

    result1 = Matches(data={"m": {"i": 42}})

    rs.assert_fact(json.dumps(dict(i=42)))
    rs.end_session()

    my_callback1.assert_called_with(result1)
    my_callback2.assert_called_with(result1)


def test_ruleset_collection():
    test_data = load_ast("asts/rules_with_assignment.yml")
    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    assert RulesetCollection.get(ruleset_data["name"]) == rs


def test_end_session_via_collection():
    test_data = load_ast("asts/rules_with_assignment.yml")
    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    assert RulesetCollection.get(ruleset_data["name"]) == rs
    end_session(ruleset_data["name"])


def test_ruleset_collection_missing_object():
    with pytest.raises(drools.exceptions.RulesetNotFoundError):
        RulesetCollection.get("non_existent_object")


def test_assert_event_via_collection():
    test_data = load_ast("asts/rules_with_assignment.yml")

    my_callback = mock.Mock()
    result = Matches(data={"first": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("assignment", my_callback))

    assert_event(ruleset_data["name"], json.dumps(dict(i=67)))
    my_callback.assert_called_with(result)


def test_post_via_collection():
    test_data = load_ast("asts/rules_with_assignment.yml")

    my_callback = mock.Mock()
    result = Matches(data={"first": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("assignment", my_callback))

    post(ruleset_data["name"], json.dumps(dict(i=67)))
    my_callback.assert_called_with(result)


def test_retract_fact_via_collection():
    test_data = load_ast("asts/assert_fact.yml")

    my_callback = mock.Mock()
    result = Matches(data={"first": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("fact check", my_callback))

    assert_fact(ruleset_data["name"], json.dumps(dict(i=67)))
    assert_fact(ruleset_data["name"], json.dumps(dict(j=42)))

    my_callback.assert_called_with(result)

    retract_fact(ruleset_data["name"], json.dumps(dict(i=67)))
    response = get_facts(ruleset_data["name"])[0]
    assert "i" not in response.keys()
    assert "j" in response.keys()


def test_get_pending_events_via_collection():
    test_data = load_ast("asts/rules_with_assignment.yml")

    my_callback = mock.Mock()
    result = Matches(data={"first": {"i": 67}})

    ruleset_data = test_data[0]["RuleSet"]
    rs = Ruleset(
        name=ruleset_data["name"], serialized_ruleset=json.dumps(ruleset_data)
    )
    rs.add_rule(Rule("assignment", my_callback))

    assert_event(ruleset_data["name"], json.dumps(dict(i=67)))
    assert get_pending_events(ruleset_data["name"]) is None
    my_callback.assert_called_with(result)
