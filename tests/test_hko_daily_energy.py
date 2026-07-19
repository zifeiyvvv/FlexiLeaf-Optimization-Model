from pathlib import Path

from flexileaf.energy.hko_daily import (
    latest_complete_daily_solar,
    parse_hko_daily_solar_csv,
)


def test_hko_daily_parser_and_latest_selection():
    project_root = Path(__file__).resolve().parents[1]
    text = (
        project_root
        / "data"
        / "sample"
        / "hko_daily_solar_example.csv"
    ).read_text(encoding="utf-8")
    frame = parse_hko_daily_solar_csv(text)
    assert len(frame) == 7
    latest = latest_complete_daily_solar(frame)
    assert latest["date"] == "2026-06-24"
    assert latest["global_solar_mj_m2"] == 21.18
