from flexileaf.site_analysis.location import (
    location_candidates,
    select_location_candidate,
)


def test_location_payload_is_ranked_and_transformed():
    payload = [
        {
            "nameEN": "Example",
            "nameZH": "例子",
            "addressEN": "Example address",
            "addressZH": "示例地址",
            "districtEN": "District",
            "districtZH": "地區",
            "x": 835599.0,
            "y": 817190.0,
        }
    ]
    frame = location_candidates(payload)
    assert len(frame) == 1
    assert frame.iloc[0]["candidate_rank"] == 0
    assert 113.8 < frame.iloc[0]["longitude"] < 114.5
    selected = select_location_candidate(frame, 0)
    assert selected["name_en"] == "Example"
