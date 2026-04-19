"""
Medicine scraper for 1mg.

Architecture
------------
* **Search** (find the drug URL): 1mg's search page renders results via
  JavaScript (React SPA), so a real headless browser (Playwright) is required.

* **Detail page** (name, salt, manufacturer, uses, side-effects, MRP):
  1mg serves two different HTML responses depending on the ``User-Agent``:
  - Modern Chrome UA → minimal SPA shell; data loaded via AJAX after mount.
  - Non-modern / simple UA → legacy SSR page that embeds the full Redux state
    as ``window.__INITIAL_STATE__ = {...}`` in a ``<script>`` tag.
  We exploit the second path using ``requests`` with a simple UA, avoiding
  the need for a headless browser on every detail fetch and making it ≈10×
  faster.
"""

import asyncio
import json
import logging
import re
import time
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.1mg.com"


def _absolute_1mg_href(raw: str) -> str:
    """Normalize a raw href to a full https URL, or return empty if unusable."""
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s.split("?")[0]
    if s.startswith("/"):
        return BASE_URL + s.split("?")[0]
    return ""


def resolve_1mg_product_url(entry: dict) -> str:
    """Build an absolute https URL to a 1mg drug/OTC product page from API fields.

    Substitute rows may expose the link under ``url``, ``link``, ``href``,
    ``deeplink``, ``productUrl``, nested ``action`` / ``cta`` objects, etc.
    Relative paths (``/drugs/...``) are prefixed with :data:`BASE_URL`.

    Args:
        entry: Raw dict from ``productSubstitutes.attributesData`` or similar.

    Returns:
        A full URL string, or ``""`` if nothing usable is present.
    """
    if not isinstance(entry, dict):
        return ""
    for key in (
        "url",
        "link",
        "href",
        "deeplink",
        "productUrl",
        "webUrl",
        "path",
        "redirectionUrl",
        "ctaUrl",
        "navigationUrl",
    ):
        u = _absolute_1mg_href(str(entry.get(key) or ""))
        if u:
            return u
    for nested_key in ("action", "cta", "meta", "navigation", "data"):
        sub = entry.get(nested_key)
        if isinstance(sub, dict):
            for key in ("url", "link", "href", "deeplink", "path", "target"):
                u = _absolute_1mg_href(str(sub.get(key) or ""))
                if u:
                    return u
    return ""


def search_1mg_first_product_url(product_name: str, session: requests.Session) -> str:
    """Resolve a product URL by loading 1mg search HTML and taking the first drug/OTC link.

    Used when substitute API rows omit ``url`` but we still need the main product
    page for :func:`get_details`. The search page is fetched with the same simple
    UA as detail pages so SSR may include real ``<a href=\"/drugs/...\">`` links.

    Args:
        product_name: Medicine display name (e.g. ``\"Olergel Dental Gel\"``).
        session: Reuse the same :class:`~requests.Session` as :func:`get_details`.

    Returns:
        Full ``https://www.1mg.com/...`` URL, or ``\"\"`` if none found.
    """
    q = (product_name or "").strip()
    if len(q) < 2:
        return ""
    try:
        search_url = f"{BASE_URL}/search/all?name={quote_plus(q)}"
        resp = session.get(search_url, timeout=25)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href*='/drugs/'], a[href*='/otc/']"):
            href = (a.get("href") or "").strip()
            if not href or "/search/" in href:
                continue
            u = _absolute_1mg_href(href)
            if u and ("/drugs/" in u or "/otc/" in u):
                return u
    except Exception as exc:
        logger.debug("search_1mg_first_product_url(%r): %s", q, exc)
    return ""


# Modern UA → SPA shell (no __INITIAL_STATE__).  Used for search page.
_SEARCH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Simple / non-modern UA → legacy SSR page with __INITIAL_STATE__ embedded.
# 1mg serves this version to user-agents that don't look like a current browser.
_DETAIL_UA = "Mozilla/5.0 Chrome/124"

# Playwright timeout (ms) for the search page
NAV_TIMEOUT_MS = 45_000

# Selector that appears once the search results JS has rendered.
# Covers both Rx /drugs/ and OTC /otc/ product links so that products like
# Moov, Vicks, Burnol (sold OTC) are discoverable alongside prescription drugs.
SEARCH_SELECTOR = "a[href*='/drugs/'], a[href*='/otc/']"

# Each entry is either:
#   • a plain string — name only, URL discovered via search
#   • a (name, direct_url) tuple — URL is used directly when search fails
#     (useful for medicines whose search results are dominated by substitutes,
#     e.g. 1mg shows Dolo 650 for "calpol" even though Calpol has a live page)
MEDICINES: list[str | tuple[str, str]] = [
    "Telma 40", "Pantop 40", "Zifi 200", "Zedocef 200", "Atorva 10",
    "Rosuvas 10", "Deplatt 75", "Ondero 5", "Jalra 50", "Istavel 100",
    "Rybelsus 7", "Gluconorm SR 500", "Azulix 2", "Teczine 5", "Nise 100",
    ("Calpol 650",              "https://www.1mg.com/drugs/calpol-650-tablet-842047"),
    ("Moov Pain Relief Cream",  "https://www.1mg.com/otc/moov-pain-relief-cream-otc316631"),
]


# ---------------------------------------------------------------------------
# Search (Playwright)
# ---------------------------------------------------------------------------

async def _navigate_search_page(
    page: Page,
    name: str,
    context,
    max_retries: int = 2,
) -> tuple[Optional[Page], list]:
    """Navigate to the 1mg search page and return rendered product links.

    Shared navigation helper used by both :func:`search_medicine` and
    :func:`search_medicines_all`.  Handles Playwright timeouts by closing
    the stale page and opening a fresh one from *context*.

    Args:
        page: Playwright Page instance.
        name: Medicine / search query string.
        context: Playwright BrowserContext for fresh-page retries.
        max_retries: Max retry attempts on timeout.

    Returns:
        Tuple ``(active_page, link_elements)`` where ``link_elements`` is the
        list of all ``<a>`` ElementHandles matching :data:`SEARCH_SELECTOR`.
        Returns ``(active_page, [])`` on failure.
    """
    encoded = quote_plus(name)
    search_url = f"{BASE_URL}/search/all?name={encoded}"
    active_page = page

    for attempt in range(1 + max_retries):
        try:
            await active_page.goto(
                search_url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded"
            )
            await active_page.wait_for_selector(SEARCH_SELECTOR, timeout=NAV_TIMEOUT_MS)
            break
        except PWTimeout:
            if attempt < max_retries:
                logger.warning(
                    "Timeout on search for '%s' (attempt %d/%d) — refreshing page",
                    name, attempt + 1, 1 + max_retries,
                )
                try:
                    await active_page.close()
                except Exception:
                    pass
                active_page = await context.new_page()
            else:
                logger.warning(
                    "Timeout waiting for results for '%s' after %d attempts",
                    name, 1 + max_retries,
                )
                return active_page, []
        except Exception as exc:
            logger.warning("Error navigating search page for '%s': %s", name, exc)
            return active_page, []

    links = await active_page.query_selector_all(SEARCH_SELECTOR)
    return active_page, links


async def search_medicines_all(
    page: Page,
    name: str,
    context,
    *,
    max_results: int = 8,
    max_retries: int = 2,
) -> tuple[list[str], Page]:
    """Return up to *max_results* product URLs from the 1mg search page.

    Operates in two modes depending on whether the search name is a specific
    brand or a generic term:

    * **Brand mode** — if any result's link text contains the normalised
      *name* (e.g. searching "Moov" finds "Moov Pain Relief Cream 50g",
      "Moov Strong Cream 30g", …), only those matching results are returned.
      This prevents Dolo 650 from being returned for a "Calpol" search.

    * **Generic mode** — if *no* result matches the name (e.g. "ointment",
      "cream", "pain relief"), all top results up to *max_results* are
      returned, allowing bulk insertion of an entire category.

    Args:
        page: Playwright Page instance (reused across calls).
        name: Search query string (brand name or generic term).
        context: Playwright BrowserContext for fresh-page retries.
        max_results: Maximum number of URLs to return (default 8).
        max_retries: Max retry attempts on Playwright timeout.

    Returns:
        Tuple ``(url_list, active_page)``.  ``url_list`` is empty when the
        search page times out or returns no results.
    """
    active_page, all_links = await _navigate_search_page(page, name, context, max_retries)
    if not all_links:
        return [], active_page

    name_normalised = name.lower().replace(" ", "")

    # Collect (text, absolute_url) for every result link (deduplicated by URL)
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []
    for el in all_links:
        try:
            text = (await el.inner_text()).strip()
        except Exception:
            text = ""
        href = await el.get_attribute("href") or ""
        url = href if href.startswith("http") else BASE_URL + href
        if url not in seen:
            seen.add(url)
            candidates.append((text, url))

    # Brand match: result text contains the search name
    brand_matches = [
        url for text, url in candidates
        if name_normalised in text.lower().replace(" ", "")
    ]

    if brand_matches:
        logger.info(
            "search_medicines_all: '%s' → %d brand match(es) (capped at %d)",
            name, len(brand_matches), max_results,
        )
        return brand_matches[:max_results], active_page

    # Generic mode: no brand match — return all top results
    all_urls = [url for _, url in candidates[:max_results]]
    logger.info(
        "search_medicines_all: '%s' → generic mode, returning %d result(s)",
        name, len(all_urls),
    )
    return all_urls, active_page


async def search_medicine(
    page: Page,
    name: str,
    context,
    *,
    max_retries: int = 2,
) -> tuple[Optional[str], Page]:
    """Return the single best-matching product URL for a brand-name search.

    Thin wrapper around :func:`search_medicines_all` that enforces strict
    brand-name matching: returns ``None`` (instead of the first generic
    result) when no result text contains *name*.  Used by the batch scraper
    where each entry in :data:`MEDICINES` is a specific brand name.

    Args:
        page: Playwright Page instance.
        name: Brand name to search for (e.g. ``"Nise 100"``).
        context: Playwright BrowserContext for fresh-page retries.
        max_retries: Max retry attempts on timeout.

    Returns:
        Tuple ``(url_or_None, active_page)``.
    """
    active_page, all_links = await _navigate_search_page(page, name, context, max_retries)
    if not all_links:
        return None, active_page

    name_normalised = name.lower().replace(" ", "")

    best_href: Optional[str] = None
    for el in all_links:
        try:
            text = (await el.inner_text()).strip()
        except Exception:
            text = ""
        if name_normalised in text.lower().replace(" ", ""):
            best_href = await el.get_attribute("href") or ""
            logger.debug("Brand match for '%s': %s", name, text)
            break

    if not best_href:
        top_texts: list[str] = []
        for el in all_links[:3]:
            try:
                top_texts.append((await el.inner_text()).strip())
            except Exception:
                pass
        logger.warning(
            "No brand-name match for '%s' on 1mg — may have been removed. "
            "Top results: %s",
            name, top_texts,
        )
        return None, active_page

    url = best_href if best_href.startswith("http") else BASE_URL + best_href
    return url, active_page


# ---------------------------------------------------------------------------
# Detail page (plain requests + HTML parsing)
# ---------------------------------------------------------------------------

def _strip_html(html_str: str) -> str:
    """Remove HTML tags and collapse whitespace to produce plain text.

    Args:
        html_str: Raw HTML fragment (may contain ``<ul>``, ``<li>``, etc.).

    Returns:
        Plain text with tags stripped and whitespace normalised.
    """
    text = re.sub(r"<[^>]+>", " ", html_str)
    return re.sub(r"\s+", " ", text).strip()


def _parse_otc_general_description(html: str, result: dict) -> None:
    """Parse the OTC ``generalDescriptionData.content`` HTML block into fields.

    1mg OTC pages embed ALL product information (Key Ingredients, Key Benefits,
    Directions For Use, Safety Information, Indications, Dosage…) inside ONE
    single HTML string under ``staticData.generalDescriptionData.content``.
    The sections are separated by ``<b>SectionName:</b>`` tags.

    This function splits that HTML on the bold section headers and maps each
    section into the appropriate ``result`` key so downstream insertion logic
    can use them for ``uses``, ``salt``, ``safety_points``, etc.

    Args:
        html:   Raw HTML string from ``generalDescriptionData.content``.
        result: The in-progress result dict from :func:`_parse_initial_state`.
                Modified in-place.
    """
    from bs4 import BeautifulSoup, NavigableString, Tag

    soup = BeautifulSoup(html, "html.parser")

    _SECTION_MAP = {
        "key benefits":        "key_benefits",
        "key ingredients":     "key_ingredients",
        "directions for use":  "directions_for_use",
        "direction for use":   "directions_for_use",
        "how to use":          "directions_for_use",
        "safety information":  "safety_information",
        "dosage":              "directions_for_use",
        "indications":         "key_benefits",   # treat as uses/benefits
        "suitable for":        "key_benefits",
        "best suited for":     "key_benefits",
        "ideal for":           "key_benefits",
    }

    current_key: Optional[str] = None
    accum: list[str]            = []

    def _flush():
        if current_key and accum:
            text = " | ".join(t for t in accum if t)
            if result.get(current_key):
                result[current_key] += " | " + text
            else:
                result[current_key] = text
        accum.clear()

    for node in soup.children:
        if isinstance(node, Tag) and node.name == "b":
            _flush()
            heading = node.get_text(strip=True).rstrip(":").lower()
            current_key = _SECTION_MAP.get(heading)
        elif isinstance(node, Tag) and node.name == "ul":
            items = [li.get_text(strip=True) for li in node.find_all("li") if li.get_text(strip=True)]
            accum.extend(items)
        elif isinstance(node, (NavigableString, Tag)):
            text = node.get_text(strip=True) if isinstance(node, Tag) else str(node).strip()
            if text:
                accum.append(text)

    _flush()

    # Fallback: if no sections were parsed, treat the whole stripped text as
    # the product introduction / key_benefits so we always store *something*.
    if not result["key_benefits"]:
        plain = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
        if plain:
            result["key_benefits"] = plain[:800]


def _parse_initial_state(html: str) -> dict:
    """Extract medicine data from ``window.__INITIAL_STATE__`` in the HTML.

    When fetched with a non-modern user-agent, 1mg returns a legacy SSR page
    that embeds the full Redux store as a ``<script>`` tag:

    .. code-block:: html

        <script>window.__INITIAL_STATE__ = {...};</script>

    We extract the JSON by tracking brace depth so the parser handles
    arbitrarily nested objects without requiring a full JS parser.

    Exact state paths (verified against live 1mg pages):

    Rx drug pages use ``drugPageReducer``; OTC product pages (e.g. Moov,
    Vicks, Burnol) use ``otcPageReducer``.  Both reducers share the same
    internal structure so the same extraction logic applies to both.

    - name:                 ``<reducer>.staticData.pageTitleData.header``
    - salt:                 ``<reducer>.staticData.generalInformation.attributesData[label=="Contains"].value``
    - manufacturer:         ``<reducer>.staticData.generalInformation.attributesData[label=="Marketer"].value``
    - uses:                 ``<reducer>.staticData.productUses.content``        (HTML)
    - side_effects:         ``<reducer>.staticData.sideEffect.content``         (HTML)
    - product_introduction: ``<reducer>.staticData.productIntroduction.content``        (HTML)
    - mrp:                  ``<reducer>.dynamicData.mixpanelData.mrp``                   (float)
    - variants:             ``<reducer>.dynamicData.variants[*].variant.variantsData``
    - alternate_brands:     ``<reducer>.dynamicData.productSubstitutes.attributesData``
    - images:               ``<reducer>.staticData.stillAndMovingImagesData``

    Args:
        html: Raw HTML of the drug/OTC detail page (SSR version).

    Returns:
        Dict with keys ``name``, ``salt``, ``manufacturer``, ``uses``,
        ``side_effects``, ``mrp``.  Fields default to ``""`` / ``None``.
    """
    result: dict = {
        "name": "", "salt": "", "manufacturer": "",
        "uses": "", "side_effects": "", "mrp": None,
        "product_introduction": "", "variants": [],
        "alternate_brands": [], "images": [],
        # OTC-specific product information sections
        "key_benefits":       "",
        "key_ingredients":    "",
        "directions_for_use": "",
        "safety_information": "",
        "is_otc":             False,
    }

    marker = "window.__INITIAL_STATE__ = "
    idx = html.find(marker)
    if idx == -1:
        logger.debug("__INITIAL_STATE__ marker not found")
        return result

    json_start = html.index("{", idx)
    depth = 0
    json_end = json_start
    for pos, ch in enumerate(html[json_start:], start=json_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                json_end = pos + 1
                break

    try:
        state: dict = json.loads(html[json_start:json_end])
    except json.JSONDecodeError as exc:
        logger.debug("JSON parse error for __INITIAL_STATE__: %s", exc)
        return result

    # drugPageReducer  → Rx prescription product pages (/drugs/)
    # otcPageReducer   → OTC product pages (/otc/, e.g. Moov, Vicks, Burnol)
    # Both share identical internal structure.
    dpr: dict = state.get("drugPageReducer") or state.get("otcPageReducer") or {}
    if not dpr:
        logger.debug("Neither drugPageReducer nor otcPageReducer found in state")
    sd: dict = dpr.get("staticData") or {}
    dd: dict = dpr.get("dynamicData") or {}

    # ── Name (same path for both Rx and OTC) ──────────────────────────────────
    result["name"] = (sd.get("pageTitleData") or {}).get("header", "")

    # ── Manufacturer ──────────────────────────────────────────────────────────
    # OTC pages: sd.manufacturerInfo.name
    # Rx  pages: sd.generalInformation.attributesData[label=="Marketer"]
    mfr_info = (sd.get("manufacturerInfo") or {}).get("name", "")
    if mfr_info:
        # Strip leading sort prefix that 1mg sometimes adds: "A)Accra Pac…"
        result["manufacturer"] = re.sub(r"^[A-Z]\)", "", mfr_info).strip()
    else:
        for attr in (sd.get("generalInformation") or {}).get("attributesData", []):
            label_lo = (attr.get("label") or "").lower()
            if label_lo in ("marketer", "manufacturer", "brand",
                            "marketed by", "manufactured by"):
                result["manufacturer"] = attr.get("value", "")
                break

    # ── Salt / Key Ingredients ────────────────────────────────────────────────
    # Rx only; OTC salt is extracted from generalDescriptionData HTML below.
    for attr in (sd.get("generalInformation") or {}).get("attributesData", []):
        label_lo = (attr.get("label") or "").lower()
        if label_lo in ("contains", "composition"):
            result["salt"] = attr.get("value", "")
            break

    # ── Rx-specific content fields ────────────────────────────────────────────
    # productUses      → short indication list  (e.g. "Treatment of Fever Pain relief")
    # productBenefits  → rich HTML per-condition descriptions (more useful as uses text)
    # productIntroduction → dosing / general advice paragraph
    # howToUse         → how to take the medicine  → directions_for_use
    # howWorks         → mechanism of action        → enriches product_introduction
    # sideEffect       → side effects paragraph
    # safetyAdvice     → array of safety warnings   → safety_information

    uses_html: str = (sd.get("productUses") or {}).get("content", "")
    result["uses"] = _strip_html(uses_html)

    # productBenefits is richer than productUses — use it as key_benefits
    benefits_html: str = (sd.get("productBenefits") or {}).get("content", "")
    if benefits_html:
        result["key_benefits"] = _strip_html(benefits_html)

    se_html: str = (sd.get("sideEffect") or {}).get("content", "")
    result["side_effects"] = _strip_html(se_html)

    how_works_html: str = (sd.get("howWorks") or {}).get("content", "")
    intro_html: str = (sd.get("productIntroduction") or {}).get("content", "")
    # howWorks goes FIRST (mechanism / "what it does" paragraph), then the
    # detailed usage/dosing/safety paragraphs from productIntroduction.
    intro_parts = [_strip_html(how_works_html), _strip_html(intro_html)]
    result["product_introduction"] = " ".join(p for p in intro_parts if p)

    # howToUse → directions_for_use
    how_to_use_html: str = (sd.get("howToUse") or {}).get("content", "")
    if how_to_use_html:
        result["directions_for_use"] = _strip_html(how_to_use_html)

    # safetyAdvice.warnings[] → each has a "description" string
    safety_warnings: list = (sd.get("safetyAdvice") or {}).get("warnings") or []
    safety_texts = [
        w.get("description", "")
        for w in safety_warnings
        if isinstance(w, dict) and w.get("description")
    ]
    if safety_texts:
        result["safety_information"] = " | ".join(safety_texts)

    # ── OTC product info — generalDescriptionData ─────────────────────────────
    # OTC pages bundle ALL product info (Key Benefits, Key Ingredients,
    # Directions, Safety Info, Indications…) into ONE HTML block at
    # sd.generalDescriptionData.content.  We split it by <b> section headers.
    general_desc_html: str = (sd.get("generalDescriptionData") or {}).get("content", "")
    if general_desc_html:
        _parse_otc_general_description(general_desc_html, result)

    # ── MRP ───────────────────────────────────────────────────────────────────
    # mixpanelData.mrp is present for both Rx and OTC pages and holds the MRP
    # of the currently-selected SKU.
    for _cand in [
        (dd.get("mixpanelData") or {}).get("mrp"),
        (dd.get("sku") or {}).get("mrp"),
        dd.get("mrp"),
    ]:
        if _cand is not None:
            try:
                result["mrp"] = float(_cand)
                break
            except (ValueError, TypeError):
                continue

    # ── Variants ──────────────────────────────────────────────────────────────
    # OTC pages: dd.variantsBottomsheetData[0].options  (confirmed via live page)
    #            dd.lowEmphasisSingleSelectionData[0].variantsData  (fallback)
    # Rx  pages: dd.variants[].variant.variantsData[]               (nested)
    variants_out: list[dict] = []

    # --- OTC path ---
    otc_options: list = []
    for node in (dd.get("variantsBottomsheetData") or []):
        otc_options = node.get("options") or []
        if otc_options:
            break
    if not otc_options:
        for node in (dd.get("lowEmphasisSingleSelectionData") or []):
            otc_options = node.get("variantsData") or []
            if otc_options:
                break

    if otc_options:
        selected_mrp = result.get("mrp")  # MRP of the selected SKU from mixpanelData
        for v in otc_options:
            label = v.get("ctaLabel") or v.get("label") or ""
            if not label:
                continue
            slug = v.get("slug") or ""
            url  = (BASE_URL + slug) if slug else None
            # For the selected variant we know the MRP; for others we scale
            # proportionally by pack size (extracted from label).
            is_sel = bool(v.get("isSelected"))
            variants_out.append({
                "label":        label,
                "is_selected":  is_sel,
                "is_available": bool(v.get("isAvailable", True)),
                "url":          url,
                "mrp":          selected_mrp if is_sel else None,
            })
    else:
        # --- Rx path (nested shape) ---
        variants_raw: list = dd.get("variants") or dd.get("packVariants") or []
        for group in variants_raw:
            vdata_list: list = (group.get("variant") or {}).get("variantsData") or []
            for v in vdata_list:
                mrp_v = v.get("mrp") or v.get("price")
                raw_url = v.get("url")
                # 1mg stores "False" (string) for the currently-selected SKU's
                # own URL — treat that as None (current page, no extra fetch needed).
                variant_url = (
                    (BASE_URL + raw_url)
                    if raw_url and raw_url not in (False, "False", "")
                    else None
                )
                variants_out.append({
                    "label":        v.get("ctaLabel", ""),
                    "is_selected":  bool(v.get("isSelected")),
                    "is_available": bool(v.get("isAvailable")),
                    "url":          variant_url,
                    "mrp":          float(mrp_v) if mrp_v else None,
                })

    # ── Last-resort fallback for secondary variant pages ──────────────────────
    # When a scrape lands on a non-primary SKU page (e.g. Paracip 500 "15 tabs"
    # page) 1mg omits variantsBottomsheetData and dd.variants entirely.  We
    # reconstruct a single variant from priceData.packSizes + mixpanelData.mrp
    # so the product is still stored with a meaningful label instead of
    # falling all the way back to "Standard Pack".
    if not variants_out:
        pack_label = (dd.get("priceData") or {}).get("packSizes", "")
        if pack_label:
            variants_out.append({
                "label":        pack_label,
                "is_selected":  True,
                "is_available": True,
                "url":          None,
                "mrp":          result.get("mrp"),
            })
            logger.debug("Used priceData.packSizes fallback variant: %r", pack_label)

    result["variants"] = variants_out

    # --- Alternate brands (same salt, different brand) ---
    # Source: dynamicData.productSubstitutes.attributesData
    # Each entry: name, manufacturer, price_per_unit, price_difference, url, id
    alt_brands_raw: list = (dd.get("productSubstitutes") or {}).get("attributesData", [])
    alt_brands_out: list[dict] = []
    for ab in alt_brands_raw:
        name_html: str = (ab or {}).get("header", "")
        price_str: str = (ab or {}).get("value", "")
        diff: dict = (ab or {}).get("valueDifference") or {}
        # Prefer any resolvable product link so downstream code can open the
        # full drug page (variants, ml/gm packs, images).
        product_page_url = resolve_1mg_product_url(ab or {}) or None
        # Extract image URL from common 1mg field names for alt-brand entries
        ab_image = (
            (ab or {}).get("imageUrl")
            or (ab or {}).get("image")
            or (ab or {}).get("imgUrl")
            or ""
        )
        alt_brands_out.append({
            "name": _strip_html(name_html),
            "manufacturer": (ab or {}).get("subtitle", "").lstrip("by ").strip(),
            "price_per_unit": _strip_html(price_str),
            "price_difference": diff.get("text", ""),
            "url": product_page_url,
            "id": (ab or {}).get("id", ""),
            "image_url": ab_image,
        })
    result["alternate_brands"] = alt_brands_out

    # --- Images: all product images with thumbnail / medium / high URLs ---
    # Source: staticData.stillAndMovingImagesData (includes alt text)
    images_raw: list = sd.get("stillAndMovingImagesData") or []
    images_out: list[dict] = []
    for img in images_raw:
        if not isinstance(img, dict):
            continue
        images_out.append({
            "thumbnail": img.get("thumbnail", ""),
            "medium": img.get("medium", ""),
            "high": img.get("high", ""),
            "alt": img.get("imageAltText", ""),
        })
    result["images"] = images_out

    return result


def get_details(url: str, session: requests.Session) -> dict:
    """Fetch and parse medicine metadata from a 1mg drug detail page.

    Uses a plain HTTP GET with ``_DETAIL_UA`` which causes 1mg to return the
    legacy SSR page with ``window.__INITIAL_STATE__`` embedded — no headless
    browser required.

    Args:
        url: Absolute URL of the drug detail page.
        session: ``requests.Session`` with ``_DETAIL_UA`` already configured.

    Returns:
        Dict with keys: ``url``, ``name``, ``salt``, ``manufacturer``,
        ``uses``, ``side_effects``, ``product_introduction``,
        ``variants``, ``mrp``.

    Example:
        >>> import requests
        >>> s = requests.Session()
        >>> s.headers["User-Agent"] = _DETAIL_UA
        >>> d = get_details("https://www.1mg.com/drugs/nise-tablet-65642", s)
        >>> assert d["name"] == "Nise Tablet"
    """
    data: dict = {"url": url}

    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        # 1mg pages are UTF-8; force correct decoding regardless of
        # the Content-Type charset header (which may be absent or wrong)
        resp.encoding = "utf-8"
    except requests.RequestException as exc:
        logger.error("Failed to fetch detail page '%s': %s", url, exc)
        return data

    parsed = _parse_initial_state(resp.text)
    data.update(parsed)
    # Mark OTC products (URL path contains /otc/) so the insertion layer can
    # set requires_rx = False and use the correct content fields.
    data["is_otc"] = "/otc/" in url

    # Fallback MRP: scan visible page text for ₹ symbol if not in state
    if data.get("mrp") is None:
        soup = BeautifulSoup(resp.text, "html.parser")
        price_match = re.search(r"₹\s?(\d+(?:\.\d+)?)", soup.get_text())
        data["mrp"] = float(price_match.group(1)) if price_match else None

    return data


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def scrape(medicines: list[str | tuple[str, str]] = MEDICINES) -> list[dict]:
    """Scrape medicine details for every name in *medicines*.

    Uses Playwright only for the JavaScript-rendered search results page and
    plain ``requests`` (with the legacy-SSR user-agent) for all detail pages.

    Args:
        medicines: List of medicine names (or ``(name, direct_url)`` tuples)
            to scrape.  When a tuple is provided, *direct_url* is used as a
            fallback if the search fails to find a brand-name match — useful
            for medicines like Calpol whose 1mg search is dominated by
            substitutes even though the product page is live.
            Defaults to :data:`MEDICINES`.

    Returns:
        List of detail dicts for every successfully found medicine.
    """
    results: list[dict] = []

    # Shared requests session for all detail-page fetches
    detail_session = requests.Session()
    detail_session.headers.update({
        "User-Agent": _DETAIL_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=_SEARCH_UA,
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        search_page = await context.new_page()

        for entry in medicines:
            # Unpack optional direct-URL fallback
            if isinstance(entry, tuple):
                med, fallback_url = entry
            else:
                med, fallback_url = entry, None

            logger.info("Searching: %s", med)

            link, search_page = await search_medicine(search_page, med, context)
            if not link:
                if fallback_url:
                    logger.info(
                        "Search found no match for '%s' — using direct URL fallback: %s",
                        med, fallback_url,
                    )
                    link = fallback_url
                else:
                    logger.warning("Not found: %s", med)
                    continue

            logger.info("Found: %s", link)

            # Synchronous detail fetch (non-browser, SSR path)
            data = get_details(link, detail_session)
            data["search_name"] = med
            results.append(data)

            # Polite crawl delay
            await asyncio.sleep(1)

        await browser.close()

    return results


if __name__ == "__main__":
    scraped = asyncio.run(scrape())

    output_path = "medicines_with_mrp.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(scraped, fh, indent=2, ensure_ascii=False)

    logger.info("Done. %d medicines saved to %s", len(scraped), output_path)
