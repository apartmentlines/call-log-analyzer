import sys
import argparse
import logging
import glob
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import cast

import pandas as pd

from .logger import Logger
from . import constants


class CallLogAnalyzer:
    """Class for analyzing call logs."""

    PBX_ID_PATTERN: re.Pattern[str] = re.compile(r"^[a-f0-9]{32}$")

    def __init__(
        self,
        user: str,
        csv_files: list[str],
        output_file: Path,
        debug: bool = False,
    ) -> None:
        """Initialize the CallLogAnalyzer.

        :param user: User identifier to filter logs by.
        :param csv_files: List of glob patterns for input CSV files.
        :param output_file: Path to the output Excel file.
        :param debug: Enable debug logging.
        """
        self.user: str = user
        self.csv_files: list[str] = csv_files
        self.output_file: Path = output_file
        self.log: logging.Logger = Logger(self.__class__.__name__, debug=debug)

    def analyze(self) -> None:
        """
        Load, filter, and analyze call logs, then write results to an Excel file.
        """
        self.log.info("Starting call log analysis...")
        df = self._load_and_combine_csvs()
        if df.empty:
            self.log.warning("No data loaded from CSV files. Exiting.")
            return

        filtered_df = self._filter_data(df)
        if filtered_df.empty:
            self.log.info("No calls matched the specified criteria.")
            return

        summary_df = self._generate_summary_sheet(filtered_df)
        detail_df = self._generate_detail_sheet(filtered_df)
        self._write_to_excel(summary_df, detail_df)

        self.log.info(f"Analysis complete. Results saved to {self.output_file}")

    def _load_and_combine_csvs(self) -> pd.DataFrame:
        """
        Load data from multiple CSV files specified by glob patterns.

        :return: A single pandas DataFrame containing combined data from all CSVs.
        :rtype: pd.DataFrame
        """
        all_files: list[str] = []
        for pattern in self.csv_files:
            all_files.extend(glob.glob(pattern))

        if not all_files:
            self.log.warning("No CSV files found for the given patterns.")
            return pd.DataFrame()

        self.log.debug(f"Found {len(all_files)} files to process.")
        df_list = [pd.read_csv(f) for f in all_files]
        return pd.concat(df_list, ignore_index=True)

    def _filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the DataFrame based on direction, user, and duration.

        :param df: The input DataFrame to filter.
        :type df: pd.DataFrame
        :return: The filtered DataFrame.
        :rtype: pd.DataFrame
        """
        self.log.debug(f"Applying filters, initial rows: {len(df)}")
        df_filtered = df[df["Direction"] == "Inbound"].copy()
        self.log.debug(f"{len(df_filtered)} rows after 'Inbound' filter.")

        df_filtered = df_filtered[
            (df_filtered["To"] == self.user) | (df_filtered["From"] == self.user)
        ].copy()
        self.log.debug(f"{len(df_filtered)} rows after user filter for '{self.user}'.")

        df_filtered = df_filtered[
            df_filtered["Duration (in seconds)"]
            >= constants.ACTIVE_CALL_SECONDS_THRESHOLD
        ].copy()
        self.log.debug(
            f"{len(df_filtered)} rows after duration filter (>={constants.ACTIVE_CALL_SECONDS_THRESHOLD}s)."
        )

        return cast(pd.DataFrame, df_filtered)

    def _get_display_name(self, identifier: str) -> str:
        """
        Return 'PBX' if the identifier matches the PBX ID pattern,
        otherwise return the original identifier.

        :param identifier: The identifier string to check.
        :type identifier: str
        :return: 'PBX' or the original identifier.
        :rtype: str
        """
        if self.PBX_ID_PATTERN.match(identifier):
            return "PBX"
        return str(identifier)

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        """
        Convert total seconds into a human-readable H/M/S string.

        :param total_seconds: The duration in seconds.
        :type total_seconds: int
        :return: A formatted string (e.g., '1h 5m 30s').
        :rtype: str
        """
        if pd.isna(total_seconds):
            return "0s"
        total_seconds = int(total_seconds)
        if total_seconds == 0:
            return "0s"

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def _generate_summary_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate a summary DataFrame from the filtered call data.

        :param df: The filtered DataFrame.
        :type df: pd.DataFrame
        :return: A DataFrame containing summary metrics.
        :rtype: pd.DataFrame
        """
        calls_to_user = df[df["To"] == self.user]
        calls_from_user = df[df["From"] == self.user]

        total_calls = len(df)
        total_calls_to = len(calls_to_user)
        total_calls_from = len(calls_from_user)
        total_duration_seconds = df["Duration (in seconds)"].sum()

        avg_duration_to = (
            calls_to_user["Duration (in seconds)"].mean() if total_calls_to > 0 else 0.0
        )
        avg_duration_from = (
            calls_from_user["Duration (in seconds)"].mean()
            if total_calls_from > 0
            else 0.0
        )
        avg_duration_all = (
            df["Duration (in seconds)"].mean() if total_calls > 0 else 0.0
        )

        summary_data = {
            "Metric": [
                "Total Calls",
                "Total Calls To User",
                "Total Calls From User",
                "Total Time Spent",
                "Avg Call Time (To User)",
                "Avg Call Time (From User)",
                "Avg Call Time (All)",
            ],
            "Value": [
                total_calls,
                total_calls_to,
                total_calls_from,
                self._format_duration(total_duration_seconds),
                self._format_duration(int(avg_duration_to)),
                self._format_duration(int(avg_duration_from)),
                self._format_duration(int(avg_duration_all)),
            ],
        }
        return pd.DataFrame(summary_data)

    def _generate_detail_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate a detailed DataFrame from filtered data for export.

        :param df: The filtered DataFrame.
        :type df: pd.DataFrame
        :return: A formatted DataFrame with detailed call information.
        :rtype: pd.DataFrame
        """
        detail_df = df.copy()

        detail_df["Created at"] = pd.to_datetime(detail_df["Created at"], utc=True)
        target_tz = ZoneInfo(constants.TARGET_TIMEZONE)
        detail_df = detail_df.sort_values(by="Created at").reset_index(drop=True)

        def get_interaction(row: pd.Series) -> str:
            if row["To"] == self.user:
                from_party = self._get_display_name(str(row["From"]))
                return f"call from {from_party}"

            return f"call to {row["To"]}"

        detail_df["Interaction"] = detail_df.apply(get_interaction, axis=1)
        detail_df["Duration (Readable)"] = detail_df["Duration (in seconds)"].apply(
            self._format_duration
        )
        detail_df["Call Time (US/Central)"] = (
            detail_df["Created at"]
            .dt.tz_convert(target_tz)
            .dt.strftime("%Y-%m-%d %H:%M:%S")
        )

        detail_df = detail_df.rename(
            columns={"Duration (in seconds)": "Duration (Seconds)"}
        )

        return cast(
            pd.DataFrame,
            detail_df[
                [
                    "Call Time (US/Central)",
                    "Interaction",
                    "Duration (Readable)",
                    "Duration (Seconds)",
                ]
            ],
        )

    def _write_to_excel(
        self, summary_df: pd.DataFrame, detail_df: pd.DataFrame
    ) -> None:
        """
        Write summary and detail DataFrames to a single Excel file.

        :param summary_df: The summary DataFrame.
        :type summary_df: pd.DataFrame
        :param detail_df: The detail DataFrame.
        :type detail_df: pd.DataFrame
        """
        with pd.ExcelWriter(self.output_file, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="summary", index=False)
            detail_df.to_excel(writer, sheet_name="detail", index=False)

            for sheet in writer.sheets.values():
                for column_cells in sheet.columns:
                    new_column_length = max(
                        len(str(cell.value)) for cell in column_cells
                    )
                    new_column_letter = column_cells[0].column_letter
                    if new_column_length > 0:
                        sheet.column_dimensions[
                            new_column_letter
                        ].width = new_column_length * 1.2

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    :return: Namespace containing parsed arguments
    """
    parser = argparse.ArgumentParser(description="Analyze Signalwire call logs")
    parser.add_argument("user", help="User identifier to filter logs by.")
    parser.add_argument(
        "csv_files",
        nargs="+",
        help="One or more CSV file paths to analyze (glob patterns supported).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path to the output Excel file.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main() -> None:
    """Main entry point for call log analyzer script."""
    args = parse_arguments()
    try:
        analyzer = CallLogAnalyzer(
            user=args.user,
            csv_files=args.csv_files,
            output_file=args.output,
            debug=args.debug,
        )
        analyzer.analyze()
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
