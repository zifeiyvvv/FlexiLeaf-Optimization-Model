import numpy as np

from flexileaf.energy.profiles import (
    generate_load_profile,
    generate_solar_irradiance_profile,
    generate_tariff_profile,
)


def test_load_profile_reaches_requested_peak():
    profile = generate_load_profile(
        archetype="education",
        peak_load_kw=400,
    )
    assert len(profile) == 24
    assert profile.max() == 400
    assert np.all(profile > 0)


def test_solar_profile_integrates_to_daily_total():
    profile = generate_solar_irradiance_profile(
        daily_solar_mj_m2=18.0,
    )
    integrated_kwh_m2 = profile.sum() / 1000.0
    assert abs(integrated_kwh_m2 - 18.0 / 3.6) < 1e-9
    assert profile.min() == 0


def test_tariff_has_three_period_values():
    tariff = generate_tariff_profile(
        off_peak_hkd_per_kwh=1.0,
        shoulder_hkd_per_kwh=1.3,
        peak_hkd_per_kwh=1.8,
    )
    assert set(np.unique(tariff)) == {1.0, 1.3, 1.8}
