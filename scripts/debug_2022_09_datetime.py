from pathlib import Path
import csv
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

FILE_PATH = BASE_DIR / "data" / "raw" / "trips" / "2022-09.csv"
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


def main() -> None:
    separator = detect_separator(FILE_PATH)

    print(f"Reading: {FILE_PATH}")
    print(f"Detected separator: {repr(separator)}")

    df = pd.read_csv(
        FILE_PATH,
        sep=separator,
        dtype=str,
        encoding="utf-8-sig",
    )

    df.columns = [column.strip() for column in df.columns]
    df = standardize_columns(df)

    print("\nColumns after standardization:")
    print(df.columns.tolist())

    start_text = (
        df["Fecha_Retiro"].astype(str).str.strip()
        + " "
        + df["Hora_Retiro"].astype(str).str.strip()
    )

    end_text = (
        df["Fecha_Arribo"].astype(str).str.strip()
        + " "
        + df["Hora_Arribo"].astype(str).str.strip()
    )

    start_datetime = pd.to_datetime(
        start_text,
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce",
    )

    end_datetime = pd.to_datetime(
        end_text,
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce",
    )

    invalid_start_mask = start_datetime.isna()
    invalid_end_mask = end_datetime.isna()

    print("\nDatetime validation:")
    print(f"Total rows: {len(df):,}")
    print(f"Invalid start datetime: {invalid_start_mask.sum():,}")
    print(f"Invalid end datetime: {invalid_end_mask.sum():,}")

    invalid_sample = df[invalid_start_mask | invalid_end_mask].copy()
    invalid_sample["raw_start_datetime_text"] = start_text[invalid_start_mask | invalid_end_mask]
    invalid_sample["raw_end_datetime_text"] = end_text[invalid_start_mask | invalid_end_mask]

    sample_output = VALIDATION_DIR / "invalid_datetime_2022_09_sample.csv"
    invalid_sample.head(500).to_csv(sample_output, index=False, encoding="utf-8-sig")

    print(f"\nInvalid datetime sample saved to: {sample_output}")

    print("\nMost common Fecha_Retiro values among invalid rows:")
    print(
        df.loc[invalid_start_mask, "Fecha_Retiro"]
        .value_counts(dropna=False)
        .head(20)
        .to_string()
    )

    print("\nMost common Hora_Retiro values among invalid rows:")
    print(
        df.loc[invalid_start_mask, "Hora_Retiro"]
        .value_counts(dropna=False)
        .head(20)
        .to_string()
    )

    valid_duration_mask = start_datetime.notna() & end_datetime.notna()

    durations = (
        end_datetime[valid_duration_mask] - start_datetime[valid_duration_mask]
    ).dt.total_seconds() / 60

    print("\nDuration summary for valid datetimes:")
    print(durations.describe().to_string())

    long_trips = df[valid_duration_mask].copy()
    long_trips["start_datetime"] = start_datetime[valid_duration_mask]
    long_trips["end_datetime"] = end_datetime[valid_duration_mask]
    long_trips["duration_minutes"] = durations

    long_trips_output = VALIDATION_DIR / "longest_trips_2022_09.csv"
    long_trips.sort_values("duration_minutes", ascending=False).head(500).to_csv(
        long_trips_output,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\nLongest trips sample saved to: {long_trips_output}")


if __name__ == "__main__":
    main()