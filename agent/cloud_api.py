"""Authenticated cloud API client used by the local DVR setup page."""

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CloudApiError(RuntimeError):
    """The Mini PC could not retrieve provisioning data from the cloud API."""


def _base_url() -> str:
    return (os.environ.get("IVELY_API_BASE") or "https://api.ivelytech.com").rstrip("/")


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = (os.environ.get("IVELY_API_TOKEN") or os.environ.get("IVELY_CLOUD_API_KEY") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(path: str) -> Any:
    request = Request(f"{_base_url()}{path}", headers=_headers(), method="GET")
    try:
        with urlopen(request, timeout=float(os.environ.get("IVELY_API_TIMEOUT", "15"))) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CloudApiError(f"Cloud API returned HTTP {exc.code}: {detail[:200]}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise CloudApiError(f"Cloud API request failed: {exc}") from exc


def _first_text(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def list_customers() -> list[dict[str, Any]]:
    data = _get("/api/v1/customer_users/getCustomerUsers?skip=0&limit=500")
    if not isinstance(data, list):
        raise CloudApiError("Customer API response is not a list")
    customers: dict[int, dict[str, Any]] = {}
    for row in data:
        if not isinstance(row, dict) or row.get("customer_id") is None:
            continue
        customer_id = int(row["customer_id"])
        name = _first_text(row, ("customer_name", "company_name", "org_name", "organization_name", "name"))
        customers.setdefault(customer_id, {"customer_id": customer_id, "name": name or f"Customer {customer_id}"})
    return sorted(customers.values(), key=lambda customer: customer["customer_id"])


def list_sites(customer_id: int) -> list[dict[str, Any]]:
    data = _get(f"/api/v1/customer_sites/getSitesByCustomerId/{int(customer_id)}?active_only=true")
    if not isinstance(data, list):
        raise CloudApiError("Site API response is not a list")
    sites = []
    for row in data:
        if not isinstance(row, dict):
            continue
        site_id = row.get("site_id", row.get("id"))
        if site_id is not None:
            sites.append({"site_id": int(site_id), "name": _first_text(row, ("name", "site_name", "display_name")) or f"Site {site_id}"})
    return sorted(sites, key=lambda site: site["site_id"])


def list_site_cameras(site_id: int) -> list[dict[str, Any]]:
    data = _get(f"/api/v1/customer_cameras/getCamerasBySiteId/{int(site_id)}?active_only=true")
    if not isinstance(data, list):
        raise CloudApiError("Camera API response is not a list")
    cameras = []
    for row in data:
        if not isinstance(row, dict):
            continue
        camera_id = row.get("camera_id", row.get("id"))
        if camera_id is not None:
            cameras.append({"camera_id": int(camera_id), "name": _first_text(row, ("camera_name", "name")) or f"Camera {camera_id}", "channel_number": row.get("channel_number")})
    return sorted(cameras, key=lambda camera: (camera["name"].lower(), camera["camera_id"]))
