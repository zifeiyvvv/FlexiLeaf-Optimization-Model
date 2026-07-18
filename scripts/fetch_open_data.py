#!/usr/bin/env python3
"""Download and standardise official Hong Kong open data for FlexiLeaf."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flexileaf.open_data.csdi import CSDIBuildingClient
from flexileaf.open_data.hko import HKOClient
from flexileaf.open_data.http_client import GovernmentHTTPClient, OpenDataError
from flexileaf.open_data.landsd import LandsDClient
from flexileaf.open_data.storage import OpenDataStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch official Hong Kong open data for FlexiLeaf."
    )
    parser.add_argument(
        "--data-root",
        default=str(PROJECT_ROOT / "data"),
        help="Directory containing raw/ and processed/ data.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    weather = subparsers.add_parser(
        "weather-current",
        help="Fetch the HKO current weather report.",
    )
    weather.add_argument("--lang", choices=["en", "tc", "sc"], default="en")

    forecast = subparsers.add_parser(
        "weather-forecast",
        help="Fetch the HKO 9-day weather forecast.",
    )
    forecast.add_argument("--lang", choices=["en", "tc", "sc"], default="en")

    subparsers.add_parser(
        "solar-live",
        help="Fetch the latest HKO one-minute solar-radiation readings.",
    )

    solar_history = subparsers.add_parser(
        "solar-history",
        help="Fetch HKO daily global solar-radiation history.",
    )
    solar_history.add_argument(
        "--station",
        choices=["KP", "KSC"],
        default="KP",
        help="KP = King's Park; KSC = Kau Sai Chau.",
    )
    solar_history.add_argument(
        "--year",
        default="ALL",
        help="Four-digit year or ALL.",
    )

    location = subparsers.add_parser(
        "location-search",
        help="Search an address, building, place or facility.",
    )
    location.add_argument("--query", required=True)

    buildings = subparsers.add_parser(
        "buildings",
        help="Fetch CSDI building footprints inside a bounding box.",
    )
    buildings.add_argument("--south-lat", type=float, required=True)
    buildings.add_argument("--west-lon", type=float, required=True)
    buildings.add_argument("--north-lat", type=float, required=True)
    buildings.add_argument("--east-lon", type=float, required=True)
    buildings.add_argument("--count", type=int, default=100)
    buildings.add_argument("--start-index", type=int, default=0)

    return parser


def save_current_weather(
    client: HKOClient,
    store: OpenDataStore,
    lang: str,
) -> None:
    resource = client.fetch_current_weather(lang=lang)
    raw_path = store.save_raw(
        provider="hko",
        dataset="current_weather",
        extension="json",
        resource=resource,
        request_parameters={"dataType": "rhrread", "lang": lang},
    )
    payload = resource.json()
    tables = client.parse_current_weather(payload)
    for table_name, frame in tables.items():
        output = store.processed_path(
            provider="hko",
            dataset="current_weather",
            filename=f"{table_name}.csv",
        )
        frame.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"Processed: {output}")
    print(f"Raw: {raw_path}")


def save_forecast(
    client: HKOClient,
    store: OpenDataStore,
    lang: str,
) -> None:
    resource = client.fetch_nine_day_forecast(lang=lang)
    raw_path = store.save_raw(
        provider="hko",
        dataset="nine_day_forecast",
        extension="json",
        resource=resource,
        request_parameters={"dataType": "fnd", "lang": lang},
    )
    frame = client.parse_nine_day_forecast(resource.json())
    output = store.processed_path(
        provider="hko",
        dataset="nine_day_forecast",
        filename="forecast.csv",
    )
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Raw: {raw_path}")
    print(f"Processed: {output}")


def save_live_solar(client: HKOClient, store: OpenDataStore) -> None:
    resource = client.fetch_latest_solar_radiation()
    raw_path = store.save_raw(
        provider="hko",
        dataset="latest_solar_radiation",
        extension="csv",
        resource=resource,
    )
    frame = client.parse_latest_solar_radiation(resource.text())
    output = store.processed_path(
        provider="hko",
        dataset="latest_solar_radiation",
        filename="latest_solar_radiation.csv",
    )
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Raw: {raw_path}")
    print(f"Processed: {output}")
    print(frame.to_string(index=False))


def save_solar_history(
    client: HKOClient,
    store: OpenDataStore,
    station: str,
    year: str,
) -> None:
    resource = client.fetch_daily_solar_radiation(
        station=station,
        year=year,
    )
    dataset = f"daily_solar_{station}_{year}"
    raw_path = store.save_raw(
        provider="hko",
        dataset=dataset,
        extension="csv",
        resource=resource,
        request_parameters={"station": station, "year": year},
    )
    frame = client.parse_daily_solar_radiation(resource.text())
    output = store.processed_path(
        provider="hko",
        dataset=dataset,
        filename="daily_solar_radiation.csv",
    )
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Raw: {raw_path}")
    print(f"Processed: {output}")
    print(f"Rows: {len(frame)}")


def save_location(
    client: LandsDClient,
    store: OpenDataStore,
    query: str,
) -> None:
    resource = client.search_location(query)
    raw_path = store.save_raw(
        provider="landsd",
        dataset="location_search",
        extension="json",
        resource=resource,
        request_parameters={"q": query},
    )
    payload = resource.json()
    frame = client.parse_location_results(payload)
    output = store.processed_path(
        provider="landsd",
        dataset="location_search",
        filename="location_search.csv",
    )
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Raw: {raw_path}")
    print(f"Processed: {output}")
    print(frame.head(10).to_string(index=False))


def save_buildings(
    client: CSDIBuildingClient,
    store: OpenDataStore,
    args: argparse.Namespace,
) -> None:
    parameters = {
        "south_lat": args.south_lat,
        "west_lon": args.west_lon,
        "north_lat": args.north_lat,
        "east_lon": args.east_lon,
        "count": args.count,
        "start_index": args.start_index,
    }
    resource = client.fetch_buildings_by_bbox(**parameters)
    raw_path = store.save_raw(
        provider="csdi",
        dataset="building_footprints",
        extension="geojson",
        resource=resource,
        request_parameters=parameters,
    )
    payload = resource.json()

    latest_geojson = store.processed_path(
        provider="csdi",
        dataset="building_footprints",
        filename="buildings.geojson",
    )
    latest_geojson.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = client.parse_building_summary(payload)
    summary_path = store.processed_path(
        provider="csdi",
        dataset="building_footprints",
        filename="buildings_summary.csv",
    )
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print(f"Raw: {raw_path}")
    print(f"Processed GeoJSON: {latest_geojson}")
    print(f"Processed summary: {summary_path}")
    print(f"Features: {len(payload.get('features', []))}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    http = GovernmentHTTPClient(
        timeout_seconds=args.timeout,
        user_agent="FlexiLeaf-Student-Project/0.1",
    )
    store = OpenDataStore(args.data_root)

    try:
        if args.command == "weather-current":
            save_current_weather(HKOClient(http), store, args.lang)
        elif args.command == "weather-forecast":
            save_forecast(HKOClient(http), store, args.lang)
        elif args.command == "solar-live":
            save_live_solar(HKOClient(http), store)
        elif args.command == "solar-history":
            save_solar_history(
                HKOClient(http),
                store,
                args.station,
                args.year,
            )
        elif args.command == "location-search":
            save_location(LandsDClient(http), store, args.query)
        elif args.command == "buildings":
            save_buildings(CSDIBuildingClient(http), store, args)
        else:
            parser.error(f"Unknown command: {args.command}")
    except (OpenDataError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
