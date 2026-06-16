from pathlib import Path
from datetime import datetime, timezone
import json
import requests
import pandas as pd


GBFS_DISCOVERY_URL = "https://gbfs.mex.lyftbikes.com/gbfs/gbfs.json"

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def get_feed_url(discovery_data: dict, feed_name: str, language: str = "es") -> str:
    """
    Finds the URL for a specific GBFS feed.

    Example:
    feed_name = "station_information"
    language = "es"
    """
    feeds = discovery_data["data"][language]["feeds"]

    for feed in feeds:
        if feed["name"] == feed_name:
            return feed["url"]

    raise ValueError(f"Feed '{feed_name}' was not found for language '{language}'.")


def download_json(url: str) -> dict:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def clean_station_information(station_data: dict) -> pd.DataFrame:
    stations = station_data["data"]["stations"]
    df = pd.DataFrame(stations)

    # Keep station number as text. Important for values like "022" or "390-391".
    df["station_number"] = df["short_name"].astype(str)

    # Clean station name in case it contains line breaks.
    df["station_name"] = (
        df["name"]
        .astype(str)
        .str.replace("\n", " ", regex=False)
        .str.strip()
    )

    # Convert useful numeric fields.
    df["latitude"] = pd.to_numeric(df["lat"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["lon"], errors="coerce")
    df["capacity"] = pd.to_numeric(df["capacity"], errors="coerce")

    # Convert rental_methods list into a simple text field.
    if "rental_methods" in df.columns:
        df["rental_methods"] = df["rental_methods"].apply(
            lambda value: ",".join(value) if isinstance(value, list) else value
        )

    selected_columns = [
        "station_id",
        "external_id",
        "station_number",
        "station_name",
        "latitude",
        "longitude",
        "capacity",
        "rental_methods",
        "has_kiosk",
    ]

    existing_columns = [column for column in selected_columns if column in df.columns]
    df = df[existing_columns]

    return df.sort_values("station_number").reset_index(drop=True)


def main() -> None:
    print("Downloading GBFS discovery file...")
    discovery_data = download_json(GBFS_DISCOVERY_URL)

    station_information_url = get_feed_url(
        discovery_data,
        feed_name="station_information",
        language="es",
    )

    print(f"Station information URL: {station_information_url}")
    print("Downloading station information...")

    station_data = download_json(station_information_url)

    last_updated = station_data.get("last_updated")
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

    raw_output_path = RAW_DIR / f"station_information_raw_{downloaded_at}.json"
    csv_output_path = PROCESSED_DIR / "station_information.csv"

    with open(raw_output_path, "w", encoding="utf-8") as file:
        json.dump(station_data, file, ensure_ascii=False, indent=2)

    df_stations = clean_station_information(station_data)
    df_stations.to_csv(csv_output_path, index=False, encoding="utf-8-sig")

    print("\nStation information downloaded successfully.")
    print(f"Raw JSON saved to: {raw_output_path}")
    print(f"Clean CSV saved to: {csv_output_path}")

    print("\nSummary:")
    print(f"Total stations: {len(df_stations)}")
    print(f"Missing coordinates: {df_stations[['latitude', 'longitude']].isna().any(axis=1).sum()}")
    print(f"Stations with capacity 0: {(df_stations['capacity'] == 0).sum()}")

    if last_updated:
        last_updated_datetime = datetime.fromtimestamp(last_updated, tz=timezone.utc)
        print(f"Feed last updated UTC: {last_updated_datetime}")

    print("\nPreview:")
    print(df_stations.head())


if __name__ == "__main__":
    main()