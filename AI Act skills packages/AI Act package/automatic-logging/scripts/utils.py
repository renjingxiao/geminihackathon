"""
Utility functions for Article 12 Logging System.
"""
import csv
import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import pandas as pd

# Paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR.parent / "Output"  # Internal CSVs stay here

# Final outputs go to main project Output folder
FINAL_OUTPUT_DIR = BASE_DIR.parent.parent.parent.parent / "Output"

# CSV file paths (internal working files)
OPERATIONAL_CSV = OUTPUT_DIR / "operational_logs.csv"
RISK_CSV = OUTPUT_DIR / "risk_logs.csv"
CAPABILITY_CSV = OUTPUT_DIR / "capability_checklist.csv"
BIOMETRIC_CSV = OUTPUT_DIR / "biometric_specifics.csv"

# Final consolidated outputs (go to main Output folder)
OUTPUT_EXCEL = FINAL_OUTPUT_DIR / "Record_Keeping_Logging_Art12.xlsx"
REPORT_PATH = FINAL_OUTPUT_DIR / "Record_Keeping_Logging_Art12_Report.md"

# CSV Headers matching templates
OPERATIONAL_HEADERS = [
    "Log ID", "Timestamp (Start)", "Timestamp (End)", 
    "Event Type (Normal Operation)", "System Version", 
    "Input Data Reference/Hash", "Output Hash"
]

RISK_HEADERS = [
    "Log ID", "Timestamp", "Event Type (Risk/Incident/Modification)",
    "Risk Category (Art 79)", "Description of Event",
    "Automated Alert Generated?", "Action Taken"
]

CAPABILITY_HEADERS = [
    "Requirement", "Description", "Status (Compliant/Not Compliant)",
    "Implementation Details"
]

BIOMETRIC_HEADERS = [
    "Requirement (Annex III 1(a))", "Log Field Name", 
    "Data Format", "Retention Period (>6 Months)"
]


def generate_uuid() -> str:
    """Generate a unique log ID."""
    return str(uuid.uuid4())


def hash_text(text: str) -> str:
    """SHA-256 hash for privacy-preserving logging."""
    if not text:
        return ""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def ensure_output_dir():
    """Create Output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def init_csv(filepath: Path, headers: List[str]):
    """Initialize a CSV file with headers if it doesn't exist."""
    if not filepath.exists():
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)


def ensure_csvs_initialized():
    """Ensure all CSV files exist with proper headers."""
    ensure_output_dir()
    init_csv(OPERATIONAL_CSV, OPERATIONAL_HEADERS)
    init_csv(RISK_CSV, RISK_HEADERS)
    init_csv(CAPABILITY_CSV, CAPABILITY_HEADERS)
    init_csv(BIOMETRIC_CSV, BIOMETRIC_HEADERS)


def append_to_csv(filepath: Path, row: List[Any]):
    """Append a row to a CSV file."""
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(row)


def read_csv_as_df(filepath: Path) -> pd.DataFrame:
    """Read a CSV file as a pandas DataFrame."""
    if filepath.exists():
        return pd.read_csv(filepath)
    return pd.DataFrame()


def consolidate_to_excel():
    """
    Consolidate all CSVs into a single Excel workbook.
    Matches the template structure: Record_Keeping_Logging_Art12.xlsx
    """
    ensure_output_dir()
    FINAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create workbook
    wb = openpyxl.Workbook()
    
    # Sheet mappings: (sheet_name, csv_path, headers)
    sheets = [
        ("1. Capability Checklist", CAPABILITY_CSV, CAPABILITY_HEADERS),
        ("2. Operational Logs", OPERATIONAL_CSV, OPERATIONAL_HEADERS),
        ("3. Risk & Incident Logs", RISK_CSV, RISK_HEADERS),
        ("4. Biometric Specifics", BIOMETRIC_CSV, BIOMETRIC_HEADERS),
    ]
    
    # Remove default sheet
    default_sheet = wb.active
    
    for sheet_name, csv_path, headers in sheets:
        ws = wb.create_sheet(title=sheet_name)
        
        # Write headers
        ws.append(headers)
        
        # Write data if CSV exists
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                ws.append(row.tolist())
    
    # Remove default empty sheet
    if default_sheet.title == "Sheet":
        wb.remove(default_sheet)
    
    # Save
    wb.save(OUTPUT_EXCEL)
    return OUTPUT_EXCEL


def get_recent_logs(csv_path: Path, n: int = 50) -> List[Dict]:
    """Get the last N rows from a CSV as list of dicts."""
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)
    return df.tail(n).to_dict('records')


def format_timestamp(dt: datetime) -> str:
    """Format datetime for CSV storage."""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")
