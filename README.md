# VoltStream – EV Charging Event Processing & Data Quality Platform

VoltStream is a backend data processing platform designed to ingest, validate, process, and monitor electric vehicle (EV) charging events.

The platform processes charging event data from multiple stations, identifies invalid and duplicate records, reconstructs charging sessions from individual events, detects anomalous sessions, and stores processing results in PostgreSQL.

It also provides pipeline execution metrics, structured logging, and a configurable synthetic data generator to support reproducible testing and larger-scale data processing.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Database Design](#database-design)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Environment Configuration](#environment-configuration)
- [Database Initialization](#database-initialization)
- [Running the Pipeline](#running-the-pipeline)
- [Synthetic Data Generation](#synthetic-data-generation)
- [Data Quality and Anomaly Detection](#data-quality-and-anomaly-detection)
- [Pipeline Monitoring](#pipeline-monitoring)
- [Testing](#testing)
- [Logging](#logging)
- [Idempotency and Traceability](#idempotency-and-traceability)
- [Limitations](#limitations)

---

## Project Overview

EV charging infrastructure generates event-based data throughout the lifecycle of a charging session.

A typical charging session consists of events such as:

1. `START` – Indicates the beginning of a charging session.
2. `METER_READING` – Records intermediate energy consumption.
3. `STOP` – Indicates the completion of a charging session.

In real-world environments, incoming data may contain missing fields, invalid timestamps, duplicate events, inconsistent meter readings, unknown charging stations, and events arriving out of chronological order.

VoltStream addresses these challenges through a structured data processing pipeline.

The platform transforms raw charging events into structured charging sessions while maintaining data quality, anomaly information, and processing traceability.

## Key Features

### 1. CSV-Based Event Ingestion

- Reads charging events from CSV files.
- Validates required columns and file structure.
- Preserves source filename and row-number information.
- Handles malformed records and invalid CSV structures.

### 2. Data Validation

Validates incoming records for:

- Missing required fields.
- Invalid event types.
- Invalid timestamps.
- Missing timezone information.
- Negative or invalid meter readings.
- Unknown charging stations.
- Unexpected CSV columns.

Invalid records are stored separately with rejection codes, detailed explanations, and original source information.

### 3. Duplicate Event Detection

- Detects duplicate event IDs.
- Prevents duplicate event insertion.
- Tracks duplicate counts at the pipeline-run level.
- Uses file checksums to identify previously processed files.

### 4. Charging Session Reconstruction

Reconstructs charging sessions by grouping events using their session IDs and processing them chronologically.

Supports:

- Completed sessions.
- In-progress sessions.
- Sessions without intermediate meter readings.
- Late-arriving events.
- Meter-based energy consumption calculation.

### 5. Anomaly Detection

Identifies anomalous charging sessions, including:

- `STATION_MISMATCH`
- `MULTIPLE_START_EVENTS`
- `METER_READING_BEFORE_START`
- `DECREASING_METER_READING`
- `STOP_WITHOUT_START`
- `MULTIPLE_STOP_EVENTS`
- `EVENT_AFTER_STOP`

Anomaly reasons are stored in PostgreSQL using JSONB.

### 6. Pipeline Monitoring

Tracks:

- Total input records.
- Accepted records.
- Rejected records.
- Duplicate records.
- Anomalous charging sessions.
- Processing duration.
- Acceptance rate.
- Rejection rate.
- Duplicate rate.

### 7. Synthetic Data Generation

Provides a reproducible and configurable data generator that creates:

- Valid charging events.
- Invalid records.
- Anomalous charging sessions.
- Duplicate events.

The generator uses registered charging stations from PostgreSQL and supports configurable record counts and random seeds.

---

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Database Driver | psycopg |
| Data Input | CSV |
| Configuration | python-dotenv |
| Logging | Python Logging |
| Testing | pytest |
| Database Management | DBeaver |
| Containerization | Docker |

---

## System Architecture

VoltStream follows a modular, layered architecture.

### Processing Flow

```text
             CSV Input
                 |
                 v
          CSV Ingestion
                 |
                 v
          Record Validation
                 |
          +------+------+
          |             |
       Invalid        Valid
          |             |
          v             v
    Rejected Records  Duplicate Detection
          |             |
          |        +----+----+
          |        |         |
          |     Duplicate  New Event
          |        |         |
          |        |         v
          |        |    Event Storage
          |        |         |
          |        |         v
          |        |  Session Reconstruction
          |        |         |
          |        |         v
          |        |  Anomaly Detection
          |        |         |
          |        |         v
          |        |   Session Storage
          |        |         |
          +--------+---------+
                   |
                   v
              PostgreSQL
                   |
                   v
           Pipeline Monitoring
                   |
                   v
             Metrics & Logs
```

### Major Components

- **Ingestion:** Reads incoming CSV files and extracts individual records.
- **Validation:** Checks record structure, required fields, and data quality.
- **Transformation:** Converts raw records into structured event objects and reconstructs charging sessions.
- **Storage:** Persists charging events, reconstructed sessions, and rejected records.
- **Monitoring:** Calculates processing metrics and maintains execution logs.
- **Pipeline Orchestration:** Coordinates the complete processing workflow and tracks execution status.

---

## Project Structure

```text
VoltStream/
│
├── src/
│   ├── __init__.py
│   ├── database.py
│   ├── create_tables.py
│   ├── pipeline.py
│   ├── pipeline_processor.py
│   ├── verify_relationships.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── station.py
│   │   ├── pipeline_run.py
│   │   ├── charging_event.py
│   │   ├── charging_session.py
│   │   ├── rejected_record.py
│   │   └── batch_file.py
│   │
│   ├── ingestion/
│   ├── validation/
│   ├── transformation/
│   │   └── session_reconstructor.py
│   │
│   ├── storage/
│   │   ├── event_storage.py
│   │   └── session_storage.py
│   │
│   └── monitoring/
│       ├── metrics.py
│       └── logger.py
│
├── generators/
│   └── charging_event_generator.py
│
├── scripts/
│   ├── verify_metrics.py
│   ├── verify_generated_data.py
│   └── process_generated_data.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── data_quality/
│
├── data/
│   ├── input/
│   │   └── charging_events.csv
│   ├── generated/
│   └── output/
│
├── docs/
├── prompt_history/
│
├── requirements.txt
├── .gitignore
├── .env
└── README.md
```

---

## Database Design

VoltStream uses PostgreSQL for persistent storage.

The database consists of six primary entities.

| Table | Responsibility |
|---|---|
| `stations` | Stores registered charging station information. |
| `pipeline_runs` | Tracks pipeline execution and processing metrics. |
| `charging_events` | Stores validated charging events. |
| `charging_sessions` | Stores reconstructed charging sessions. |
| `rejected_records` | Stores invalid records and rejection details. |
| `batch_files` | Tracks individual input files, checksums, and processing status. |

### Important Relationships

- A charging station can have multiple charging events.
- A charging station can have multiple charging sessions.
- A pipeline run can contain multiple charging events.
- A pipeline run can contain multiple rejected records.
- A pipeline run can be associated with multiple batch files.
- Charging sessions retain the pipeline run that last processed them.

**Design consideration:** `charging_events.session_id` is intentionally not a foreign key to `charging_sessions.session_id`. This allows incoming events to arrive before their corresponding charging session has been reconstructed.

---

## Prerequisites

Ensure the following software is installed:

- Python 3.12 or compatible version.
- PostgreSQL 16 or compatible version.
- Docker (if running PostgreSQL through a container).
- Git.
- pip.

---

## Installation and Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd VoltStream
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Create a PostgreSQL database named:

```sql
CREATE DATABASE voltstream;
```

Alternatively, configure the project to connect to an existing PostgreSQL instance.

---

## Environment Configuration

Create a `.env` file in the project root.

Example:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=voltstream
DB_USER=postgres
DB_PASSWORD=your_password
```

Update the values according to your PostgreSQL configuration.

**Important:** Never commit `.env` or real database credentials to the public repository.

---

## Database Initialization

Initialize the database tables:

```powershell
python -m src.create_tables
```

Register charging stations before processing events.

Example:

```sql
INSERT INTO stations (
    station_id,
    station_name,
    city,
    max_power_kw
)
VALUES
(
    'ST001',
    'Salt Lake Charging Hub',
    'Kolkata',
    120
),
(
    'ST002',
    'New Town Charging Hub',
    'Kolkata',
    60
);
```

Only insert stations if they are not already registered.

---

## Running the Pipeline

A sample CSV dataset is available at:

```text
data/input/charging_events.csv
```

Execute the pipeline using the project's processing interface or the supplied metrics verification script.

Example:

```powershell
python -m scripts.verify_metrics
```

The script processes the sample CSV and displays pipeline execution metrics.

The core pipeline can also be invoked programmatically through:

```python
from src.database import SessionLocal
from src.pipeline import process_csv_file

db_session = SessionLocal()

try:
    result = process_csv_file(
        db_session,
        "data/input/charging_events.csv"
    )

    print(result)

finally:
    db_session.close()
```

The pipeline returns execution information, including run ID, batch information, processing status, and record counts.

---

## Synthetic Data Generation

VoltStream includes a configurable synthetic event generator.

Generate approximately 300 records:

```powershell
python -m generators.charging_event_generator --records 300 --seed 43
```

The generated file is saved under:

```text
data/generated/charging_events_generated.csv
```

### Generator Parameters

| Parameter | Description | Default |
|---|---|---|
| `--records` | Approximate number of records to generate | 300 |
| `--seed` | Random seed for reproducibility | 42 |
| `--output` | Generated CSV filename | charging_events_generated.csv |

Example:

```powershell
python -m generators.charging_event_generator --records 3000 --seed 100 --output large_dataset.csv
```

### Configurable Data Distribution

The generator uses the following default distribution:

| Category | Percentage |
|---|---:|
| Valid | 70% |
| Invalid | 15% |
| Anomalous | 10% |
| Duplicate | 5% |

The percentages represent generated session categories, not exact percentages of individual CSV rows. Duplicate scenarios add an additional event to the generated dataset.

### Verify Generated Data

```powershell
python -m scripts.verify_generated_data
```

### Process Generated Data

```powershell
python -m scripts.process_generated_data
```

The processing script displays the pipeline run information and calculated metrics.

---

## Data Quality and Anomaly Detection

VoltStream separates record-level validation from session-level anomaly detection.

### Record-Level Validation

Invalid records are rejected before event storage.

Examples:

- Invalid timestamp.
- Negative meter reading.
- Missing event ID.
- Invalid event type.
- Unknown charging station.

Rejected records retain their source information and rejection reasons.

### Session-Level Anomaly Detection

Some events can individually pass validation but still form an anomalous charging session.

Examples:

**Multiple START events**

```text
START -> START -> STOP
```

**STOP without START**

```text
METER_READING -> METER_READING -> STOP
```

**Decreasing meter reading**

```text
START (0 kWh)
      |
METER_READING (25 kWh)
      |
STOP (15 kWh)
```

These sessions are stored with `ANOMALOUS` status and their corresponding anomaly reasons.

---

## Pipeline Monitoring

The monitoring module calculates execution-level metrics.

Available metrics include:

| Metric | Description |
|---|---|
| Input Count | Total records received. |
| Accepted Count | Records successfully accepted. |
| Rejected Count | Invalid records rejected. |
| Duplicate Count | Duplicate event records detected. |
| Anomalous Session Count | Reconstructed sessions marked anomalous. |
| Processing Duration | Time taken by the pipeline. |
| Acceptance Rate | Percentage of accepted records. |
| Rejection Rate | Percentage of rejected records. |
| Duplicate Rate | Percentage of duplicate records. |

The metrics can be retrieved programmatically:

```python
from src.monitoring.metrics import calculate_run_metrics

metrics = calculate_run_metrics(
    db_session,
    run_id
)

print(metrics)
```

---

## Testing

VoltStream includes unit, integration, and data-quality tests.

Run the complete test suite:

```powershell
python -m pytest -v
```

The project currently contains 66 passing tests.

The tests cover:

- CSV ingestion.
- Record validation.
- Duplicate detection.
- Event transformation.
- Session reconstruction.
- Anomaly detection.
- Database storage.
- Pipeline processing.
- Metrics calculation.
- Logging behavior.
- Data-quality scenarios.

---

## Logging

VoltStream uses Python's logging module for structured execution logs.

Logs are written to:

```text
logs/voltstream.log
```

The logging system captures:

- Pipeline run creation.
- Pipeline execution start and completion.
- CSV processing activity.
- Session reconstruction.
- Record processing statistics.
- Duplicate file detection.
- Processing failures.

---

## Idempotency and Traceability

VoltStream implements safeguards to maintain processing traceability.

### File-Level Duplicate Detection

Input files are identified using SHA-256 checksums.

Previously processed files are detected and are not processed again under the existing batch-detection rules.

### Event-Level Duplicate Detection

Duplicate event IDs are detected before insertion.

### Processing Traceability

Every processing run has a unique run ID.

The system maintains relationships between pipeline runs, batch files, charging events, rejected records, and reconstructed sessions.

This allows processing results and data-quality issues to be traced back to their originating input.

---

## Limitations

The current implementation has the following scope and limitations:

- Input ingestion is CSV-based.
- Synthetic data is used for reproducible testing rather than representing real charging infrastructure data.
- The system does not currently expose a web-based dashboard or REST API.
- Processing is batch-oriented rather than real-time streaming.
- Duplicate event detection uses database lookups and is designed around the current event ID model.
- The generator creates synthetic scenarios; its data distributions are illustrative rather than statistically representative of production EV charging workloads.

---

## Project Objective

VoltStream demonstrates the design and implementation of a modular data processing platform capable of handling event-based charging data, maintaining data quality, reconstructing sessions, identifying anomalies, and monitoring pipeline execution.

The project emphasizes data validation, reliable processing, persistence, traceability, reproducibility, and testability.
