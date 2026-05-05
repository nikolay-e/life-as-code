from __future__ import annotations

from typing import Any

import requests

from logging_config import get_logger

logger = get_logger(__name__)

OFF_BASE = "https://world.openfoodfacts.org"
USER_AGENT = "life-as-code/1.0 (nikolay.eremeev.business@gmail.com)"
DEFAULT_TIMEOUT = 8.0
NUTRIENT_FIELDS = (
    "energy-kcal_100g",
    "proteins_100g",
    "fat_100g",
    "carbohydrates_100g",
    "fiber_100g",
)


def _normalize(product: dict[str, Any]) -> dict[str, Any]:
    nutriments = product.get("nutriments") or {}
    kcal = nutriments.get("energy-kcal_100g")
    if kcal is None:
        energy_kj = nutriments.get("energy-kj_100g") or nutriments.get("energy_100g")
        if isinstance(energy_kj, (int, float)):
            kcal = round(float(energy_kj) / 4.184, 1)
    name = (
        product.get("product_name_ru")
        or product.get("product_name")
        or product.get("generic_name")
        or ""
    )
    return {
        "code": product.get("code"),
        "name": name.strip() or None,
        "brand": (product.get("brands") or "").split(",")[0].strip() or None,
        "calories_per_100g": kcal,
        "protein_g_per_100g": _coerce_float(nutriments.get("proteins_100g")),
        "fat_g_per_100g": _coerce_float(nutriments.get("fat_100g")),
        "carbs_g_per_100g": _coerce_float(nutriments.get("carbohydrates_100g")),
        "fiber_g_per_100g": _coerce_float(nutriments.get("fiber_100g")),
    }


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def search_off(
    query: str, *, lc: str = "ru", page_size: int = 10
) -> list[dict[str, Any]]:
    params: dict[str, str | int] = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "lc": lc,
        "fields": "code,product_name,product_name_ru,generic_name,brands,nutriments",
    }
    try:
        response = requests.get(
            f"{OFF_BASE}/cgi/search.pl",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("openfoodfacts_search_failed", query=query, error=str(exc))
        return []
    payload = response.json() if response.content else {}
    products = payload.get("products") or []
    normalized = [_normalize(p) for p in products if p.get("code")]
    return [p for p in normalized if p.get("name")]


def get_off_by_barcode(code: str) -> dict[str, Any] | None:
    try:
        response = requests.get(
            f"{OFF_BASE}/api/v2/product/{code}.json",
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("openfoodfacts_barcode_failed", code=code, error=str(exc))
        return None
    payload = response.json() if response.content else {}
    if payload.get("status") != 1:
        return None
    return _normalize(payload.get("product") or {})
