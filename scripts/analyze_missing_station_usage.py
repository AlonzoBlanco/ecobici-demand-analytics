from pathlib import Path
import csv
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

TRIPS_RAW_DIR = BASE_DIR / "data" / "raw" / "trips"
STATION_INFORMATION_PATH = BASE_DIR / "data" / "processed" / "station_information.csv"
VALIDATION_DIR = BASE_DIR / "data" / "validation"

VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


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


def load_station_keys() -> set:
    stations = pd.read_csv(
        STATION_INFORMATION_PATH,
        dtype={"station_number": str},
    )

    stations["station_key"] = stations["station_number"].apply(normalize_station_key)

    return set(stations["station_key"])


def update_missing_counts(
    missing_counts: dict,
    file_name: str,
    role: str,
    station_series: pd.Series,
    valid_station_keys: set,
) -> int:
    station_keys = station_series.apply(normalize_station_key)

    missing_mask = ~station_keys.isin(valid_station_keys) & (station_keys != "")
    missing_values = station_keys[missing_mask]

    counts = missing_values.value_counts()

    for station_key, count in counts.items():
        key = (file_name, role, station_key)
        missing_counts[key] = missing_counts.get(key, 0) + int(count)

    return int(missing_mask.sum())


def main() -> None:
    valid_station_keys = load_station_keys()
    csv_files = sorted(TRIPS_RAW_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {TRIPS_RAW_DIR}")

    missing_counts = {}
    file_summaries = []

    total_rows = 0
    total_missing_start_rows = 0
    total_missing_end_rows = 0

    for file_path in csv_files:
        print(f"\nAnalyzing: {file_path.name}")

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

        file_rows = 0
        file_missing_start_rows = 0
        file_missing_end_rows = 0

        for chunk_index, chunk in enumerate(reader, start=1):
            chunk.columns = [column.strip() for column in chunk.columns]
            chunk = standardize_columns(chunk)

            file_rows += len(chunk)

            if "Ciclo_Estacion_Retiro" in chunk.columns:
                file_missing_start_rows += update_missing_counts(
                    missing_counts,
                    file_path.name,
                    "start",
                    chunk["Ciclo_Estacion_Retiro"],
                    valid_station_keys,
                )

            if "Ciclo_EstacionArribo" in chunk.columns:
                file_missing_end_rows += update_missing_counts(
                    missing_counts,
                    file_path.name,
                    "end",
                    chunk["Ciclo_EstacionArribo"],
                    valid_station_keys,
                )

            print(f"  Chunk {chunk_index} processed. Rows so far: {file_rows:,}")

        total_rows += file_rows
        total_missing_start_rows += file_missing_start_rows
        total_missing_end_rows += file_missing_end_rows

        file_summaries.append({
            "file": file_path.name,
            "rows": file_rows,
            "missing_start_rows": file_missing_start_rows,
            "missing_end_rows": file_missing_end_rows,
            "missing_start_percentage": file_missing_start_rows / file_rows * 100 if file_rows else 0,
            "missing_end_percentage": file_missing_end_rows / file_rows * 100 if file_rows else 0,
        })

    missing_rows = []

    for (file_name, role, station_key), count in missing_counts.items():
        missing_rows.append({
            "file": file_name,
            "role": role,
            "station_key": station_key,
            "affected_trips": count,
        })

    missing_df = pd.DataFrame(missing_rows)
    summary_df = pd.DataFrame(file_summaries)

    if not missing_df.empty:
        missing_df = missing_df.sort_values(
            by="affected_trips",
            ascending=False,
        )

    missing_output = VALIDATION_DIR / "missing_station_usage.csv"
    summary_output = VALIDATION_DIR / "missing_station_usage_by_file.csv"

    missing_df.to_csv(missing_output, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_output, index=False, encoding="utf-8-sig")

    unique_missing_stations = missing_df["station_key"].nunique() if not missing_df.empty else 0

    print("\nAnalysis finished.")
    print(f"Rows analyzed: {total_rows:,}")
    print(f"Unique missing stations: {unique_missing_stations:,}")
    print(f"Trips with missing start station: {total_missing_start_rows:,}")
    print(f"Trips with missing end station: {total_missing_end_rows:,}")

    if total_rows:
        print(f"Missing start percentage: {total_missing_start_rows / total_rows * 100:.4f}%")
        print(f"Missing end percentage: {total_missing_end_rows / total_rows * 100:.4f}%")

    print(f"\nSaved: {missing_output}")
    print(f"Saved: {summary_output}")

    if not missing_df.empty:
        print("\nTop missing stations:")
        print(missing_df.head(20))


if __name__ == "__main__":
    main()