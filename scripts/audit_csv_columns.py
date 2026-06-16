from pathlib import Path
import csv
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
TRIPS_RAW_DIR = BASE_DIR / "data" / "raw" / "trips"
VALIDATION_DIR = BASE_DIR / "data" / "validation"

VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


def detect_separator(file_path: Path) -> str:
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as file:
        sample = file.read(4096)

    try:
        dialect = csv.Sniffer().sniff(sample)
        return dialect.delimiter
    except csv.Error:
        return ","


def main():
    rows = []

    csv_files = sorted(TRIPS_RAW_DIR.glob("*.csv"))

    for file_path in csv_files:
        separator = detect_separator(file_path)

        try:
            df = pd.read_csv(
                file_path,
                sep=separator,
                nrows=0,
                encoding="utf-8-sig",
            )
        except UnicodeDecodeError:
            df = pd.read_csv(
                file_path,
                sep=separator,
                nrows=0,
                encoding="latin1",
            )

        columns = [column.strip() for column in df.columns]

        rows.append({
            "file": file_path.name,
            "separator": repr(separator),
            "columns": " | ".join(columns),
        })

    output_path = VALIDATION_DIR / "csv_columns_audit.csv"
    pd.DataFrame(rows).to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Column audit saved to: {output_path}")


if __name__ == "__main__":
    main()