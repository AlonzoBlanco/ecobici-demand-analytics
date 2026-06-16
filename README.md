# ECOBICI Demand Analytics

End-to-end data analytics project using public ECOBICI trip data from Mexico City. The project processes historical trip records from 2022 onward, enriches them with station metadata, stores the cleaned data in a local DuckDB database, and exports aggregated datasets for dashboard creation in Power BI.

The main goal is not to replicate the official ECOBICI app or show real-time bike availability. Instead, this project focuses on historical demand analysis: usage patterns, peak hours, station activity, frequent routes, user profiles, and station flow balance.

## Project Overview

ECOBICI provides public historical trip data in monthly CSV files. These files contain millions of records and include information such as user gender, user age, bike ID, start station, start date/time, end station, and end date/time.

This project builds a reproducible pipeline to:

* download and clean station metadata from the GBFS `station_information` feed;
* audit inconsistent CSV column names across historical files;
* standardize historical trip data;
* validate station references and datetime fields;
* build a local DuckDB database;
* create clean analysis views;
* export aggregated datasets for Power BI;
* design dashboards focused on demand, stations, routes, and user behavior.

## Data Source

The historical trip CSV files are not included in this repository because they are large and publicly available from the official ECOBICI website.

Download the historical monthly CSV files from:

https://ecobici.cdmx.gob.mx/datos-abiertos/

For this project, data from **2022 onward** was used. Earlier data was intentionally excluded because mobility patterns before and during the COVID-19 pandemic may not represent the current behavior of the system.

Station metadata was obtained from the ECOBICI GBFS real-time feed:

https://gbfs.mex.lyftbikes.com/gbfs/gbfs.json

The `station_information` feed was used to obtain station names, station numbers, latitude, longitude, and capacity.

## Dataset Fields

The historical CSV files mainly contain the following fields:

```text
Genero_Usuario
Edad_Usuario
Bici
Ciclo_Estacion_Retiro
Fecha_Retiro
Hora_Retiro
Ciclo_EstacionArribo
Fecha_Arribo
Hora_Arribo
```

Some 2022 files use different column names, such as:

```text
Ciclo_Estacion_Arribo
Fecha Arribo
CE_retiro
CE_arribo
Fecha_retiro
Hora_retiro
```

Because of this, the project includes a column standardization step before loading the data into the database.

## Tech Stack

* Python 3.12
* pandas
* DuckDB
* Requests
* Power BI
* CSV / JSON data processing

## Project Structure

```text
ecobici-demand-analytics/
│
├── data/
│   ├── raw/
│   │   ├── trips/                  # Historical ECOBICI CSV files
│   │   └── station_information_*.json
│   │
│   ├── processed/
│   │   └── station_information.csv
│   │
│   ├── database/
│   │   └── ecobici.duckdb
│   │
│   ├── validation/
│   │   ├── csv_columns_audit.csv
│   │   ├── missing_station_usage.csv
│   │   └── quality_by_file.csv
│   │
│   └── exports/
│       ├── monthly_trips.csv
│       ├── weekday_trips.csv
│       ├── hourly_trips.csv
│       ├── hourly_weekday_trips.csv
│       ├── station_flow_balance.csv
│       ├── top_start_stations.csv
│       ├── top_end_stations.csv
│       ├── top_routes.csv
│       └── user_profile_summary.csv
│
├── scripts/
│   ├── download_station_information.py
│   ├── audit_csv_columns.py
│   ├── validate_historical_trips.py
│   ├── analyze_missing_station_usage.py
│   ├── build_duckdb_database.py
│   ├── run_quality_checks.py
│   ├── create_analysis_views.py
│   └── export_dashboard_datasets.py
│
├── requirements.txt
└── README.md
```

## Setup

Create a virtual environment:

```bash
py -3.12 -m venv .venv
```

Activate it on Windows:

```bash
.\.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Example `requirements.txt`:

```text
requests
pandas
duckdb
```

## How to Run the Pipeline

### 1. Download Station Information

```bash
python scripts/download_station_information.py
```

This downloads the ECOBICI `station_information` feed and creates a cleaned station catalog:

```text
data/processed/station_information.csv
```

### 2. Audit Historical CSV Columns

```bash
python scripts/audit_csv_columns.py
```

This checks the column names used in each historical CSV file. This step is important because some 2022 files use different column names.

### 3. Validate Historical Trips

```bash
python scripts/validate_historical_trips.py
```

This validates:

* number of rows per file;
* unique start and end stations;
* station references missing from the current station catalog;
* invalid date and time values;
* user gender distribution.

### 4. Analyze Missing Station Usage

```bash
python scripts/analyze_missing_station_usage.py
```

This calculates how many trips are affected by stations that do not appear in the current station metadata.

### 5. Build the DuckDB Database

```bash
python scripts/build_duckdb_database.py
```

This creates the local database:

```text
data/database/ecobici.duckdb
```

The main table is:

```text
trips_clean
```

This table contains cleaned and standardized trip data, including:

```text
start_datetime
end_datetime
duration_minutes
year
month
day
hour
weekday
is_weekend
start_station_found
end_station_found
```

### 6. Run Quality Checks

```bash
python scripts/run_quality_checks.py
```

Final quality check summary:

```text
Total trips loaded: 67,686,742
Invalid start datetime records: 20
Invalid end datetime records: 0
Trips over 3 hours: 58,070
Trips over 24 hours: 13,425
Missing start station references: 264,356
Missing end station references: 274,596
```

Only 20 records had invalid start datetime values after handling both 2-digit and 4-digit year formats.

### 7. Create Analysis Views

```bash
python scripts/create_analysis_views.py
```

This creates a clean analysis view:

```text
trips_analysis
```

The analysis view keeps trips that meet the following conditions:

```sql
start_datetime IS NOT NULL
end_datetime IS NOT NULL
duration_minutes > 0
duration_minutes <= 180
```

Final clean dataset:

```text
Clean trips: 67,628,652
Average duration: 15.31 minutes
```

### 8. Export Dashboard Datasets

```bash
python scripts/export_dashboard_datasets.py
```

This creates aggregated CSV files for Power BI in:

```text
data/exports/
```

These files are much lighter than the full trip table and are designed for dashboard visualizations.

## Power BI Dashboard

The Power BI dashboard is designed around four main pages:

### 1. Overview

General system usage summary.

Suggested visuals:

* total trips;
* average trip duration;
* trips by year and month;
* trips by weekday;
* trips by hour.

### 2. Demand Patterns

Analysis of when ECOBICI is used the most.

Suggested visuals:

* hourly demand;
* weekday vs hour heatmap;
* monthly trends;
* weekday/weekend comparison.

### 3. Stations and Balance

Station-level behavior and flow balance.

Suggested visuals:

* top departure stations;
* top arrival stations;
* stations with positive or negative net flow;
* map using station latitude and longitude;
* demand relative to station capacity.

### 4. Routes and Users

Most common routes and user profile analysis.

Suggested visuals:

* top origin-destination routes;
* average duration by route;
* trips by gender;
* trips by age group.

## Key Data Cleaning Decisions

### Original CSV Files Are Preserved

Raw files are kept unchanged in:

```text
data/raw/trips/
```

All transformations are performed through Python scripts to keep the process reproducible.

### Station Numbers Are Treated as Text

Station identifiers such as `072` are normalized to match the station catalog, but station numbers are not treated as numeric measures in the dashboard.

### Long Trips Are Preserved but Excluded from Main Analysis

Trips longer than 3 hours are kept in the raw cleaned table, but excluded from the main analysis view to avoid distorting normal mobility patterns.

### Missing Historical Stations Are Not Deleted

Some historical station references do not appear in the current station catalog. These records are preserved, but marked using:

```text
start_station_found
end_station_found
```

This allows general demand analysis to use all valid trips, while geographic analysis can filter only trips with known station coordinates.

## Main Results

After cleaning and validation:

```text
Total trips loaded: 67,686,742
Clean trips used for analysis: 67,628,652
Average trip duration: 15.31 minutes
Invalid start datetime records: 20
Invalid end datetime records: 0
```

The resulting dataset is ready for SQL analysis, Power BI dashboards, and future machine learning work.

## Future Improvements

Possible future improvements include:

* building a demand classification model for low, medium, and high station demand;
* adding weather data to analyze the effect of rain and temperature;
* comparing demand before and after station expansions;
* creating a lightweight web version of the dashboard for portfolio presentation;
* automating monthly data ingestion.

## Purpose

This project was developed as a portfolio data analytics project to demonstrate:

* data cleaning with Python;
* processing large CSV files;
* working with real public data;
* SQL-based analysis using DuckDB;
* data validation and quality checks;
* dashboard preparation for Power BI;
* analysis of urban mobility patterns.
