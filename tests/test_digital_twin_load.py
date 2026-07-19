import json
from pathlib import Path

from flexileaf.digital_twin.load_model import build_annual_load
from flexileaf.digital_twin.weather import (
    build_hourly_weather,
    combine_daily_weather,
)


def test_load_matches_annual_targets():
    root = Path(__file__).resolve().parents[1]
    config = json.loads(
        (
            root
            / "configs"
            / "design_basis_case_2025.json"
        ).read_text(encoding="utf-8")
    )
    source = root / "data" / "source" / "hko"
    daily = combine_daily_weather(
        solar_path=source / "daily_KP_GSR_2025.csv",
        humidity_path=source / "daily_KP_RH_2025.csv",
        sunshine_path=source / "daily_KP_SUN_2025.csv",
        simulation_year=2025,
    )
    weather = build_hourly_weather(
        daily,
        latitude=config["latitude"],
        random_seed=config["random_seed"],
        annual_mean_temperature_target_c=24.3,
    )
    load, calibration = build_annual_load(
        weather,
        assets=config["assets"],
        annual_ev_charging_energy_kwh=config[
            "public_infrastructure"
        ]["annual_ev_charging_energy_kwh"],
    )
    target = calibration["annual_target_energy_kwh"].sum()
    actual = load["total_load_kw"].sum()
    assert abs(actual - target) / target < 1e-10
