import pandas as pd

from flexileaf.site_analysis.solar import (
    choose_nearest_solar_station,
    select_solar_observation,
)


def test_nearest_station_has_distance():
    station = choose_nearest_solar_station(
        longitude=114.17,
        latitude=22.32,
    )
    assert station["station_code"] in {"KP", "KSC"}
    assert station["distance_to_site_m"] >= 0


def test_station_observation_selection():
    frame = pd.DataFrame(
        [
            {
                "station": "King's Park",
                "global_solar_wm2": 500,
            },
            {
                "station": "Kau Sai Chau",
                "global_solar_wm2": 550,
            },
        ]
    )
    row = select_solar_observation(frame, "KP")
    assert row["global_solar_wm2"] == 500
