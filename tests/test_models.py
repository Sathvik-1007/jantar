"""Unit tests for jantar.models — canonical types (single source of truth)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jantar.models import AgentRequest, AgentResponse, AuthMethod, Domain, ToolDescriptor


def test_domain_enum_has_all_expected_domains():
    expected = {
        "agriculture", "transport", "health", "finance", "identity", "education",
        "language", "environment", "employment", "food_security", "housing",
        "data", "tax", "general", "energy", "water", "crime", "rural_development",
        "commerce", "tourism", "science", "telecom", "weather", "postal",
        "banking", "social_welfare", "women_child", "industry", "minerals",
        "census", "elections",
    }
    assert {d.value for d in Domain} == expected


def test_auth_method_values():
    assert {a.value for a in AuthMethod} == {"api_key", "bearer", "header", "open"}


def test_tool_descriptor_requires_name():
    with pytest.raises(ValidationError):
        ToolDescriptor(description="x", domain=Domain.HEALTH)  # name missing


def test_tool_descriptor_defaults():
    t = ToolDescriptor(name="t", description="d", domain=Domain.TRANSPORT)
    assert t.id == ""
    assert t.auth_method == AuthMethod.API_KEY
    assert t.http_method == "GET"
    assert t.examples == []
    assert t.rate_limit == 100
    assert t.sensitivity == "low"


def test_tool_descriptor_coerces_domain_string():
    t = ToolDescriptor(name="t", description="d", domain="finance")
    assert t.domain is Domain.FINANCE


def test_tool_descriptor_rejects_unknown_domain():
    with pytest.raises(ValidationError):
        ToolDescriptor(name="t", description="d", domain="not_a_domain")


def test_agent_request_defaults():
    r = AgentRequest(text="hi")
    assert r.language == "auto"
    assert r.voice is False


def test_agent_response_defaults():
    r = AgentResponse(answer="ok")
    assert r.citations == []
    assert r.tools_used == []
    assert r.plan == []
    assert r.audit_trail == []
    assert r.run_id == ""
