from pathlib import Path
import csv
import duckdb
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

TRIPS_RAW_DIR = BASE_DIR / "data" / "raw" / "trips"
STATION_INFORMATION_PATH = BASE_DIR / "data" / "processed" / "station_information.csv"
DATABASE_DIR = BASE_DIR / "data" / "database"
DATABASE_PATH = DATABASE_DIR / "ecobici.duckdb"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)


EXPECTED_COLUMNS = [
    "Genero_Usuario",
    "Edad_Usuario",
    "Bici",
    "Ciclo_Estacion_Retiro",
    "Fecha_Retiro",
    "Hora_Retiro",
    "Ciclo_EstacionArribo",
    "Fecha_Arribo",
    "Hora_Arribo",
]


COLUMN_ALIASES = {
    "Genero_Usuario": [
        "Genero_Usuario",
        "Genero_usuario",
    ],
    "Edad_Usuario": [
        "Edad_Usuario",
        "Edad_usuario",
    ],
    "Bici": [
        "Bici",
    ],
    "Ciclo_Estacion_Retiro": [
        "Ciclo_Estacion_Retiro",
        "CE_retiro",
    ],
    "Fecha_Retiro": [
        "Fecha_Retiro",
        "Fecha_retiro",
    ],
    "Hora_Retiro": [
        "Hora_Retiro",
        "Hora_retiro",
    ],
    "Ciclo_EstacionArribo": [
        "Ciclo_EstacionArribo",
        "Ciclo_Estacion_Arribo",
        "CE_arribo",
    ],
    "Fecha_Arribo": [
        "Fecha_Arribo",
        "Fecha Arribo",
        "Fecha_arribo",
    ],
    "Hora_Arribo": [
        "Hora_Arribo",
        "Hora_arribo",
    ],
}


def detect_separator(file_path: Path) -> str:
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as file:
        sample = file.read(4096)

    try:
        dialect = csv.Sniffer().sniff(sample)
        return dialect.delimiter
    except csv.Error:
        return ","


def normalize_column_name(column_name: str) -> str:
    text = str(column_name).strip().lower()

    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
    }

    for original, replacement in replacements.items():
        text = text.replace(original, replacement)

    text = text.replace("_", "")
    text = text.replace(" ", "")

    return text


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized_original_columns = {
        normalize_column_name(column): column
        for column in df.columns
    }

    rename_map = {}

    for standard_column, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_column_name(alias)

            if normalized_alias in normalized_original_columns:
                original_column = normalized_original_columns[normalized_alias]
                rename_map[original_column] = standard_column
                break

    return df.rename(columns=rename_map)


def normalize_station_key(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if text.isdigit():
        return str(int(text))

    return text


def normalize_gender(value) -> str:
    if pd.isna(value):
        return "?"

    text = str(value).strip().upper()

    if text in {"M", "F", "O", "?"}:
        return text

    return "?"


def load_station_catalog() -> pd.DataFrame:
    stations = pd.read_csv(
        STATION_INFORMATION_PATH,
        dtype={"station_number": str},
    )

    stations["station_number"] = stations["station_number"].apply(normalize_station_key)

    return stations


def prepare_trips_chunk(
    chunk: pd.DataFrame,
    file_name: str,
    row_offset: int,
    valid_station_keys: set,
) -> pd.DataFrame:
    chunk.columns = [column.strip() for column in chunk.columns]
    chunk = standardize_columns(chunk)

    missing_columns = [column for column in EXPECTED_COLUMNS if column not in chunk.columns]

    if missing_columns:
        raise ValueError(
            f"{file_name} is missing required columns after standardization: {missing_columns}"
        )

    df = chunk[EXPECTED_COLUMNS].copy()

    df["source_file"] = file_name

    df["trip_id"] = [
        f"{file_name.replace('.csv', '')}_{row_offset + index}"
        for index in range(len(df))
    ]

    df["gender"] = df["Genero_Usuario"].apply(normalize_gender)
    df["age"] = pd.to_numeric(df["Edad_Usuario"], errors="coerce").astype("Int64")
    df["bike_id"] = df["Bici"].astype(str).str.strip()

    df["start_station_number"] = df["Ciclo_Estacion_Retiro"].apply(normalize_station_key)
    df["end_station_number"] = df["Ciclo_EstacionArribo"].apply(normalize_station_key)

    df["start_station_found"] = df["start_station_number"].isin(valid_station_keys)
    df["end_station_found"] = df["end_station_number"].isin(valid_station_keys)

    df["start_datetime"] = parse_ecobici_datetime(
        df["Fecha_Retiro"],
        df["Hora_Retiro"],
    )

    df["end_datetime"] = parse_ecobici_datetime(
        df["Fecha_Arribo"],
        df["Hora_Arribo"],
    )

    df["duration_minutes"] = (
        df["end_datetime"] - df["start_datetime"]
    ).dt.total_seconds() / 60

    df["start_date"] = df["start_datetime"].dt.date
    df["end_date"] = df["end_datetime"].dt.date

    df["year"] = df["start_datetime"].dt.year.astype("Int64")
    df["month"] = df["start_datetime"].dt.month.astype("Int64")
    df["day"] = df["start_datetime"].dt.day.astype("Int64")
    df["hour"] = df["start_datetime"].dt.hour.astype("Int64")

    # Monday = 0, Sunday = 6
    df["weekday"] = df["start_datetime"].dt.weekday.astype("Int64")
    df["is_weekend"] = df["weekday"].isin([5, 6])

    final_columns = [
        "trip_id",
        "source_file",
        "gender",
        "age",
        "bike_id",
        "start_station_number",
        "end_station_number",
        "start_datetime",
        "end_datetime",
        "duration_minutes",
        "start_date",
        "end_date",
        "year",
        "month",
        "day",
        "hour",
        "weekday",
        "is_weekend",
        "start_station_found",
        "end_station_found",
    ]

    return df[final_columns]

def parse_ecobici_datetime(date_series: pd.Series, time_series: pd.Series) -> pd.Series:
    datetime_text = (
        date_series.astype(str).str.strip()
        + " "
        + time_series.astype(str).str.strip()
    )

    parsed = pd.to_datetime(
        datetime_text,
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce",
    )

    missing_mask = parsed.isna()

    if missing_mask.any():
        parsed_two_digit_year = pd.to_datetime(
            datetime_text[missing_mask],
            format="%d/%m/%y %H:%M:%S",
            errors="coerce",
        )

        parsed.loc[missing_mask] = parsed_two_digit_year

    return parsed

def create_database_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("DROP TABLE IF EXISTS trips_clean;")
    connection.execute("DROP TABLE IF EXISTS stations;")

    connection.execute(
        """
        CREATE TABLE stations (
            station_id VARCHAR,
            external_id VARCHAR,
            station_number VARCHAR,
            station_name VARCHAR,
            latitude DOUBLE,
            longitude DOUBLE,
            capacity INTEGER,
            rental_methods VARCHAR,
            has_kiosk BOOLEAN
        );
        """
    )

    connection.execute(
        """
        CREATE TABLE trips_clean (
            trip_id VARCHAR,
            source_file VARCHAR,
            gender VARCHAR,
            age INTEGER,
            bike_id VARCHAR,
            start_station_number VARCHAR,
            end_station_number VARCHAR,
            start_datetime TIMESTAMP,
            end_datetime TIMESTAMP,
            duration_minutes DOUBLE,
            start_date DATE,
            end_date DATE,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            hour INTEGER,
            weekday INTEGER,
            is_weekend BOOLEAN,
            start_station_found BOOLEAN,
            end_station_found BOOLEAN
        );
        """
    )


def main() -> None:
    if not STATION_INFORMATION_PATH.exists():
        raise FileNotFoundError(f"Station catalog not found: {STATION_INFORMATION_PATH}")

    csv_files = sorted(TRIPS_RAW_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in: {TRIPS_RAW_DIR}")

    stations = load_station_catalog()
    valid_station_keys = set(stations["station_number"])

    connection = duckdb.connect(str(DATABASE_PATH))
    create_database_schema(connection)

    connection.register("stations_df", stations)
    connection.execute("INSERT INTO stations SELECT * FROM stations_df;")
    connection.unregister("stations_df")

    total_inserted_rows = 0

    for file_path in csv_files:
        print(f"\nProcessing {file_path.name}")

        separator = detect_separator(file_path)

        try:
            reader = pd.read_csv(
                file_path,
                sep=separator,
                chunksize=200_000,
                dtype=str,
                encoding="utf-8-sig",
            )
        except UnicodeDecodeError:
            reader = pd.read_csv(
                file_path,
                sep=separator,
                chunksize=200_000,
                dtype=str,
                encoding="latin1",
            )

        file_inserted_rows = 0

        for chunk_index, chunk in enumerate(reader, start=1):
            processed_chunk = prepare_trips_chunk(
                chunk=chunk,
                file_name=file_path.name,
                row_offset=file_inserted_rows,
                valid_station_keys=valid_station_keys,
            )

            connection.register("processed_chunk_df", processed_chunk)
            connection.execute("INSERT INTO trips_clean SELECT * FROM processed_chunk_df;")
            connection.unregister("processed_chunk_df")

            file_inserted_rows += len(processed_chunk)
            total_inserted_rows += len(processed_chunk)

            print(
                f"  Chunk {chunk_index} inserted. "
                f"File rows: {file_inserted_rows:,} | "
                f"Total rows: {total_inserted_rows:,}"
            )

    print("\nDatabase created successfully.")
    print(f"Database path: {DATABASE_PATH}")
    print(f"Total rows inserted: {total_inserted_rows:,}")

    print("\nQuick validation:")
    result = connection.execute(
        """
        SELECT
            COUNT(*) AS total_trips,
            COUNT(*) FILTER (WHERE start_datetime IS NULL) AS invalid_start_datetime,
            COUNT(*) FILTER (WHERE end_datetime IS NULL) AS invalid_end_datetime,
            COUNT(*) FILTER (WHERE duration_minutes < 0) AS negative_duration_trips,
            COUNT(*) FILTER (WHERE start_station_found = FALSE) AS missing_start_station_trips,
            COUNT(*) FILTER (WHERE end_station_found = FALSE) AS missing_end_station_trips
        FROM trips_clean;
        """
    ).fetchdf()

    print(result.to_string(index=False))

    connection.close()


if __name__ == "__main__":
    main()