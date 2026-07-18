import pytest

from flexileaf.site_analysis.pv_model import (
    estimate_building_pv,
    estimate_surface_pv_power,
)


def test_zero_irradiance_produces_zero_power():
    result = estimate_surface_pv_power(
        usable_area_m2=100,
        irradiance_wm2=0,
        module_efficiency=0.20,
        performance_ratio=0.82,
        orientation_factor=0.90,
    )
    assert result["estimated_current_power_kw"] == 0


def test_positive_irradiance_produces_bounded_power():
    result = estimate_surface_pv_power(
        usable_area_m2=100,
        irradiance_wm2=800,
        module_efficiency=0.20,
        performance_ratio=0.82,
        orientation_factor=0.90,
    )
    assert 0 < result["estimated_current_power_kw"]
    assert result["estimated_current_power_kw"] <= result["dc_capacity_kwp"]


def test_invalid_fraction_is_rejected():
    with pytest.raises(ValueError):
        estimate_surface_pv_power(
            usable_area_m2=100,
            irradiance_wm2=800,
            module_efficiency=1.2,
            performance_ratio=0.82,
            orientation_factor=0.90,
        )
