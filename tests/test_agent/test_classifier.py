"""Unit tests for jantar.agent.classifier.parse_classification.

Proves the json-repair-backed parser recovers every common malformed LLM
output and normalizes the result, with a safe hybrid fallback on garbage.
"""

from __future__ import annotations

from jantar.agent.classifier import parse_classification

Q = "what documents for ration card"


def test_clean_json():
    raw = '{"type": "knowledge_query", "tool_query": "", "knowledge_query": "ration card docs", "params": {}}'
    r = parse_classification(raw, Q)
    assert r["type"] == "knowledge_query"
    assert r["knowledge_query"] == "ration card docs"
    assert r["params"] == {}


def test_markdown_fenced_json():
    raw = '```json\n{"type": "tool_action", "params": {"commodity": "Wheat"}}\n```'
    r = parse_classification(raw, Q)
    assert r["type"] == "tool_action"
    assert r["params"] == {"commodity": "Wheat"}


def test_trailing_comma_and_prose():
    raw = 'Sure, here you go: {"type": "hybrid", "params": {"pincode": "110001"},}'
    r = parse_classification(raw, Q)
    assert r["type"] == "hybrid"
    assert r["params"]["pincode"] == "110001"


def test_single_quotes():
    raw = "{'type': 'tool_action', 'params': {'state': 'Delhi'}}"
    r = parse_classification(raw, Q)
    assert r["type"] == "tool_action"
    assert r["params"]["state"] == "Delhi"


def test_truncated_json_is_recovered():
    raw = '{"type": "tool_action", "tool_query": "price", "params": {"state": "Delhi"'
    r = parse_classification(raw, Q)
    assert r["type"] == "tool_action"
    assert r["params"]["state"] == "Delhi"


def test_non_json_falls_back_to_hybrid():
    r = parse_classification("I cannot help with that.", Q)
    assert r["type"] == "hybrid"
    assert r["tool_query"] == Q
    assert r["knowledge_query"] == Q
    assert r["params"] == {}


def test_unknown_type_coerced_to_hybrid():
    raw = '{"type": "banana", "params": {}}'
    r = parse_classification(raw, Q)
    assert r["type"] == "hybrid"


def test_missing_params_defaults_to_empty_dict():
    raw = '{"type": "knowledge_query"}'
    r = parse_classification(raw, Q)
    assert r["params"] == {}


def test_non_dict_params_replaced_with_empty_dict():
    raw = '{"type": "knowledge_query", "params": "oops"}'
    r = parse_classification(raw, Q)
    assert r["params"] == {}


def test_json_array_falls_back_to_hybrid():
    raw = '[{"type": "tool_action"}]'
    r = parse_classification(raw, Q)
    assert r["type"] == "hybrid"


def test_missing_query_fields_default_to_query():
    raw = '{"type": "hybrid", "params": {}}'
    r = parse_classification(raw, Q)
    assert r["tool_query"] == Q
    assert r["knowledge_query"] == Q


def test_domain_field_is_extracted():
    raw = '{"type": "tool_action", "domain": "agriculture", "params": {}}'
    r = parse_classification(raw, Q)
    assert r["domain"] == "agriculture"


def test_missing_domain_defaults_to_none():
    raw = '{"type": "knowledge_query", "params": {}}'
    r = parse_classification(raw, Q)
    assert r["domain"] is None


def test_non_string_domain_becomes_none():
    raw = '{"type": "hybrid", "domain": 123, "params": {}}'
    r = parse_classification(raw, Q)
    assert r["domain"] is None
