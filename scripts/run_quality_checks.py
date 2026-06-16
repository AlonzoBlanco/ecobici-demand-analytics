from pathlib import Path
import duckdb
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

BASE_DIR = Path(__file__).resolve().parents[1]

DATABASE_PATH = BASE_DIR / "data" / "database" / "ecobici.duckdb"
VALIDATION_DIR = BASE_DIR / "data" / "validation"

VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    connection = duckdb.connect(str(DATABASE_PATH))

    quality_summary = connection.execute(
        """
        SELECT
            COUNT(*) AS total_trips,

            COUNT(*) FILTER (
                WHERE start_datetime IS NULL
            ) AS invalid_start_datetime,

            COUNT(*) FILTER (
                WHERE end_datetime IS NULL
            ) AS invalid_end_datetime,

            COUNT(*) FILTER (
                WHERE start_datetime IS NOT NULL
                  AND end_datetime IS NOT NULL
            ) AS valid_datetime_trips,

            COUNT(*) FILTER (
                WHERE duration_minutes < 0
            ) AS negative_duration_trips,

            COUNT(*) FILTER (
                WHERE duration_minutes = 0
            ) AS zero_duration_trips,

            COUNT(*) FILTER (
                WHERE duration_minutes > 180
            ) AS trips_over_3_hours,

            COUNT(*) FILTER (
                WHERE duration_minutes > 1440
            ) AS trips_over_24_hours,

            COUNT(*) FILTER (
                WHERE start_station_found = FALSE
            ) AS missing_start_station_trips,

            COUNT(*) FILTER (
                WHERE end_station_found = FALSE
            ) AS missing_end_station_trips
        FROM trips_clean;
        """
    ).fetchdf()

    print("\nQuality summary:")
    print(quality_summary.to_string(index=False))

    quality_by_file = connection.execute(
        """
        SELECT
            source_file,
            COUNT(*) AS total_trips,

            COUNT(*) FILTER (
                WHERE start_datetime IS NULL
            ) AS invalid_start_datetime,

            COUNT(*) FILTER (
                WHERE end_datetime IS NULL
            ) AS invalid_end_datetime,

            COUNT(*) FILTER (
                WHERE duration_minutes < 0
            ) AS negative_duration_trips,

            COUNT(*) FILTER (
                WHERE duration_minutes > 180
            ) AS trips_over_3_hours,

            COUNT(*) FILTER (
                WHERE start_station_found = FALSE
            ) AS missing_start_station_trips,

            COUNT(*) FILTER (
                WHERE end_station_found = FALSE
            ) AS missing_end_station_trips
        FROM trips_clean
        GROUP BY source_file
        ORDER BY source_file;
        """
    ).fetchdf()

    output_path = VALIDATION_DIR / "quality_by_file.csv"
    quality_by_file.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"\nQuality by file saved to: {output_path}")

    print("\nTop files with invalid start datetime:")
    print(
        quality_by_file
        .sort_values("invalid_start_datetime", ascending=False)
        .head(10)
        .to_string(index=False)
    )

    connection.close()


if __name__ == "__main__":
    main()