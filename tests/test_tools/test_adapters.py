"""Unit tests for non-Sarvam adapters: data_gov, open_meteo, free_apis."""

from __future__ import annotations

import pytest

from jantar.tools.adapters.data_gov import DataGovAdapter
from jantar.tools.adapters.open_meteo import OpenMeteoAdapter
from jantar.tools.adapters.free_apis import FreeApisAdapter


class TestDataGovAdapter:
    def test_handles_data_gov_dynamic(self):
        a = DataGovAdapter()
        assert "data_gov_dynamic" in a.handles()

    @pytest.mark.asyncio
    async def test_missing_resource_id_returns_error(self):
        a = DataGovAdapter()
        result = await a.execute("data_gov_dynamic", {})
        assert "error" in result or "status" in result

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self, monkeypatch):
        monkeypatch.setattr("jantar.config.settings.data_gov_api_key", "")
        a = DataGovAdapter()
        result = await a.execute("data_gov_dynamic", {"resource_id": "abc"})
        assert "error" in result


class TestOpenMeteoAdapter:
    def test_handles_weather_tools(self):
        a = OpenMeteoAdapter()
        names = a.handles()
        assert "open_meteo_weather" in names
        assert "open_meteo_air_quality" in names

    def test_city_resolution(self):
        from jantar.tools.adapters.open_meteo import _resolve_city
        coords = _resolve_city("Delhi")
        assert coords is not None
        assert abs(coords[0] - 28.6) < 1  # lat
        assert abs(coords[1] - 77.2) < 1  # lon

    def test_unknown_city_returns_none(self):
        from jantar.tools.adapters.open_meteo import _resolve_city
        assert _resolve_city("xyznonexistent") is None


class TestFreeApisAdapter:
    def test_handles_india_post_and_ifsc(self):
        a = FreeApisAdapter()
        names = a.handles()
        assert "india_post_pincode" in names
        assert "razorpay_ifsc" in names

    @pytest.mark.asyncio
    async def test_india_post_missing_pincode(self):
        a = FreeApisAdapter()
        result = await a.execute("india_post_pincode", {})
        # Should handle gracefully (empty pincode)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ifsc_missing_code(self):
        a = FreeApisAdapter()
        result = await a.execute("razorpay_ifsc", {})
        assert isinstance(result, dict)
