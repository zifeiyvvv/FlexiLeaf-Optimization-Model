import math

from flexileaf.site_analysis.geo import (
    hk1980_to_wgs84,
    make_wgs84_bbox_from_hk1980,
)


def test_hk1980_conversion_is_in_hong_kong():
    longitude, latitude = hk1980_to_wgs84(835599.0, 817190.0)
    assert 113.8 < longitude < 114.5
    assert 22.1 < latitude < 22.6


def test_bbox_has_correct_order():
    bbox = make_wgs84_bbox_from_hk1980(
        centre_x=835599.0,
        centre_y=817190.0,
        radius_m=250,
    )
    assert bbox["south_lat"] < bbox["north_lat"]
    assert bbox["west_lon"] < bbox["east_lon"]
