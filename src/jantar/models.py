from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Domain(str, Enum):
    """Government service domains — maps to NAPIX/data.gov.in sectors."""
    AGRICULTURE = "agriculture"
    TRANSPORT = "transport"
    HEALTH = "health"
    FINANCE = "finance"
    IDENTITY = "identity"
    EDUCATION = "education"
    LANGUAGE = "language"
    ENVIRONMENT = "environment"
    EMPLOYMENT = "employment"
    FOOD_SECURITY = "food_security"
    HOUSING = "housing"
    DATA = "data"
    TAX = "tax"
    GENERAL = "general"
    ENERGY = "energy"
    WATER = "water"
    CRIME = "crime"
    RURAL_DEVELOPMENT = "rural_development"
    COMMERCE = "commerce"
    TOURISM = "tourism"
    SCIENCE = "science"
    TELECOM = "telecom"
    WEATHER = "weather"
    POSTAL = "postal"
    BANKING = "banking"
    SOCIAL_WELFARE = "social_welfare"
    WOMEN_CHILD = "women_child"
    INDUSTRY = "industry"
    MINERALS = "minerals"
    CENSUS = "census"
    ELECTIONS = "elections"


class AuthMethod(str, Enum):
    API_KEY = "api_key"
    BEARER = "bearer"
    HEADER = "header"
    OPEN = "open"


class ToolDescriptor(BaseModel):
    """A registered API tool that the agent can invoke."""
    id: str = ""
    name: str
    description: str
    domain: Domain
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    auth_method: AuthMethod = AuthMethod.API_KEY
    base_url: str = ""
    endpoint: str = ""
    http_method: str = "GET"
    examples: list[str] = Field(default_factory=list)
    contextual_description: str = ""
    rate_limit: int = 100
    sensitivity: str = "low"


class AgentRequest(BaseModel):
    text: str
    language: str = "auto"
    voice: bool = False


class AgentResponse(BaseModel):
    answer: str
    citations: list[dict[str, str]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    audit_trail: list[dict[str, Any]] = Field(default_factory=list)
    run_id: str = ""
