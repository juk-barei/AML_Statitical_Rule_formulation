"""
This is for loading the transformed data to cloud to share with other members. Credential will be provided in .env. 
It will be similar style to ingest.py, a commend driven module for cmd options customization.
"""
import argparse

# ==============DEFAULT======================
EXPORT_EXTENSION = ".parquet"


def parse_args() -> argparse.Namespace:
    """Parse export arguments; the export implementation is pending."""
    return argparse.ArgumentParser(description=__doc__).parse_args()

