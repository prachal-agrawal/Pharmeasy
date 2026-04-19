"""
One-time migration: back-fill order_prescriptions from legacy prescription_url data.

Legacy formats handled
----------------------
1. Plain URL  → e.g.  "/uploads/rx_1_1700000000.jpg"   (already handled by SQL migration)
2. JSON array → e.g.  '["/uploads/rx_1_1700000001.jpg", "/uploads/rx_1_1700000002.jpg"]'

Run this script AFTER executing migration 004_order_prescriptions.sql:

    cd backend
    python migrate_rx_data.py

The script is fully idempotent (INSERT IGNORE).
"""

import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Back-fill order_prescriptions rows from legacy JSON-array prescription_url values.

    Returns:
        Exit code: 0 on success, 1 if any errors occurred.
    """
    from database import DB  # noqa: PLC0415 – lazy import; DB pool starts here

    with DB() as db:
        # Fetch orders that still have a JSON-array or quoted-string in prescription_url
        rows = db.fetchall(
            """SELECT id, prescription_url, created_at
               FROM orders
               WHERE prescription_url IS NOT NULL
                 AND TRIM(prescription_url) != ''
                 AND (
                       LEFT(TRIM(prescription_url), 1) = '['
                    OR LEFT(TRIM(prescription_url), 1) = '"'
                 )"""
        )

    if not rows:
        logger.info("No JSON-array prescription_url rows found — nothing to migrate.")
        return 0

    logger.info("Found %d order(s) with JSON prescription_url to migrate.", len(rows))

    inserted = skipped = errors = 0

    for row in rows:
        order_id = row["id"]
        raw      = row["prescription_url"]

        try:
            parsed = json.loads(raw)

            # Normalise: could be a single quoted string or a list
            if isinstance(parsed, str):
                urls: list[str] = [parsed]
            elif isinstance(parsed, list):
                urls = [str(u) for u in parsed if u]
            else:
                logger.warning("Order %d: unexpected JSON type %s — skipping", order_id, type(parsed))
                skipped += 1
                continue

            with DB() as db:
                for url in urls:
                    url = url.strip()
                    if not url:
                        continue
                    db.execute(
                        """INSERT IGNORE INTO order_prescriptions (order_id, url, created_at)
                           VALUES (%s, %s, %s)""",
                        (order_id, url, row["created_at"]),
                    )
                    inserted += 1

            logger.info(
                "Order %d → migrated %d prescription URL(s).", order_id, len(urls)
            )

        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("Order %d: failed to parse '%s': %s", order_id, raw[:60], exc)
            errors += 1

    print("\n" + "=" * 50)
    print("  Prescription Migration Summary")
    print("=" * 50)
    print(f"  Inserted : {inserted}")
    print(f"  Skipped  : {skipped}  (already in table or unrecognised)")
    print(f"  Errors   : {errors}")
    print("=" * 50 + "\n")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
