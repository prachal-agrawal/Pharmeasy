"""
Scraper service — on-demand medicine data fetching and DB insertion.

Responsibilities
----------------
1. **Content rewriting**: All text scraped from 1mg is paraphrased
   before storage so no copyrighted prose is stored verbatim.
2. **Category inference**: Maps medicine names/salts to one of the
   local DB categories using keyword matching.
3. **DB insertion**: Upsert-safe insert of a scraped medicine with its
   variants.  15% flat discount is applied to all MRPs.
4. **On-demand pipeline**: ``fetch_and_insert(name)`` — single async
   entry-point used by the API to scrape one medicine and insert it.
5. **Bulk import**: ``import_from_json(path)`` — used by the CLI import
   script to load the pre-scraped JSON file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests

from config import get_settings
from database import DB

_settings = get_settings()
from medicine_scraper_with_mrp import (
    _DETAIL_UA,
    _SEARCH_UA,
    get_details,
    resolve_1mg_product_url,
    search_1mg_first_product_url,
    search_medicine,
    search_medicines_all,
)

logger = logging.getLogger(__name__)

# 15 % flat discount applied on every MRP
FLAT_DISCOUNT: float = 0.15


def _detail_session() -> requests.Session:
    """Build a :class:`requests.Session` suitable for 1mg detail-page GETs.

    Returns:
        Session with ``User-Agent`` and accept headers matching
        :func:`medicine_scraper_with_mrp.get_details` expectations.
    """
    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": _DETAIL_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return sess

# Default safety & warning text reused for all auto-inserted medicines
_DEFAULT_SAFETY_POINTS: list[str] = [
    "Follow prescribed dosage schedule",
    "Store in a cool, dry place away from direct sunlight",
    "Keep out of reach of children",
    "Do not use beyond the expiry date printed on the pack",
]

_DEFAULT_WARNING: str = (
    "Keep out of reach of children. "
    "Always consult a qualified healthcare professional before use. "
    "Stop use and seek medical advice if adverse reactions occur."
)

# ---------------------------------------------------------------------------
# Category keyword mapping
# Order matters — first match wins.
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: list[tuple[list[str], str]] = [
    (
        [
            "antibiotic", "bacterial", "infection", "amoxicillin",
            "azithromycin", "cefixime", "cefpodoxime", "doxycycline",
            "ciprofloxacin", "metronidazole", "clindamycin", "levofloxacin",
        ],
        "antibiotics",
    ),
    (
        [
            "allergy", "cetirizine", "loratadine", "fexofenadine",
            "levocetirizine", "antihistamine", "rhinitis", "urticaria",
            "montelukast",
        ],
        "allergy",
    ),
    (
        [
            "gastro", "pantoprazole", "omeprazole", "rabeprazole",
            "esomeprazole", "acidity", "ulcer", "gerd", "reflux",
            "antacid", "domperidone", "metoclopramide", "ondansetron",
            "pantop", "nausea", "vomiting",
        ],
        "gastro",
    ),
    (
        [
            "diabetes", "metformin", "insulin", "glipizide", "sitagliptin",
            "vildagliptin", "gliclazide", "dapagliflozin", "blood sugar",
            "gluconorm", "glycomet", "galvus",
        ],
        "diabetes",
    ),
    (
        [
            "cardiac", "heart", "hypertension", "blood pressure",
            "amlodipine", "atenolol", "telmisartan", "losartan",
            "ramipril", "atorvastatin", "rosuvastatin", "clopidogrel",
            "cholesterol", "telma", "rosuvas", "deplatt",
        ],
        "cardiac",
    ),
    (
        [
            "vitamin", "supplement", "calcium", "zinc", "iron",
            "b12", "folic", "omega", "mineral", "multivitamin",
            "calcirol", "uprise", "cholecalciferol",
        ],
        "supplements",
    ),
    (
        [
            "gel", "spray", "cream", "ointment", "lotion",
            "topical", "diclofenac gel", "omnigel",
            "moov", "volini", "iodex", "relispray", "burnol",
        ],
        "gels-sprays",
    ),
    (
        [
            "pain", "nise", "ibuprofen", "paracetamol", "diclofenac",
            "aspirin", "analgesic", "anti-inflammatory", "nsaid",
            "tramadol", "nimesulide",
        ],
        "pain-relief",
    ),
]


def _infer_category_slug(name: str, salt: str, uses: str) -> str:
    """Infer the best-matching category slug from medicine attributes.

    Args:
        name: Medicine name (e.g. ``"Telma 40 Tablet"``).
        salt: Salt composition string (e.g. ``"Telmisartan (40mg)"``).
        uses: Uses text.

    Returns:
        Category slug such as ``"cardiac"`` or ``"pain-relief"``.
    """
    combined = f"{name} {salt} {uses}".lower()
    for keywords, slug in _CATEGORY_KEYWORDS:
        if any(kw in combined for kw in keywords):
            return slug
    return "pain-relief"  # safe fallback


def _get_category_id(slug: str) -> int:
    """Resolve a category slug to its database primary key.

    Args:
        slug: URL slug of the category (e.g. ``"gastro"``).

    Returns:
        Integer category ID from the DB (falls back to first category).
    """
    with DB() as db:
        row = db.fetchone("SELECT id FROM categories WHERE slug=%s", (slug,))
        if row:
            return int(row["id"])
        fallback = db.fetchone("SELECT id FROM categories ORDER BY sort_order LIMIT 1")
        return int(fallback["id"]) if fallback else 1


# ---------------------------------------------------------------------------
# Content rewriting (copyright-free paraphrase)
# ---------------------------------------------------------------------------

def _extract_conditions(uses_text: str) -> list[str]:
    """Extract individual medical conditions from a raw uses string.

    Handles two formats produced by 1mg's ``productUses`` field:

    1. **Label-description format** (modern pages):
       ``"Pain relief : <desc>. Treatment of Fever : <desc>."``
       — The condition name precedes each `` : `` separator; descriptions
       follow it.  Splitting on `` : `` yields chunks where the first chunk
       is the first condition and each subsequent chunk ends with the next
       condition name (after the description sentence).

    2. **Run-together format** (older pages):
       ``"Treatment of Hypertension Heart Failure"``
       — Conditions are capitalized words run together without separators.

    Args:
        uses_text: Raw uses text scraped from 1mg (HTML already stripped).

    Returns:
        List of condition strings (max 6).
    """
    text = uses_text.strip()

    # ── Format 1: "ConditionName : description ConditionName2 : description2" ──
    # Split on " : " to separate label from description pairs.
    # chunks = ["Pain relief", "desc... Treatment of Fever", "desc..."]
    if " : " in text:
        chunks = text.split(" : ")
        conditions: list[str] = []
        # First chunk is always the first condition name (nothing before it)
        first_cond = chunks[0].strip().strip(".,;()")
        if len(first_cond) > 3:
            conditions.append(first_cond)
        # Each middle chunk = description of previous condition + next condition name.
        # The next condition name follows the last ". " sentence boundary.
        for chunk in chunks[1:-1]:
            parts = re.split(r"\.\s+", chunk.strip())
            cand = parts[-1].strip().strip(".,;()")  # last fragment = next condition
            if len(cand) > 3:
                conditions.append(cand)
        return conditions[:6]

    # ── Format 2: run-together conditions (remove action-verb prefixes first) ──
    text = re.sub(
        r"(Treatment|Prevention|Management|Indicated|Used)\s+of\s*|"
        r"\w+ \d+ Tablet helps? (treat|manage|prevent|control)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Truncate at first colon (e.g. "Bacterial infections : full desc only 1 item")
    if ":" in text:
        text = text.split(":")[0]
    # Split at lowercase→uppercase boundary (run-together conditions)
    text = re.sub(r"(?<=[a-z\)]) (?=[A-Z])", "|", text)
    parts = [p.strip().strip(".,;()") for p in text.split("|") if p.strip()]
    return [p for p in parts if len(p) > 3][:6]


def rewrite_uses(uses_text: str) -> str:
    """Rewrite the uses / indications text in original language.

    Extracts the core medical conditions and reformulates them using
    neutral clinical phrasing to avoid direct copying of 1mg content.

    Args:
        uses_text: Raw uses text scraped from 1mg.

    Returns:
        Clean, original uses sentence for storage in the database.

    Example:
        >>> rewrite_uses("Treatment of Hypertension (high blood pressure) Heart Failure")
        'Used for: hypertension (high blood pressure); heart failure'
    """
    if not uses_text:
        return ""
    conditions = _extract_conditions(uses_text)
    if not conditions:
        # Fallback: trim whitespace on the raw text
        return re.sub(r"\s+", " ", uses_text[:300]).strip()
    return "Used for: " + "; ".join(c.lower() for c in conditions)


def _extract_side_effect_names(se_text: str) -> list[str]:
    """Extract individual side-effect names from the scraped block.

    1mg's side-effects text follows a predictable pattern:
    ``"… Common side effects of <MedicineName> Effect1 Effect2 Effect3"``
    The effect names are capitalized phrases separated by spaces.

    Args:
        se_text: Full side-effects paragraph from scraper.

    Returns:
        List of raw effect name strings (max 10).
    """
    # Locate the capitalized effects list after the standard disclaimer
    match = re.search(
        r"Common side effects of\s+[\w\d]+(?:\s+[\d]+)?\s+",
        se_text,
        re.IGNORECASE,
    )
    if match:
        effects_text = se_text[match.end():]
    else:
        # No standard header — use the full text
        effects_text = se_text

    # Split at lowercase→uppercase boundary to separate run-together effects
    effects = re.split(r"(?<=[a-z]) (?=[A-Z])", effects_text)
    results: list[str] = []
    skip_words = {"most", "consult", "common", "disappear", "medical", "your", "they"}
    for e in effects:
        e = e.strip().strip(".,;")
        if 3 < len(e) < 60 and e.split()[0].lower() not in skip_words:
            results.append(e)
    return results[:10]


def rewrite_side_effects(se_text: str) -> list[str]:
    """Rewrite side effects as a copyright-free list.

    Extracts the symptom names and prefixes each with a standard medical
    phrase so no sentence is a verbatim copy of the source.

    Args:
        se_text: Raw side-effects paragraph scraped from 1mg.

    Returns:
        List of rewritten side-effect strings suitable for the DB
        ``side_effects`` JSON column.

    Example:
        >>> rewrite_side_effects("... Common side effects of X Nausea Headache Diarrhea")
        ['May cause nausea', 'Possible headache', 'Reported diarrhea']
    """
    names = _extract_side_effect_names(se_text)
    prefixes = ["May cause", "Possible", "Reported", "Can cause", "Some patients report", "Occasional"]
    rewritten: list[str] = []
    for i, name in enumerate(names):
        rewritten.append(f"{prefixes[i % len(prefixes)]} {name.lower()}")
    return rewritten or ["Consult your doctor if you notice any unusual symptoms"]


_SYNONYM_MAP: dict[str, str] = {
    # Light synonym substitutions to produce original phrasing while keeping
    # the same clinical meaning.  Applied word-by-word after sentence splitting.
    "helps relieve":   "provides relief from",
    "helps reduce":    "helps lower",
    "helps treat":     "is used to treat",
    "works by":        "acts by",
    "It works":        "It acts",
    "commonly":        "frequently",
    "It is used to treat": "It is indicated for",
    "It is used for":  "It is indicated for",
    "It is used in":   "It is indicated in",
    "is used to treat":"is indicated for",
    "is used for":     "is indicated for",
    "is widely prescribed": "is commonly recommended",
    "adverse effects": "unwanted effects",
    "side effects":    "unwanted effects",
    "not suitable":    "not appropriate",
}

_PROMO_KW = re.compile(r"\b(1mg|tata|pharmeasy|netmeds|apollo|buy now)\b", re.I)


def _apply_synonyms(text: str) -> str:
    """Apply light synonym substitutions for copyright-safe paraphrasing.

    Args:
        text: A single sentence of plain text.

    Returns:
        The sentence with a small number of phrases replaced by synonyms.
    """
    for phrase, replacement in _SYNONYM_MAP.items():
        text = re.sub(re.escape(phrase), replacement, text, flags=re.IGNORECASE)
    return text


def rewrite_introduction(intro_text: str) -> str:
    """Rewrite the product introduction in original language.

    Preserves the full product description — mechanism of action first,
    followed by usage/dosing/safety paragraphs — while applying light
    synonym substitutions so the stored text is an original paraphrase
    rather than a verbatim copy of the source.

    Structure of ``intro_text`` (after scraper ordering fix):
      1. ``howWorks`` content   → mechanism sentence ("It acts by …")
      2. ``productIntroduction``→ dosing, side-effect and safety paragraphs

    Args:
        intro_text: Raw product-introduction HTML-stripped text (plain text,
                    no HTML tags).

    Returns:
        Paraphrased description string preserving all meaningful sentences
        (up to ~6), or an empty string if the input is empty.

    Example:
        >>> rewrite_introduction("It works by blocking pain signals. "
        ...                      "You should take it with food.")
        'It acts by blocking pain signals. You should take it with food.'
    """
    if not intro_text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", intro_text.strip())
    kept: list[str] = []

    for s in sentences:
        s = s.strip()
        # Skip very short fragments and promotional brand mentions
        if len(s) < 20 or _PROMO_KW.search(s):
            continue
        kept.append(_apply_synonyms(s))
        if len(kept) >= 6:
            break

    if not kept:
        # Ultimate fallback: first two non-trivial sentences verbatim
        kept = [s.strip() for s in sentences[:4] if len(s.strip()) > 30][:2]

    return " ".join(kept)


# ---------------------------------------------------------------------------
# Variant helpers
# ---------------------------------------------------------------------------

def _parse_count_from_label(label: str) -> int:
    """Extract the numeric unit count embedded in a variant label.

    Args:
        label: e.g. ``"30 tablets"``, ``"10 tablets"``, ``"15 ml"``.

    Returns:
        Integer count; defaults to ``10`` if no number is found.
    """
    m = re.search(r"(\d+)", label)
    return int(m.group(1)) if m else 10


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def medicine_exists(name: str, salt: str, brand: str = "") -> Optional[int]:
    """Return the DB id of an existing medicine matching name AND brand.

    Two medicines are considered duplicates only when **both** their name and
    brand (manufacturer) match — case-insensitively.  This prevents medicines
    that share the same salt (e.g. Dolo 650 and Calpol 650 are both
    Paracetamol 650 mg) from being incorrectly treated as the same product.

    Match priority:
    1. Exact name match                           (always checked)
    2. Exact name  AND  exact brand match         (when brand is provided)

    The former salt-only OR condition has been removed because it caused
    false positives: any two paracetamol brands would collide on salt alone.

    Args:
        name:  Medicine name as returned by the scraper.
        salt:  Salt / active-ingredient string (kept for API compatibility,
               no longer used as a match criterion).
        brand: Manufacturer / brand name (optional).  When provided, a
               (name, brand) pair must match for a hit.

    Returns:
        Existing medicine ID or ``None`` if not found.
    """
    with DB() as db:
        if brand:
            row = db.fetchone(
                """SELECT id FROM medicines
                   WHERE LOWER(name) = LOWER(%s)
                      OR (LOWER(name)  = LOWER(%s)
                          AND LOWER(brand) = LOWER(%s))
                   LIMIT 1""",
                (name, name, brand),
            )
        else:
            row = db.fetchone(
                "SELECT id FROM medicines WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                (name,),
            )
        return int(row["id"]) if row else None


# ---------------------------------------------------------------------------
# Alternate-brand helpers
# ---------------------------------------------------------------------------

def insert_alternate_brands(
    source_med_id: int,
    source_salt: str,
    source_category_id: int,
    source_uses: str,
    source_side_effects: list[str],
    source_safety_pts: str,
    source_warning: str,
    primary_count: int,
    alt_brands: list[dict],
    http_session: Optional[requests.Session] = None,
    source_primary_variant_label: str = "",
    source_medicine_name: str = "",
) -> int:
    """Insert alternate-brand medicines and create medicine_alternatives mappings.

    For each entry in *alt_brands* (from the scraper's ``alternate_brands``
    field):

    1. If a medicine with the same display name already exists, only the
       mapping row is created.
    2. Otherwise, resolve a 1mg product URL with :func:`resolve_1mg_product_url`
       (API fields and nested ``action``/``cta`` links). If still missing,
       :func:`search_1mg_first_product_url` loads the search HTML and takes the
       first ``/drugs/`` or ``/otc/`` link (same SSR approach as detail pages).
    3. **Fetch that substitute's own detail page** with :func:`get_details` and
       insert via :func:`insert_scraped_medicine` (correct variants and MRP).
       Nested alternate lists are not expanded (``skip_alternate_brands=True``).
    4. If no URL can be resolved or detail scrape/insert fails, the alternative
       is skipped. There is no list-price fallback: multiplying per-unit list
       prices by the source pack size produced wrong totals (e.g. ₹89 → ₹890).

    Args:
        source_med_id: DB primary key of the source (branded) medicine.
        source_salt: Salt composition shared by all alternatives.
        source_category_id: Category ID override for full detail inserts.
        source_uses: Rewritten uses text (passed through for API compatibility).
        source_side_effects: Rewritten side-effect list.
        source_safety_pts: JSON-serialised safety-points list.
        source_warning: Warning text string.
        primary_count: Unused; retained for call-site compatibility.
        alt_brands: List of dicts from the scraper (``name``, ``url``,
            ``manufacturer``, ``price_per_unit``, ``image_url``, …).
        http_session: Session for :func:`get_details` and search fallback.
        source_primary_variant_label: Unused; retained for call-site compatibility.
        source_medicine_name: Unused; retained for call-site compatibility.

    Returns:
        Number of ``medicine_alternatives`` mappings created or refreshed.
    """
    sess = http_session or _detail_session()
    count = 0
    for ab in alt_brands:
        name = (ab.get("name") or "").strip()
        if not name:
            continue
        detail_url = resolve_1mg_product_url(ab) if isinstance(ab, dict) else ""
        if not detail_url:
            detail_url = search_1mg_first_product_url(name, sess)

        try:
            with DB() as db:
                row = db.fetchone(
                    "SELECT id FROM medicines WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                    (name,),
                )
                alt_med_id: Optional[int] = int(row["id"]) if row else None

            # New row: load the substitute's own product page (never list-only pricing).
            if alt_med_id is None and detail_url:
                try:
                    detail = get_details(detail_url, sess)
                    dname = (detail.get("name") or detail.get("search_name") or "").strip()
                    if dname:
                        alt_med_id = insert_scraped_medicine(
                            detail,
                            category_id_override=source_category_id,
                            skip_alternate_brands=True,
                            http_session=sess,
                        )
                        logger.info(
                            "Inserted alternative from detail page '%s' → id=%d (%s)",
                            detail_url,
                            alt_med_id,
                            dname,
                        )
                    else:
                        logger.warning(
                            "Alternative page returned no product name, skipping: %s",
                            detail_url,
                        )
                except Exception as exc:
                    logger.warning(
                        "Detail scrape failed for alt '%s' (%s): %s",
                        name,
                        detail_url,
                        exc,
                    )

            if alt_med_id is None:
                logger.warning(
                    "Skipping alternative %r — no insertable detail page "
                    "(resolved_url=%s)",
                    name,
                    detail_url or "",
                )
                continue

            with DB() as db:
                db.execute(
                    """INSERT INTO medicine_alternatives
                       (source_medicine_id, alternative_medicine_id)
                       VALUES (%s,%s)
                       ON DUPLICATE KEY UPDATE is_active=1""",
                    (source_med_id, alt_med_id),
                )
            count += 1

        except Exception as exc:
            logger.warning("Error processing alt brand '%s': %s", name, exc)

    if count:
        logger.info(
            "Created %d alternative mapping(s) for medicine ID=%d",
            count,
            source_med_id,
        )
    return count


def _process_alt_brands(source_id: int, rec: dict) -> None:
    """Derive all alt-brand data from a raw JSON record and insert alternatives.

    Convenience wrapper around :func:`insert_alternate_brands` that handles
    content rewriting and category/variant-count resolution so callers only
    need to pass the raw scraped dict.

    Args:
        source_id: DB primary key of the already-inserted source medicine.
        rec: Raw medicine dict (from the JSON file or scraper output).
    """
    alt_brands = rec.get("alternate_brands") or []
    if not alt_brands:
        return

    salt         = (rec.get("salt") or "").strip()
    uses         = rewrite_uses(rec.get("uses", ""))
    side_effects = rewrite_side_effects(rec.get("side_effects", ""))
    safety_pts   = json.dumps(_DEFAULT_SAFETY_POINTS)
    warning      = _DEFAULT_WARNING

    # Fetch the source medicine's category from DB (it was already inserted)
    with DB() as db:
        row = db.fetchone(
            "SELECT category_id FROM medicines WHERE id=%s", (source_id,)
        )
        cat_id = int(row["category_id"]) if row else _get_category_id("pain-relief")

    # Determine primary pack count from the selected (or first) variant
    all_src_variants = rec.get("variants") or []
    src_product_name = (rec.get("name") or "").strip()
    selected_label = ""
    if all_src_variants:
        selected = next(
            (v for v in all_src_variants if v.get("is_selected")),
            all_src_variants[0],
        )
        selected_label = (selected.get("label") or "").strip()
        primary_count = _parse_count_from_label(selected.get("label", "15")) or 15
    else:
        primary_count = 15

    sess = _detail_session()
    insert_alternate_brands(
        source_med_id=source_id,
        source_salt=salt,
        source_category_id=cat_id,
        source_uses=uses,
        source_side_effects=side_effects,
        source_safety_pts=safety_pts,
        source_warning=warning,
        primary_count=primary_count,
        alt_brands=alt_brands,
        http_session=sess,
        source_primary_variant_label=selected_label,
        source_medicine_name=src_product_name,
    )


# ---------------------------------------------------------------------------
# Image download helper
# ---------------------------------------------------------------------------

def _download_and_save_image(
    image_url: str,
    medicine_id: int,
    session: Optional[requests.Session] = None,
    *,
    index: int = 0,
) -> Optional[str]:
    """Download a product image from a remote URL and save it locally.

    Writes under the configured upload directory. The first image for a
    medicine uses ``med_<medicine_id>.<ext>``; additional gallery images use
    ``med_<medicine_id>_1.<ext>``, ``med_<medicine_id>_2.<ext>``, etc.

    Args:
        image_url: Absolute URL of the image to download (e.g. from 1mg CDN).
        medicine_id: DB primary key of the medicine — used in the filename.
        session: Optional ``requests.Session`` to reuse (creates a new one if
            not provided).
        index: Zero-based slot in the gallery; ``0`` keeps the legacy primary
            filename, ``1+`` adds a numeric suffix so files do not overwrite.

    Returns:
        Local URL path string (``"/uploads/med_<id>.<ext>"`` or suffixed), or
        ``None`` if the download fails.
    """
    if not image_url:
        return None

    try:
        sess = session or requests.Session()
        resp = sess.get(image_url, timeout=15, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        # Derive extension from Content-Type or the URL path
        ext_map = {
            "image/jpeg": ".jpg", "image/jpg": ".jpg",
            "image/png":  ".png", "image/webp": ".webp",
            "image/gif":  ".gif",
        }
        ext = ext_map.get(content_type.split(";")[0].strip(), "")
        if not ext:
            url_ext = os.path.splitext(image_url.split("?")[0])[-1].lower()
            ext = url_ext if url_ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"

        upload_dir = _settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)

        stem = f"med_{medicine_id}" if index == 0 else f"med_{medicine_id}_{index}"
        fname = f"{stem}{ext}"
        fpath = os.path.join(upload_dir, fname)

        with open(fpath, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)

        local_url = f"/uploads/{fname}"
        logger.info("Image saved for medicine ID=%d → %s", medicine_id, local_url)
        return local_url

    except Exception as exc:
        logger.warning("Failed to download image from '%s': %s", image_url, exc)
        return None


def _collect_scrape_image_urls(images: list[dict]) -> list[str]:
    """Collect ordered unique remote URLs for every scraped product image.

    For each asset, prefers ``medium``, then ``thumbnail``, then ``high``.
    Duplicate URLs (same string) are skipped so each file is downloaded once.

    Args:
        images: List of dicts from :func:`medicine_scraper_with_mrp.get_details`
            (keys ``thumbnail``, ``medium``, ``high``).

    Returns:
        Ordered list of absolute URL strings (may be empty).
    """
    seen: set[str] = set()
    out: list[str] = []
    for img in images:
        if not isinstance(img, dict):
            continue
        raw = img.get("medium") or img.get("thumbnail") or img.get("high") or ""
        url = str(raw).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


# ---------------------------------------------------------------------------
# DB insertion
# ---------------------------------------------------------------------------

def insert_scraped_medicine(
    data: dict,
    *,
    category_id_override: Optional[int] = None,
    skip_alternate_brands: bool = False,
    http_session: Optional[requests.Session] = None,
) -> int:
    """Insert one scraped medicine record and its variants into the DB.

    Rewrites all copyright-sensitive fields before saving.
    Applies the configured ``FLAT_DISCOUNT`` to every MRP.

    Args:
        data: Dict produced by :func:`medicine_scraper_with_mrp.get_details`.
            Expected keys: ``name``, ``salt``, ``manufacturer``, ``uses``,
            ``side_effects``, ``product_introduction``, ``mrp``, ``variants``,
            ``search_name``.
        category_id_override: If set, use this category ID instead of inferring
            from name/salt (used when inserting generics from a substitute URL).
        skip_alternate_brands: If True, do not expand nested alternate brands
            (avoids recursion when inserting an alternative from its own page).
        http_session: Passed to :func:`insert_alternate_brands` for fetching
            each substitute's detail page; defaults to a new session when
            alternate brands are present.

    Returns:
        Primary key of the newly inserted medicine row.

    Raises:
        Exception: Propagated from the DB layer on constraint violation.
    """
    name    = (data.get("name")  or data.get("search_name") or "").strip()
    salt    = (data.get("salt")  or "").strip()
    brand   = (data.get("manufacturer") or "").strip()
    is_otc  = bool(data.get("is_otc") or "/otc/" in (data.get("url") or ""))

    # ── OTC content resolution ──────────────────────────────────────────────
    # OTC pages (Moov, Vicks, Burnol, etc.) store usable content in
    # productInformation sections rather than productUses / sideEffect.
    #
    # Priority for each field:
    #   uses        → productUses → Key Benefits
    #   description → productIntroduction → Key Benefits
    #   salt        → scraped salt → Key Ingredients
    #   safety_pts  → scraped Directions + Safety Information → defaults

    uses_raw   = data.get("uses") or data.get("key_benefits") or ""
    desc_raw   = data.get("product_introduction") or data.get("key_benefits") or ""
    salt_final = salt or (data.get("key_ingredients") or "").strip()

    # Rewrite content fields to avoid direct copyright reproduction
    uses         = rewrite_uses(uses_raw)
    side_effects = rewrite_side_effects(data.get("side_effects", ""))
    description  = rewrite_introduction(desc_raw)
    warning      = _DEFAULT_WARNING

    # Build safety_points from scraped Directions + Safety Information when
    # available (OTC products); fall back to the default list otherwise.
    scraped_directions = (data.get("directions_for_use") or "").strip()
    scraped_safety     = (data.get("safety_information")  or "").strip()
    if scraped_directions or scraped_safety:
        pts: list[str] = []
        if scraped_directions:
            pts.append(scraped_directions[:300])
        if scraped_safety:
            # Split on sentence boundaries and keep the most useful ones
            for sentence in re.split(r"[.•·\n]+", scraped_safety):
                s = sentence.strip()
                if len(s) > 10:
                    pts.append(s)
                if len(pts) >= 5:
                    break
        safety_pts = json.dumps(pts or _DEFAULT_SAFETY_POINTS)
    else:
        safety_pts = json.dumps(_DEFAULT_SAFETY_POINTS)

    if category_id_override is not None:
        cat_id = category_id_override
        cat_slug = f"override:{cat_id}"
    else:
        cat_slug = _infer_category_slug(name, salt_final, uses)
        cat_id = _get_category_id(cat_slug)

    # primary_count tracks the selected variant's unit count; used later for
    # pricing alt-brand variants (updated inside the with-block via Python scope).
    primary_count = 15
    source_primary_variant_label = ""

    with DB() as db:
        mid = db.insert(
            """INSERT INTO medicines
               (name, brand, salt_composition, manufacturer, category_id,
                description, uses, side_effects, safety_points, warning,
                requires_rx, is_active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                name, brand, salt_final, brand, cat_id,
                description,
                uses,
                json.dumps(side_effects),
                safety_pts,
                warning,
                0 if is_otc else 1,   # OTC medicines do not require a prescription
                1,
            ),
        )

        # ── Insert variants ──────────────────────────────────────────
        mrp_total    = float(data.get("mrp") or 0)
        variants_raw: list[dict] = data.get("variants") or []

        # Include ALL variants (even unavailable ones — shown as out-of-stock).
        # Only skip entries that have neither a label nor any identifying info.
        all_variants = [v for v in variants_raw if v.get("label") or v.get("is_selected")]

        if all_variants:
            # Determine the base MRP per unit from the selected/first variant.
            # When a variant carries its own MRP (common for OTC packs like
            # "1 Tube of 75 gm Gel") we use that directly; otherwise we scale
            # from the top-level mrp_total ÷ unit count.
            selected      = next((v for v in all_variants if v.get("is_selected")), all_variants[0])
            source_primary_variant_label = (selected.get("label") or "").strip()
            base_count    = _parse_count_from_label(selected.get("label", "30")) or 30
            primary_count = base_count
            per_unit_mrp  = mrp_total / max(base_count, 1)

            for i, v in enumerate(all_variants):
                label = v.get("label") or f"Pack {i + 1}"
                # Unavailable variants are inserted with stock=0 so the UI can
                # show them as "Out of Stock" without hiding them entirely.
                stock = 100 if v.get("is_available", True) else 0

                # Prefer per-variant MRP captured by the scraper (OTC packs
                # always have their own price; Rx tabs use scaled per-unit math).
                if v.get("mrp"):
                    var_mrp = float(v["mrp"])
                else:
                    cnt     = _parse_count_from_label(label)
                    var_mrp = round(per_unit_mrp * cnt, 2) if per_unit_mrp else mrp_total

                price = round(var_mrp * (1 - FLAT_DISCOUNT), 2)
                db.execute(
                    """INSERT INTO medicine_variants
                       (medicine_id, label, mrp, price, stock, sort_order)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (mid, label, var_mrp or mrp_total, price, stock, i),
                )
        elif mrp_total:
            # No variant data at all — create a single fallback variant.
            # Use the product name as the label for OTC items so we never
            # show the generic "Standard Pack" string.
            fallback_label = name if is_otc else "Standard Pack"
            source_primary_variant_label = fallback_label
            logger.warning("No variants scraped for '%s' (id=%d) — inserting '%s' fallback", name, mid, fallback_label)
            price = round(mrp_total * (1 - FLAT_DISCOUNT), 2)
            db.execute(
                """INSERT INTO medicine_variants
                   (medicine_id, label, mrp, price, stock, sort_order)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (mid, fallback_label, mrp_total, price, 100, 0),
            )

    logger.info(
        "Inserted medicine '%s' (ID=%d) in category '%s'", name, mid, cat_slug
    )

    # ── Download and store product images (gallery in ``image_urls``) ───────
    images: list[dict] = data.get("images") or []
    remote_urls = _collect_scrape_image_urls(images)
    if remote_urls:
        img_sess = http_session or requests.Session()
        local_paths: list[str] = []
        for i, remote in enumerate(remote_urls):
            print(f"    [image] Downloading ({i + 1}/{len(remote_urls)}) for '{name}' ← {remote[:80]}...")
            local_path = _download_and_save_image(remote, mid, session=img_sess, index=i)
            if local_path:
                local_paths.append(local_path)
                print(f"    [image] ✓ Saved → {local_path}")
            else:
                print(f"    [image] ✗ Download failed for slot {i}")
        if local_paths:
            first = local_paths[0]
            urls_json = json.dumps(local_paths)
            with DB() as db:
                db.execute(
                    "UPDATE medicines SET image_url=%s, image_urls=%s WHERE id=%s",
                    (first, urls_json, mid),
                )
        else:
            print(f"    [image] ✗ No images saved for '{name}'")
    else:
        print(f"    [image] ✗ No image URL found in scraped data for '{name}'")

    # ── Insert alternate brands & mappings ──────────────────────────────────
    alt_brands_raw = data.get("alternate_brands") or []
    if alt_brands_raw and not skip_alternate_brands:
        sess = http_session or _detail_session()
        insert_alternate_brands(
            source_med_id=mid,
            source_salt=salt,
            source_category_id=cat_id,
            source_uses=uses,
            source_side_effects=side_effects,
            source_safety_pts=safety_pts,
            source_warning=warning,
            primary_count=primary_count,
            alt_brands=alt_brands_raw,
            http_session=sess,
            source_primary_variant_label=source_primary_variant_label,
            source_medicine_name=name,
        )

    return mid


# ---------------------------------------------------------------------------
# On-demand scrape + insert pipeline
# ---------------------------------------------------------------------------

async def fetch_and_insert(medicine_name: str) -> Optional[dict]:
    """Scrape one medicine from 1mg and insert it into the local database.

    Checks for an existing record before scraping using both an exact LIKE
    name/brand match and a post-scrape idempotency check.  If the medicine
    already exists under the same (or containing) name, returns its ID
    immediately without launching the headless browser or making any network
    request to 1mg.

    Args:
        medicine_name: Free-text medicine name to search on 1mg
            (e.g. ``"Nise 100"``).

    Returns:
        Dict ``{"id": int, "name": str, "already_existed": bool}`` on
        success, or ``None`` if the search returned no result or parsing
        failed.
    """
    from playwright.async_api import async_playwright  # lazy import

    # Early name LIKE check — avoids launching the headless browser when the
    # medicine is already in the catalogue.  Only checks the *name* column
    # (not brand/description) to prevent unrelated alt-brand entries from
    # being treated as a hit.  A Python-level substring check is applied
    # after the SQL query as a second guard.
    q_norm = medicine_name.lower().replace(" ", "")
    with DB() as db:
        early_row = db.fetchone(
            """SELECT id, name FROM medicines
               WHERE is_active = 1
                 AND LOWER(name) LIKE LOWER(%s)
               ORDER BY
                 CASE WHEN LOWER(name) = LOWER(%s) THEN 0
                      ELSE 1 END
               LIMIT 1""",
            (f"%{medicine_name}%", medicine_name),
        )

    if early_row:
        # Python guard: query must genuinely appear in the found medicine name
        found_norm = (early_row["name"] or "").lower().replace(" ", "")
        if q_norm not in found_norm:
            logger.warning(
                "fetch_and_insert: early check returned '%s' for '%s' — mismatch, proceeding to scrape",
                early_row["name"], medicine_name,
            )
            early_row = None

    if early_row:
        logger.info(
            "fetch_and_insert: '%s' already in DB as '%s' (ID=%d) — skipping scrape",
            medicine_name, early_row["name"], early_row["id"],
        )
        return {"id": int(early_row["id"]), "name": early_row["name"], "already_existed": True}

    detail_session = _detail_session()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=_SEARCH_UA,
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        search_page = await context.new_page()

        try:
            link, _ = await search_medicine(search_page, medicine_name, context)
            if not link:
                logger.warning("No 1mg result for '%s'", medicine_name)
                return None

            data = get_details(link, detail_session)
            data["search_name"] = medicine_name

            scraped_name = (data.get("name") or "").strip()
            if not scraped_name:
                logger.warning("Could not parse medicine details for '%s'", medicine_name)
                return None

            # Idempotency check — name AND brand must both match
            existing_id = medicine_exists(
                scraped_name,
                data.get("salt", ""),
                data.get("manufacturer", ""),
            )
            if existing_id:
                logger.info(
                    "Medicine '%s' already exists (ID=%d) — skipping insert",
                    scraped_name, existing_id,
                )
                return {"id": existing_id, "name": scraped_name, "already_existed": True}

            mid = insert_scraped_medicine(data, http_session=detail_session)
            return {"id": mid, "name": scraped_name, "already_existed": False}

        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# On-demand multi-result scrape + insert pipeline
# ---------------------------------------------------------------------------

async def fetch_and_insert_many(
    medicine_name: str,
    max_results: int = 8,
) -> list[dict]:
    """Scrape all matching medicines from 1mg and insert them into the DB.

    Unlike :func:`fetch_and_insert` (which returns a single best match),
    this function uses :func:`search_medicines_all` to collect every product
    URL returned by the 1mg search page and processes each one:

    * **Brand search** (e.g. ``"Moov"``) — returns all Moov variants
      (cream, spray, strong) found on the results page.
    * **Generic search** (e.g. ``"ointment"``) — returns the top
      *max_results* products from the results page regardless of brand.

    Each medicine is scraped, content-rewritten, and inserted idempotently
    (existing records are skipped).  Detail pages are fetched concurrently
    using :mod:`asyncio` + :mod:`concurrent.futures` to minimise wall-clock
    time.

    Args:
        medicine_name: Free-text search query sent to 1mg
            (e.g. ``"Moov Pain Relief"`` or ``"ointment"``).
        max_results: Maximum number of product URLs to process (default 8).

    Returns:
        List of dicts, one per processed product:
        ``{"id": int, "name": str, "already_existed": bool}``.
        Products that could not be parsed are silently skipped.
    """
    from playwright.async_api import async_playwright  # lazy import
    import concurrent.futures

    # Early check: return all existing DB matches for this query to avoid
    # launching the browser when the catalogue already has results.
    q_norm = medicine_name.lower().replace(" ", "")
    with DB() as db:
        existing_rows = db.fetchall(
            """SELECT id, name FROM medicines
               WHERE is_active = 1
                 AND LOWER(name) LIKE LOWER(%s)
               ORDER BY name
               LIMIT %s""",
            (f"%{medicine_name}%", max_results),
        )
    confirmed_existing = [
        r for r in existing_rows
        if q_norm in (r["name"] or "").lower().replace(" ", "")
    ]
    if confirmed_existing:
        print(f"  [scraper] Early exit — '{medicine_name}' already in DB:")
        for r in confirmed_existing:
            print(f"    id={r['id']}  name='{r['name']}'")
        logger.info(
            "fetch_and_insert_many: '%s' — %d match(es) already in DB, skipping scrape",
            medicine_name, len(confirmed_existing),
        )
        return [
            {"id": int(r["id"]), "name": r["name"], "already_existed": True}
            for r in confirmed_existing
        ]

    print(f"  [scraper] Not in DB — launching Playwright for '{medicine_name}' ...")
    detail_session = _detail_session()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=_SEARCH_UA,
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        search_page = await context.new_page()

        try:
            print(f"  [scraper] Searching 1mg for '{medicine_name}' ...")
            urls, _ = await search_medicines_all(
                search_page, medicine_name, context, max_results=max_results
            )
            if not urls:
                print(f"  [scraper] ✗ No URLs found on 1mg for '{medicine_name}'")
                logger.warning(
                    "fetch_and_insert_many: no results found for '%s'", medicine_name
                )
                return []

            print(f"  [scraper] ✓ Found {len(urls)} URL(s) on 1mg:")
            for u in urls:
                print(f"    {u}")

            logger.info(
                "fetch_and_insert_many: found %d URL(s) for '%s' — fetching details",
                len(urls), medicine_name,
            )

            print(f"  [scraper] Fetching detail pages concurrently (workers=4) ...")
            # Fetch all detail pages concurrently in a thread-pool (get_details
            # is synchronous / blocking HTTP so we use run_in_executor).
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                detail_futures = [
                    loop.run_in_executor(pool, get_details, url, detail_session)
                    for url in urls
                ]
                detail_results: list[dict] = await asyncio.gather(*detail_futures)

            print(f"  [scraper] ✓ Detail pages fetched — {len(detail_results)} result(s)")

        finally:
            await browser.close()

    # Insert each scraped medicine idempotently
    inserted: list[dict] = []
    print(f"  [scraper] Inserting medicines into DB ...")
    for data in detail_results:
        scraped_name = (data.get("name") or "").strip()
        if not scraped_name:
            print(f"  [scraper]   ✗ Skipped — could not parse name from {data.get('url')}")
            logger.debug("Skipping result with no name: %s", data.get("url"))
            continue

        data.setdefault("search_name", medicine_name)

        # name AND brand must both match to be treated as a duplicate
        existing_id = medicine_exists(
            scraped_name,
            data.get("salt", ""),
            data.get("manufacturer", ""),
        )
        if existing_id:
            print(f"  [scraper]   ↩ Already exists: '{scraped_name}' (id={existing_id})")
            logger.info("'%s' already exists (ID=%d) — skipping", scraped_name, existing_id)
            inserted.append({"id": existing_id, "name": scraped_name, "already_existed": True})
            continue

        try:
            print(f"  [scraper]   ↳ Inserting '{scraped_name}' ...")
            mid = insert_scraped_medicine(data, http_session=detail_session)
            print(f"  [scraper]   ✓ Inserted '{scraped_name}' → id={mid}")
            inserted.append({"id": mid, "name": scraped_name, "already_existed": False})
        except Exception as exc:
            print(f"  [scraper]   ✗ Error inserting '{scraped_name}': {exc}")
            logger.warning("Error inserting '%s': %s", scraped_name, exc)

    new_count      = sum(1 for r in inserted if not r["already_existed"])
    existing_count = sum(1 for r in inserted if r["already_existed"])
    print(f"  [scraper] ✓ Done — {new_count} new  |  {existing_count} existing  |  total={len(inserted)}")
    logger.info(
        "fetch_and_insert_many: '%s' → %d processed (%d new, %d existing)",
        medicine_name,
        len(inserted),
        new_count,
        existing_count,
    )
    return inserted


# ---------------------------------------------------------------------------
# Bulk JSON import
# ---------------------------------------------------------------------------

def import_from_json(json_path: str | Path) -> dict:
    """Import all medicines from a pre-scraped JSON file into the database.

    Skips entries that already exist (idempotent).  Applies the same
    content rewriting used by :func:`fetch_and_insert`.

    Args:
        json_path: Path to a JSON file containing a list of scraped
            medicine dicts (output format of
            :mod:`medicine_scraper_with_mrp`).

    Returns:
        Stats dict with keys ``inserted``, ``skipped``, ``errors``.

    Example:
        >>> stats = import_from_json("medicines_with_mrp.json")
        >>> print(stats)
        {'inserted': 12, 'skipped': 3, 'errors': 0}
    """
    path = Path(json_path)
    with path.open(encoding="utf-8") as fh:
        records: list[dict] = json.load(fh)

    inserted = skipped = errors = 0

    for rec in records:
        name = (rec.get("name") or rec.get("search_name") or "").strip()
        salt = (rec.get("salt") or "").strip()

        if not name:
            logger.warning("Skipping record with no name: %s", rec)
            errors += 1
            continue

        try:
            brand_val = (rec.get("manufacturer") or "").strip()
            existing = medicine_exists(name, salt, brand_val)
            if existing:
                logger.info("Skipping '%s' — already exists (ID=%d)", name, existing)
                skipped += 1
                # Still ensure alternate-brand mappings are created even when
                # the source medicine was inserted in a prior run.
                try:
                    _process_alt_brands(existing, rec)
                except Exception as alt_exc:
                    logger.warning(
                        "Alt-brand error for existing '%s': %s", name, alt_exc
                    )
                continue

            insert_scraped_medicine(rec)   # alt brands handled inside
            inserted += 1
        except Exception as exc:
            logger.error("Error inserting '%s': %s", name, exc)
            errors += 1

    logger.info(
        "Import complete — inserted=%d  skipped=%d  errors=%d",
        inserted, skipped, errors,
    )
    return {"inserted": inserted, "skipped": skipped, "errors": errors}
