from pathlib import Path
import duckdb


SCRIPT_PATH = Path(__file__).resolve()


def find_project_dir() -> Path:
    candidates = [
        SCRIPT_PATH.parent,
        SCRIPT_PATH.parents[1],
        Path.cwd(),
    ]

    for candidate in candidates:
        if (candidate / "data" / "database" / "ecobici.duckdb").exists():
            return candidate

    return SCRIPT_PATH.parents[1]


BASE_DIR = find_project_dir()
DATABASE_PATH = BASE_DIR / "data" / "database" / "ecobici.duckdb"
OUTPUT_DIR = BASE_DIR / "data" / "exports"


QUERIES = {
    "monthly_trips.csv": """
        SELECT
            year,
            month,
            COUNT(*) AS total_trips,
            AVG(duration_minutes) AS avg_duration_minutes,
            MEDIAN(duration_minutes) AS median_duration_minutes
        FROM trips_analysis
        GROUP BY year, month
        ORDER BY year, month;
    """,
    "weekday_trips.csv": """
        SELECT
            weekday,
            CASE weekday
                WHEN 0 THEN 'Monday'
                WHEN 1 THEN 'Tuesday'
                WHEN 2 THEN 'Wednesday'
                WHEN 3 THEN 'Thursday'
                WHEN 4 THEN 'Friday'
                WHEN 5 THEN 'Saturday'
                WHEN 6 THEN 'Sunday'
            END AS weekday_name,
            COUNT(*) AS total_trips,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM trips_analysis
        GROUP BY weekday
        ORDER BY weekday;
    """,
    "hourly_trips.csv": """
        SELECT
            hour,
            COUNT(*) AS total_trips,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM trips_analysis
        GROUP BY hour
        ORDER BY hour;
    """,
    "hourly_weekday_trips.csv": """
        SELECT
            weekday,
            CASE weekday
                WHEN 0 THEN 'Monday'
                WHEN 1 THEN 'Tuesday'
                WHEN 2 THEN 'Wednesday'
                WHEN 3 THEN 'Thursday'
                WHEN 4 THEN 'Friday'
                WHEN 5 THEN 'Saturday'
                WHEN 6 THEN 'Sunday'
            END AS weekday_name,
            hour,
            COUNT(*) AS total_trips
        FROM trips_analysis
        GROUP BY weekday, hour
        ORDER BY weekday, hour;
    """,
    "top_start_stations.csv": """
        SELECT
            start_station_number,
            start_station_name,
            start_latitude,
            start_longitude,
            start_capacity,
            COUNT(*) AS total_departures,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM trips_with_station_info
        WHERE start_station_found = TRUE
        GROUP BY
            start_station_number,
            start_station_name,
            start_latitude,
            start_longitude,
            start_capacity
        ORDER BY total_departures DESC;
    """,
    "top_end_stations.csv": """
        SELECT
            end_station_number,
            end_station_name,
            end_latitude,
            end_longitude,
            end_capacity,
            COUNT(*) AS total_arrivals,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM trips_with_station_info
        WHERE end_station_found = TRUE
        GROUP BY
            end_station_number,
            end_station_name,
            end_latitude,
            end_longitude,
            end_capacity
        ORDER BY total_arrivals DESC;
    """,
    "station_flow_balance.csv": """
        WITH departures AS (
            SELECT
                start_station_number AS station_number,
                start_station_name AS station_name,
                start_latitude AS latitude,
                start_longitude AS longitude,
                COUNT(*) AS total_departures
            FROM trips_with_station_info
            WHERE start_station_found = TRUE
            GROUP BY
                start_station_number,
                start_station_name,
                start_latitude,
                start_longitude
        ),
        arrivals AS (
            SELECT
                end_station_number AS station_number,
                COUNT(*) AS total_arrivals
            FROM trips_with_station_info
            WHERE end_station_found = TRUE
            GROUP BY end_station_number
        )
        SELECT
            d.station_number,
            d.station_name,
            d.latitude,
            d.longitude,
            d.total_departures,
            COALESCE(a.total_arrivals, 0) AS total_arrivals,
            d.total_departures - COALESCE(a.total_arrivals, 0) AS net_departures
        FROM departures d
        LEFT JOIN arrivals a
            ON d.station_number = a.station_number
        ORDER BY ABS(d.total_departures - COALESCE(a.total_arrivals, 0)) DESC;
    """,
    "top_routes.csv": """
        SELECT
            start_station_number,
            start_station_name,
            end_station_number,
            end_station_name,
            COUNT(*) AS total_trips,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM trips_with_station_info
        WHERE start_station_found = TRUE
          AND end_station_found = TRUE
          AND start_station_number <> end_station_number
        GROUP BY
            start_station_number,
            start_station_name,
            end_station_number,
            end_station_name
        ORDER BY total_trips DESC
        LIMIT 500;
    """,
    "user_profile_summary.csv": """
        WITH user_profiles AS (
            SELECT
                gender,
                TRY_CAST(age AS INTEGER) AS user_age,
                duration_minutes
            FROM trips_analysis
        )
        SELECT
            gender,
            CASE
                WHEN user_age IS NULL THEN 'Unknown'
                WHEN user_age < 18 THEN 'Under 18'
                WHEN user_age BETWEEN 18 AND 24 THEN '18-24'
                WHEN user_age BETWEEN 25 AND 34 THEN '25-34'
                WHEN user_age BETWEEN 35 AND 44 THEN '35-44'
                WHEN user_age BETWEEN 45 AND 54 THEN '45-54'
                WHEN user_age BETWEEN 55 AND 64 THEN '55-64'
                ELSE '65+'
            END AS age_group,
            COUNT(*) AS total_trips,
            AVG(duration_minutes) AS avg_duration_minutes
        FROM user_profiles
        GROUP BY gender, age_group
        ORDER BY gender, age_group;
    """,
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(DATABASE_PATH), read_only=True)

    for file_name, query in QUERIES.items():
        output_path = OUTPUT_DIR / file_name
        clean_query = query.strip().rstrip(";")
        connection.execute(
            f"""
            COPY ({clean_query})
            TO '{output_path.as_posix()}'
            WITH (HEADER, DELIMITER ',');
            """
        )
        print(f"Exported: {output_path}")

    connection.close()


if __name__ == "__main__":
    main()
