"""Google Places API: find businesses, get details. Filter for no website / no app."""
import json
import time
from typing import Any, Optional

import requests

from .config_loader import get_google_api_key
from .db import insert_lead
from .logging_utils import get_logger

logger = get_logger(__name__)

PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"


def _request(url: str, params: dict[str, str]) -> dict[str, Any]:
    key = get_google_api_key()
    if not key:
        raise ValueError("GOOGLE_PLACES_API_KEY not set")
    params["key"] = key
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def text_search(query: str, page_token: Optional[str] = None) -> dict[str, Any]:
    params: dict[str, str] = {"query": query}
    if page_token:
        params["pagetoken"] = page_token
    return _request(PLACES_TEXT_SEARCH, params)


def place_details(place_id: str) -> dict[str, Any]:
    return _request(PLACES_DETAILS, {"place_id": place_id, "fields": "place_id,name,formatted_address,formatted_phone_number,international_phone_number,website,url,address_components,types"})  # noqa: E501


def _website_status(place: dict[str, Any]) -> str:
    """
    Return one of: has_website | no_website | unknown.

    We only treat a lead as "no website" when Places explicitly returns a
    website field that is empty. If the website field is missing entirely,
    status is unknown and we skip it to avoid false positives.
    """
    if "website" not in place:
        return "unknown"
    website = (place.get("website") or "").strip()
    if website and website.startswith("http"):
        return "has_website"
    return "no_website"


def _has_app_link(place: dict[str, Any]) -> bool:
    # Google Place doesn't have a dedicated "app" field; url is often Maps link.
    # We treat "no website" as primary signal for "needs a website".
    # If you later add app detection (e.g. from website content), plug here.
    return False


def _city_from_components(components: list[dict]) -> str:
    for c in components:
        if "locality" in (c.get("types") or []):
            return (c.get("long_name") or "").strip()
    return ""


def _country_from_components(components: list[dict]) -> str:
    for c in components:
        if "country" in (c.get("types") or []):
            return (c.get("long_name") or "").strip()
    return ""


def is_target_lead(place: dict[str, Any]) -> bool:
    """Keep businesses that don't have a website (and optionally no app)."""
    return _website_status(place) == "no_website"


def fetch_and_store_leads(
    locations: dict[str, list[str]],
    industries: list[str],
    max_results_per_query: int = 20,
) -> int:
    """
    For each (country -> cities) and each industry, run text search,
    get details, filter for no website, store in DB. Returns total leads added.
    """
    key = get_google_api_key()
    if not key:
        logger.error("GOOGLE_PLACES_API_KEY not set")
        return 0

    total_stored = 0
    skipped_has_website = 0
    skipped_unknown_website = 0
    seen_place_ids: set[str] = set()

    for country, cities in (locations or {}).items():
        for city in cities:
            for industry in (industries or []):
                query = f"{industry} in {city}, {country}"
                try:
                    data = text_search(query)
                    if data.get("status") != "OK" and data.get("status") != "ZERO_RESULTS":
                        logger.warning("Places API status: %s for query %s", data.get("status"), query)
                        continue
                    results = data.get("results") or []
                    for item in results[:max_results_per_query]:
                        place_id = item.get("place_id")
                        if not place_id or place_id in seen_place_ids:
                            continue
                        seen_place_ids.add(place_id)
                        time.sleep(0.2)  # avoid rate limit
                        try:
                            det = place_details(place_id)
                            inner = (det.get("result") or {}) if det.get("status") == "OK" else {}
                            if not inner:
                                continue
                            status = _website_status(inner)
                            if status == "has_website":
                                skipped_has_website += 1
                                continue
                            if status == "unknown":
                                skipped_unknown_website += 1
                                continue
                            name = (inner.get("name") or "").strip() or "Unknown"
                            address = (inner.get("formatted_address") or "").strip()
                            phone = (inner.get("formatted_phone_number") or inner.get("international_phone_number") or "").strip()
                            website = (inner.get("website") or "").strip()
                            components = inner.get("address_components") or []
                            city_name = _city_from_components(components)
                            country_name = _country_from_components(components) or country
                            # Places API rarely returns email; store if we ever get it
                            email = (inner.get("email") or "").strip() if isinstance(inner.get("email"), str) else ""
                            raw_json = json.dumps(inner, ensure_ascii=False)
                            insert_lead(
                                place_id=place_id,
                                name=name,
                                address=address,
                                city=city_name or city,
                                country=country_name,
                                phone=phone,
                                email=email,
                                website=website,
                                industry=industry,
                                raw_json=raw_json,
                            )
                            total_stored += 1
                            logger.info("Stored lead: %s (%s)", name, city_name or city)
                        except Exception as e:
                            logger.warning("Place details error for %s: %s", place_id, e)
                    page_token = data.get("next_page_token")
                    if page_token:
                        time.sleep(1)
                        data2 = text_search(query, page_token=page_token)
                        # could iterate results from data2 same way (simplified: one page per query)
                except Exception as e:
                    logger.warning("Text search error for %s: %s", query, e)

    logger.info(
        "Lead filter summary: stored=%s, skipped_has_website=%s, skipped_unknown_website=%s",
        total_stored,
        skipped_has_website,
        skipped_unknown_website,
    )
    return total_stored
