from pathlib import Path

from flexileaf.digital_twin.weather import (
    build_hourly_weather,
    combine_daily_weather,
)


def test_weather_has_8760_rows_and_energy_conservation():
    root = Path(__file__).resolve().parents[1]
    source = root / "data" / "source" / "hko"
    daily = combine_daily_weather(
        solar_path=source / "daily_KP_GSR_2025.csv",
        humidity_path=source / "daily_KP_RH_2025.csv",
        sunshine_path=source / "daily_KP_SUN_2025.csv",
        simulation_year=2025,
    )
    hourly = build_hourly_weather(
        daily,
        latitude=22.312,
        random_seed=20250719,
        annual_mean_temperature_target_c=24.3,
    )
    assert len(daily) == 365
    assert len(hourly) == 8760
    assert (
        hourly.attrs[
            "maximum_daily_solar_energy_error_mj_m2"
        ]
        < 1e-9
    )
    assert abs(hourly["temperature_c"].mean() - 24.3) < 1e-9
