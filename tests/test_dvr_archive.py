from urllib.error import HTTPError
from unittest.mock import patch

import pytest

from agent.dvr_archive import DvrArchiveError, _parse_search_result, _search_xml, search_recordings


def _dvr():
    return {"ip": "192.168.1.6", "username": "admin", "password": "secret", "channels": [1, 2]}


def test_search_xml_uses_the_dvr_basic_schema_in_its_required_order():
    xml = _search_xml(101, "2026-09-28T18:30:00Z", "2026-09-28T19:30:00Z", 5).decode()

    assert xml.index("<searchID>") < xml.index("<trackList>")
    assert xml.index("<trackList>") < xml.index("<timeSpanList>")
    assert xml.index("<maxResults>") < xml.index("<searchResultPostion>")
    assert "//recordType.meta.std-cgi.com" in xml


def test_parse_search_result_returns_only_playable_segments():
    results = _parse_search_result(
        b'''<CMSearchResult><matchList><searchMatchItem><trackID>101</trackID>
        <timeSpan><startTime>2026-09-28T16:20:46Z</startTime><endTime>2026-09-28T19:01:26Z</endTime></timeSpan>
        <mediaSegmentDescriptor><codecType>H.264-BP</codecType><playbackURI>rtsp://192.168.1.6/Streaming/tracks/101/</playbackURI></mediaSegmentDescriptor>
        </searchMatchItem></matchList></CMSearchResult>'''
    )

    assert results == [{
        "track_id": "101",
        "start_time": "2026-09-28T16:20:46Z",
        "end_time": "2026-09-28T19:01:26Z",
        "codec": "H.264-BP",
        "playback_uri": "rtsp://192.168.1.6/Streaming/tracks/101/",
    }]


def test_search_rejects_unconfigured_channel_without_contacting_dvr():
    with pytest.raises(ValueError, match="not configured"):
        search_recordings(_dvr(), 8, "2026-09-28T18:30:00Z", "2026-09-28T19:30:00Z")


def test_search_rejects_an_excessive_time_range():
    with pytest.raises(ValueError, match="24 hours"):
        search_recordings(_dvr(), 1, "2026-09-28T00:00:00Z", "2026-09-30T00:00:00Z")


def test_dvr_http_error_does_not_leak_credentials():
    with patch("agent.dvr_archive.build_opener") as build:
        build.return_value.open.side_effect = HTTPError("http://192.168.1.6", 401, "unauthorized", {}, None)
        with pytest.raises(DvrArchiveError, match="HTTP 401"):
            search_recordings(_dvr(), 1, "2026-09-28T18:30:00Z", "2026-09-28T19:30:00Z")
