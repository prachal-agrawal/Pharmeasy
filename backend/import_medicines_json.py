"""
CLI script — import pre-scraped medicines from medicines_with_mrp.json into the DB.

Usage
-----
    # From the backend/ directory:
    python import_medicines_json.py
    python import_medicines_json.py --file medicines_with_mrp.json
    python import_medicines_json.py --file /path/to/custom.json

The script is fully idempotent: medicines that already exist (matched by
name or salt composition) are silently skipped.

All content fields (uses, side_effects, product_introduction) are
rewritten through the copyright-safe paraphrase layer before insertion.
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_JSON = Path(__file__).with_name("medicines_with_mrp.json")


def main() -> int:
    """Entry point for the import CLI.

    Returns:
        Exit code: 0 on success, 1 if any errors occurred.
    """
    parser = argparse.ArgumentParser(
        description="Import scraped medicines from a JSON file into the MathuraPharmeasy database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file",
        default=str(DEFAULT_JSON),
        help=f"Path to the JSON file (default: {DEFAULT_JSON})",
    )
    args = parser.parse_args()

    json_path = Path(args.file)
    if not json_path.exists():
        logger.error("JSON file not found: %s", json_path)
        return 1

    logger.info("Starting import from: %s", json_path)

    # Import here so the DB pool is only initialised when running the script
    from scraper_service import import_from_json  # noqa: PLC0415

    stats = import_from_json(json_path)

    print("\n" + "=" * 50)
    print("  Import Summary")
    print("=" * 50)
    print(f"  Inserted : {stats['inserted']}")
    print(f"  Skipped  : {stats['skipped']}  (already in DB)")
    print(f"  Errors   : {stats['errors']}")
    print("=" * 50 + "\n")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
