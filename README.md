# Call Log Analyzer

A command-line tool to analyze SignalWire call log data from CSV files. It filters call records for a specific user, processes them, and generates a summary and detailed report in an Excel spreadsheet.

## Features

- Filters inbound calls for a specific user.
- Filters calls based on a minimum duration threshold.
- Identifies PBX systems from their unique IDs in the logs.
- Generates a multi-sheet Excel report (`summary` and `detail`).
- Automatically adjusts column widths in the output file for readability.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```
    source .venv/bin/activate
    ```

2.  **Install the package and its dependencies:**
    ```bash
    pip install .
    ```
    For development, you can install in editable mode with development dependencies:
    ```bash
    pip install -e ".[dev]"
    ```

## Usage

Run the script from the command line, providing the user identifier, one or more CSV file paths (glob patterns are supported), and an output file path.

### Syntax

```bash
call-log-analyzer <user> <csv_files...> -o <output_file.xlsx> [--debug]
```

### Arguments

-   `user`: (Required) The user identifier to filter for (e.g., `some_user`).
-   `csv_files`: (Required) One or more paths to input CSV files. Supports glob patterns (e.g., `data/*.csv`).
-   `-o, --output`: (Required) The path for the generated Excel report (e.g., `reports/analysis.xlsx`).
-   `--debug`: (Optional) Enable verbose debug logging.

### Example

```bash
call-log-analyzer some_user "path/to/logs/*.csv" -o analysis.xlsx
```

This command will:
1.  Process all `.csv` files in the `path/to/logs/` directory.
2.  Filter for all inbound calls involving the user `some_user` that meet the duration threshold.
3.  Generate an Excel file named `analysis.xlsx` with `summary` and `detail` sheets.
