import json
from pathlib import Path

from flexileaf.digital_twin.pv_model import build_annual_pv
from flexileaf.digital_twin.weather import (
    build_hourly_weather,
    combine_daily_weather,
)


def test_pv_is_nonnegative_and_design_exceeds_conservative():
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
    conservative, _ = build_annual_pv(
        weather,
        assets=config["assets"],
        public_infrastructure=config["public_infrastructure"],
        scenario_name="conservative",
        scenario=config["performance_scenarios"]["conservative"],
    )
    design, _ = build_annual_pv(
        weather,
        assets=config["assets"],
        public_infrastructure=config["public_infrastructure"],
        scenario_name="design",
        scenario=config["performance_scenarios"]["design"],
    )
    assert (design["total_pv_kw"] >= 0).all()
    assert design["total_pv_kw"].sum() > conservative[
        "total_pv_kw"
    ].sum()
