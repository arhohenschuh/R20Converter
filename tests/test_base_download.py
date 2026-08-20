"""Tests for asset downloading in :mod:`entities.base`.

Network access is never performed: :func:`entities.base._resourceSession` is
monkeypatched with a stub session so the resolution-fallback, caching and error
reporting behaviour can be exercised deterministically.
"""

import os

import pytest
import requests

import entities.base as base


class StubResponse(object):
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content


class StubSession(object):
    """Returns canned responses per URL and records the request order."""

    def __init__(self, responses):
        self.responses = responses
        self.requested = []

    def get(self, url, timeout=None):
        self.requested.append(url)
        response = self.responses.get(url)
        if isinstance(response, Exception):
            raise response
        if response is None:
            return StubResponse(404)
        return response


@pytest.fixture
def stub_session(monkeypatch):
    def install(responses):
        session = StubSession(responses)
        monkeypatch.setattr(base, "_resourceSession", lambda: session)
        return session
    return install


@pytest.fixture(autouse=True)
def clear_resource_cache():
    # The cache is class-level state shared by every Entity, so it must not leak
    # between tests.
    base.Entity.resource_cache.clear()
    yield
    base.Entity.resource_cache.clear()


ORIGINAL = "https://s3.amazonaws.com/files.d20.io/images/1/original.png"
MAX = "https://s3.amazonaws.com/files.d20.io/images/1/max.png"
MED = "https://s3.amazonaws.com/files.d20.io/images/1/med.png"
THUMB = "https://s3.amazonaws.com/files.d20.io/images/1/thumb.png"
SOURCE = "https://s3.amazonaws.com/files.d20.io/images/1/thumb.png"

# Roll20 renamed its asset CDN, so each resolution is attempted on the current
# host before the old one (B048).
RENAMED_ORIGINAL = "https://files.d20.io/images/1/original.png"
RENAMED_MAX = "https://files.d20.io/images/1/max.png"
RENAMED_MED = "https://files.d20.io/images/1/med.png"
RENAMED_THUMB = "https://files.d20.io/images/1/thumb.png"


class TestDownloadResource(object):
    def test_successful_download_writes_the_file(self, entity, stub_session):
        stub_session({ORIGINAL: StubResponse(200, b"PNG")})
        dest, config = entity.downloadResource(SOURCE, "scenes/map.png")
        assert open(dest, "rb").read() == b"PNG"
        assert config.endswith("/scenes/map.png")

    def test_requests_carry_a_timeout(self, entity, stub_session):
        captured = {}
        session = stub_session({ORIGINAL: StubResponse(200, b"PNG")})

        original_get = session.get

        def get(url, timeout=None):
            captured["timeout"] = timeout
            return original_get(url, timeout=timeout)

        session.get = get
        entity.downloadResource(SOURCE, "scenes/map.png")
        assert captured["timeout"] == base.DOWNLOAD_TIMEOUT

    def test_falls_back_through_smaller_resolutions(self, entity, stub_session):
        session = stub_session({MED: StubResponse(200, b"PNG")})
        dest, _ = entity.downloadResource(SOURCE, "scenes/map.png")
        assert session.requested == [RENAMED_ORIGINAL, ORIGINAL,
                                     RENAMED_MAX, MAX,
                                     RENAMED_MED, MED]
        assert open(dest, "rb").read() == b"PNG"

    def test_empty_success_falls_back_to_a_non_empty_candidate(self, entity, stub_session):
        session = stub_session({
            RENAMED_ORIGINAL: StubResponse(200, b""),
            ORIGINAL: StubResponse(200, b"PNG"),
        })
        dest, _ = entity.downloadResource(SOURCE, "scenes/map.png")
        assert session.requested == [RENAMED_ORIGINAL, ORIGINAL]
        assert open(dest, "rb").read() == b"PNG"
        assert any("HTTP 200 with empty body" in warning
                   for warning in entity._database.warnings)

    def test_gives_up_after_the_smallest_resolution(self, entity, stub_session):
        session = stub_session({})
        dest, config = entity.downloadResource(SOURCE, "scenes/map.png")
        assert session.requested == [RENAMED_ORIGINAL, ORIGINAL,
                                     RENAMED_MAX, MAX,
                                     RENAMED_MED, MED,
                                     RENAMED_THUMB, THUMB]
        assert dest is None
        assert config == ""

    def test_non_roll20_urls_are_not_degraded(self, entity, stub_session):
        url = "https://example.invalid/picture.png"
        session = stub_session({url: StubResponse(200, b"PNG")})
        entity.downloadResource(url, "scenes/map.png")
        assert session.requested == [url]

    def test_network_errors_are_reported_not_swallowed(self, entity, stub_session):
        stub_session({ORIGINAL: requests.ConnectionError("boom")})
        entity.downloadResource(SOURCE, "scenes/map.png")
        warnings = entity._database.warnings
        assert any("boom" in w for w in warnings)

    def test_http_error_codes_are_reported(self, entity, stub_session):
        stub_session({ORIGINAL: StubResponse(403)})
        entity.downloadResource(SOURCE, "scenes/map.png")
        assert any("HTTP 403" in w for w in entity._database.warnings)

    def test_repeated_urls_are_fetched_only_once(self, entity, stub_session):
        session = stub_session({ORIGINAL: StubResponse(200, b"PNG")})
        first, _ = entity.downloadResource(SOURCE, "scenes/one.png")
        second, _ = entity.downloadResource(SOURCE, "scenes/two.png")
        # Second entity reuses the cache but still gets its own file on disk.
        assert session.requested == [RENAMED_ORIGINAL, ORIGINAL]
        assert first != second
        assert open(second, "rb").read() == b"PNG"

    def test_cache_stores_paths_rather_than_content(self, entity, stub_session):
        stub_session({ORIGINAL: StubResponse(200, b"PNG")})
        dest, _ = entity.downloadResource(SOURCE, "scenes/one.png")
        cached = base.Entity.resource_cache[SOURCE]
        assert cached == dest
        assert os.path.exists(cached)

    def test_stale_cache_entry_falls_back_to_downloading(self, entity, stub_session):
        session = stub_session({ORIGINAL: StubResponse(200, b"PNG")})
        first, _ = entity.downloadResource(SOURCE, "scenes/one.png")
        os.remove(first)
        second, _ = entity.downloadResource(SOURCE, "scenes/two.png")
        assert session.requested == [RENAMED_ORIGINAL, ORIGINAL] * 2
        assert open(second, "rb").read() == b"PNG"

    def test_extension_is_taken_from_the_url(self, entity, stub_session):
        url = "https://example.invalid/picture.jpg?123"
        stub_session({url: StubResponse(200, b"JPG")})
        _, config = entity.downloadResource(url, "scenes/map.png")
        assert config.endswith(".jpg")


class TestResourceSession(object):
    def test_session_is_reused(self):
        assert base._resourceSession() is base._resourceSession()

    def test_retries_are_configured_for_both_schemes(self):
        session = base._resourceSession()
        for scheme in ("http://", "https://"):
            retries = session.get_adapter(scheme).max_retries
            assert retries.total == base.DOWNLOAD_RETRIES
            assert retries.backoff_factor == base.DOWNLOAD_BACKOFF

    def test_client_errors_are_not_retried(self):
        # 404 means "this resolution does not exist"; retrying it would multiply
        # the request count of every conversion for no benefit.
        retries = base._resourceSession().get_adapter("https://").max_retries
        assert 404 not in retries.status_forcelist
        assert 503 in retries.status_forcelist
