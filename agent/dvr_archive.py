"""Read recorded-video metadata from a Hikvision DVR without exposing credentials.

The DVR's archive stays on its own hard disk.  This module only performs the
read-only ISAPI search that returns recording time ranges and playback URIs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm, Request, build_opener
from uuid import uuid4
from xml.etree import ElementTree


_SEARCH_PATH = "/ISAPI/ContentMgmt/search"
_TIMING_METADATA = "//recordType.meta.std-cgi.com"
_MAX_SEARCH_SECONDS = 24 * 60 * 60


class DvrArchiveError(RuntimeError):
    """The DVR could not search its recording archive."""


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("time must use UTC format YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.replace(tzinfo=timezone.utc)


def _element_text(element: ElementTree.Element, name: str) -> str:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == name:
            return (child.text or "").strip()
    return ""


def _search_xml(track_id: int, start_time: str, end_time: str, max_results: int) -> bytes:
    # This is the "basic" CMSearchDescription schema returned by the
    # DS-7108HGHI-K1. Field order matters on older Hikvision DVR firmware.
    root = ElementTree.Element("CMSearchDescription")
    # The DVR accepted the proven payload only with a UUID-shaped search ID.
    # It normalizes that value with braces in the CMSearchResult response.
    ElementTree.SubElement(root, "searchID").text = str(uuid4())
    track_list = ElementTree.SubElement(root, "trackList")
    ElementTree.SubElement(track_list, "trackID").text = str(track_id)
    times = ElementTree.SubElement(root, "timeSpanList")
    span = ElementTree.SubElement(times, "timeSpan")
    ElementTree.SubElement(span, "startTime").text = start_time
    ElementTree.SubElement(span, "endTime").text = end_time
    ElementTree.SubElement(root, "maxResults").text = str(max_results)
    ElementTree.SubElement(root, "searchResultPostion").text = "0"
    metadata = ElementTree.SubElement(root, "metadataList")
    ElementTree.SubElement(metadata, "metadataDescriptor").text = _TIMING_METADATA
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _parse_search_result(payload: bytes) -> list[dict[str, str]]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise DvrArchiveError("DVR returned an invalid archive-search response") from exc

    root_name = root.tag.rsplit("}", 1)[-1]
    if root_name == "ResponseStatus":
        detail = _element_text(root, "statusString") or "DVR rejected the archive search"
        raise DvrArchiveError(detail)
    if root_name != "CMSearchResult":
        raise DvrArchiveError("DVR returned an unexpected archive-search response")

    results: list[dict[str, str]] = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] != "searchMatchItem":
            continue
        time_span = next(
            (child for child in item if child.tag.rsplit("}", 1)[-1] == "timeSpan"),
            None,
        )
        media = next(
            (child for child in item if child.tag.rsplit("}", 1)[-1] == "mediaSegmentDescriptor"),
            None,
        )
        if time_span is None or media is None:
            continue
        playback_uri = _element_text(media, "playbackURI")
        if not playback_uri:
            continue
        results.append(
            {
                "track_id": _element_text(item, "trackID"),
                "start_time": _element_text(time_span, "startTime"),
                "end_time": _element_text(time_span, "endTime"),
                "codec": _element_text(media, "codecType"),
                "playback_uri": playback_uri,
            }
        )
    return results


def search_recordings(
    dvr: dict[str, Any],
    channel: int,
    start_time: str,
    end_time: str,
    max_results: int = 32,
) -> list[dict[str, str]]:
    """Return matching DVR recording segments for one configured channel."""
    if int(channel) not in {int(value) for value in dvr.get("channels") or []}:
        raise ValueError("channel is not configured on this DVR Edge")
    start = _parse_utc(start_time)
    end = _parse_utc(end_time)
    if end <= start:
        raise ValueError("end_time must be after start_time")
    if (end - start).total_seconds() > _MAX_SEARCH_SECONDS:
        raise ValueError("archive search range cannot exceed 24 hours")
    if not 1 <= int(max_results) <= 64:
        raise ValueError("max_results must be between 1 and 64")

    ip = str(dvr.get("ip") or "").strip()
    username = str(dvr.get("username") or "").strip()
    password = str(dvr.get("password") or "")
    if not ip or not username or not password:
        raise DvrArchiveError("DVR archive credentials are not configured")

    url = f"http://{ip}{_SEARCH_PATH}"
    manager = HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None, url, username, password)
    opener = build_opener(HTTPDigestAuthHandler(manager))
    track_id = int(f"{int(channel)}01")
    request = Request(
        url,
        data=_search_xml(track_id, start_time, end_time, int(max_results)),
        headers={"Content-Type": "application/xml; charset=utf-8", "Accept": "application/xml"},
        method="POST",
    )
    try:
        with opener.open(request, timeout=20) as response:
            return _parse_search_result(response.read())
    except HTTPError as exc:
        raise DvrArchiveError(f"DVR archive search returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise DvrArchiveError("DVR archive search could not reach the DVR") from exc
