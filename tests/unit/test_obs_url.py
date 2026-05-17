from __future__ import annotations

import pytest

from sdac.obs.url import ParsedObsws, parse_obsws_url


def test_parse_full_url():
    p = parse_obsws_url("obsws://127.0.0.1:4455/secret123")
    assert p == ParsedObsws(host="127.0.0.1", port=4455, password="secret123")


def test_parse_url_without_password():
    p = parse_obsws_url("obsws://example.com:4455")
    assert p.host == "example.com"
    assert p.port == 4455
    assert p.password == ""


def test_parse_url_with_default_port_falls_back_to_4455():
    p = parse_obsws_url("obsws://host/abc")
    assert p.port == 4455
    assert p.password == "abc"


def test_parse_url_rejects_non_obsws_scheme():
    with pytest.raises(ValueError, match="obsws://"):
        parse_obsws_url("https://example.com/secret")


def test_parse_url_rejects_missing_host():
    with pytest.raises(ValueError, match="host"):
        parse_obsws_url("obsws://")
