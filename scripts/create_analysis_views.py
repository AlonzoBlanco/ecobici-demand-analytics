from pathlib import Path
import duckdb


BASE_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = BASE_DIR / "data" / "database" / "ecobici.duckdb"


def main() -> None:
    connection = duckdb.connect(str(DATABASE_PATH))

    connection.execute("""
        CREATE OR REPLACE VIEW trips_analysis AS
        SELECT *
        FROM trips_clean
        WHERE start_datetime IS NOT NULL
          AND end_datetime IS NOT NULL
          AND duration_minutes > 0
          AND duration_minutes <= 180;
    """)

    connection.execute("""
        CREATE OR REPLACE VIEW trips_with_station_info AS
        SELECT
            t.*,

            s_start.station_name AS start_station_name,
            s_start.latitude AS start_latitude,
            s_start.longitude AS start_longitude,
            s_start.capacity AS start_capacity,

            s_end.station_name AS end_station_name,
            s_end.latitude AS end_latitude,
            s_end.longitude AS end_longitude,
            s_end.capacity AS end_capacity

        FROM trips_analysis t
        LEFT JOIN stations s_start
            ON t.start_station_number = s_start.station_number
        LEFT JOIN stations s_end
            ON t.end_station_number = s_end.station_number;
    """)

    summary = connection.execute("""
        SELECT
            COUNT(*) AS clean_trips,
            COUNT(*) FILTER (WHERE start_station_found = FALSE) AS clean_missing_start_station,
            COUNT(*) FILTER (WHERE end_station_found = FALSE) AS clean_missing_end_station,
            MIN(start_datetime) AS min_start_datetime,
            MAX(start_datetime) AS max_start_datetime,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM trips_analysis;
    """).fetchdf()

    print("\nAnalysis views created successfully.")
    print(summary.to_string(index=False))

    connection.close()


if __name__ == "__main__":
    main()