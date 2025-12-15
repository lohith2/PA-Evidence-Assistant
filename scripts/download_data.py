#!/usr/bin/env python3
"""
Automated data pipeline — downloads and ingests all sources into Pinecone.
Run inside the backend container: python scripts/download_data.py --all
"""

import sys
import asyncio
from pathlib import Path

# Add backend to path when run from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from ingestion.ingest import main

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Download and ingest all sources")
    parser.add_argument("--source", default="ALL")
    args = parser.parse_args()

    source = "ALL" if args.all else args.source
    asyncio.run(main(source))
