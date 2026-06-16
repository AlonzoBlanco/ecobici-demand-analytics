from pathlib import Path
import csv
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

TRIPS_RAW_DIR = BASE_DIR / "data" / "raw" / "trips"
STATION_INFORMATION_PATH = BASE_DIR / "data" / "processed" / "station_information.csv"
VALIDATION_DIR = BASE_DIR / "data" / "validation"

VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


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
    """
    Detects whether the CSV uses comma, semicolon, tab, etc.
    """
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
    """
    Creates a safer station key for matching historical data
    with station_information.

    Examples:
    "022" -> "22"
    "22" -> "22"
    "22.0" -> "22"
    "390-391" -> "390-391"
    """
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if text.isdigit():
        return str(int(text))

    return text


def load_station_catalog() -> pd.DataFrame:
    stations = pd.read_csv(
        STATION_INFORMATION_PATH,
        dtype={"station_number": str},
    )

    stations["station_key"] = stations["station_number"].apply(normalize_station_key)

    return stations


def validate_file(file_path: Path, station_keys: set, chunksize: int = 200_000) -> tuple[dict, list[dict]]:
    separator = detect_separator(file_path)

    total_rows = 0
    gender_counts = {}
    start_stations = set()
    end_stations = set()
    missing_start_stations = set()
    missing_end_stations = set()
    invalid_dates = 0
    invalid_times = 0

    print(f"\nValidating: {file_path.name}")
    print(f"Detected separator: {repr(separator)}")

    try:
        reader = pd.read_csv(
            file_path,
            sep=separator,
            chunksize=chunksize,
            dtype=str,
            encoding="utf-8-sig",
        )
    except UnicodeDecodeError:
        reader = pd.read_csv(
            file_path,
            sep=separator,
            chunksize=chunksize,
            dtype=str,
            encoding="latin1",
        )

    detected_columns = None

    for chunk_index, chunk in enumerate(reader, start=1):
        chunk.columns = [column.strip() for column in chunk.columns]
        chunk = standardize_columns(chunk)

        if detected_columns is None:
            detected_columns = list(chunk.columns)

            missing_columns = [col for col in EXPECTED_COLUMNS if col not in detected_columns]
            extra_columns = [col for col in detected_columns if col not in EXPECTED_COLUMNS]

            if missing_columns:
                print(f"Missing columns: {missing_columns}")

            if extra_columns:
                print(f"Extra columns: {extra_columns}")

        total_rows += len(chunk)

        if "Genero_Usuario" in chunk.columns:
            counts = chunk["Genero_Usuario"].fillna("?").str.strip().value_counts()
            for gender, count in counts.items():
                gender_counts[gender] = gender_counts.get(gender, 0) + int(count)

        if "Ciclo_Estacion_Retiro" in chunk.columns:
            start_keys = set(chunk["Ciclo_Estacion_Retiro"].apply(normalize_station_key))
            start_keys.discard("")
            start_stations.update(start_keys)
            missing_start_stations.update(start_keys - station_keys)

        if "Ciclo_EstacionArribo" in chunk.columns:
            end_keys = set(chunk["Ciclo_EstacionArribo"].apply(normalize_station_key))
            end_keys.discard("")
            end_stations.update(end_keys)
            missing_end_stations.update(end_keys - station_keys)

        if "Fecha_Retiro" in chunk.columns:
            parsed_dates = pd.to_datetime(
                chunk["Fecha_Retiro"],
                format="%d/%m/%Y",
                errors="coerce",
            )
            invalid_dates += int(parsed_dates.isna().sum())

        if "Hora_Retiro" in chunk.columns:
            parsed_times = pd.to_datetime(
                chunk["Hora_Retiro"],
                format="%H:%M:%S",
                errors="coerce",
            )
            invalid_times += int(parsed_times.isna().sum())

        print(f"  Chunk {chunk_index} processed. Rows so far: {total_rows:,}")

    summary = {
        "file": file_path.name,
        "rows": total_rows,
        "unique_start_stations": len(start_stations),
        "unique_end_stations": len(end_stations),
        "missing_start_stations": len(missing_start_stations),
        "missing_end_stations": len(missing_end_stations),
        "invalid_fecha_retiro": invalid_dates,
        "invalid_hora_retiro": invalid_times,
        "gender_M": gender_counts.get("M", 0),
        "gender_F": gender_counts.get("F", 0),
        "gender_O": gender_counts.get("O", 0),
        "gender_unknown": gender_counts.get("?", 0),
    }

    missing_rows = []

    for station in sorted(missing_start_stations):
        missing_rows.append({
            "file": file_path.name,
            "station_key": station,
            "missing_in": "Ciclo_Estacion_Retiro",
        })

    for station in sorted(missing_end_stations):
        missing_rows.append({
            "file": file_path.name,
            "station_key": station,
            "missing_in": "Ciclo_EstacionArribo",
        })

    return summary, missing_rows


def main() -> None:
    if not STATION_INFORMATION_PATH.exists():
        raise FileNotFoundError(
            f"Station information file not found: {STATION_INFORMATION_PATH}"
        )

    if not TRIPS_RAW_DIR.exists():
        raise FileNotFoundError(
            f"Trips folder not found: {TRIPS_RAW_DIR}"
        )

    stations = load_station_catalog()
    station_keys = set(stations["station_key"])

    csv_files = sorted(TRIPS_RAW_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in: {TRIPS_RAW_DIR}"
        )

    all_summaries = []
    all_missing_rows = []

    print(f"Station catalog loaded: {len(stations):,} stations")
    print(f"CSV files found: {len(csv_files)}")

    for file_path in csv_files:
        summary, missing_rows = validate_file(file_path, station_keys)
        all_summaries.append(summary)
        all_missing_rows.extend(missing_rows)

    summary_df = pd.DataFrame(all_summaries)
    missing_df = pd.DataFrame(all_missing_rows)

    summary_output = VALIDATION_DIR / "historical_files_summary.csv"
    missing_output = VALIDATION_DIR / "missing_stations_summary.csv"

    summary_df.to_csv(summary_output, index=False, encoding="utf-8-sig")
    missing_df.to_csv(missing_output, index=False, encoding="utf-8-sig")

    print("\nValidation finished.")
    print(f"Summary saved to: {summary_output}")
    print(f"Missing stations saved to: {missing_output}")

    print("\nGeneral summary:")
    print(summary_df)

    total_rows = summary_df["rows"].sum()
    total_missing_start = summary_df["missing_start_stations"].sum()
    total_missing_end = summary_df["missing_end_stations"].sum()

    print("\nTotals:")
    print(f"Rows analyzed: {total_rows:,}")
    print(f"Missing start station references: {total_missing_start:,}")
    print(f"Missing end station references: {total_missing_end:,}")


if __name__ == "__main__":
    main()