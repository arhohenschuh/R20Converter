import hashlib
import json
import zipfile

import pytest

from forge_publish import CHUNK_SIZE, package_module, publish, s3_etag


class FakeResponse(object):
    def __init__(self, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class FakeForge(object):
    def __init__(self):
        self.assets = {}
        self.descriptors = {}
        self.base = "https://assets.forge.test/"

    def post(self, url, headers=None, json=None, data=None, files=None):
        assert headers == {"Access-Key": "secret"}
        if url.endswith("/assets/create"):
            descriptor = json["assets"][0]
            path = descriptor["path"]
            if self.descriptors.get(path) == (descriptor["size"], descriptor["etag"]):
                return FakeResponse({"results": [{"url": self.base + path}]})
            return FakeResponse({"results": [{"url": None}]})
        path = data["path"]
        body = files["file"][1].read()
        self.assets[path] = body
        self.descriptors[path] = (len(body), _etag_bytes(body))
        return FakeResponse({"url": self.base + path})

    def get(self, url):
        path = url[len(self.base):]
        return FakeResponse(content=self.assets[path])


def _etag_bytes(body):
    chunks = [body[offset:offset + CHUNK_SIZE]
              for offset in range(0, len(body), CHUNK_SIZE)]
    if len(chunks) <= 1:
        return hashlib.md5(body).hexdigest()
    digests = b"".join(hashlib.md5(chunk).digest() for chunk in chunks)
    return "%s-%d" % (hashlib.md5(digests).hexdigest(), len(chunks))


def make_module(tmp_path):
    module = tmp_path / "test-module"
    module.mkdir()
    (module / "module.json").write_text(json.dumps({
        "id": "test-module", "type": "module", "title": "Test Module",
        "version": "1.2.3"
    }), encoding="utf-8")
    (module / "packs").mkdir()
    (module / "packs" / "data").write_bytes(b"pack data")
    (module / "packs" / "LOCK").write_bytes(b"")
    return module


@pytest.mark.parametrize("size", [0, CHUNK_SIZE, CHUNK_SIZE + 1])
def test_s3_etag_boundaries(tmp_path, size):
    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"x" * size)
    if size <= CHUNK_SIZE:
        expected = hashlib.md5(artifact.read_bytes()).hexdigest()
    else:
        chunks = [hashlib.md5(b"x" * CHUNK_SIZE).digest(), hashlib.md5(b"x").digest()]
        expected = "%s-2" % hashlib.md5(b"".join(chunks)).hexdigest()
    assert s3_etag(artifact) == expected


def test_package_has_single_module_root_and_drops_locks(tmp_path):
    module = make_module(tmp_path)
    archive = package_module(module, tmp_path / "dist" / "test-module-1.2.3.zip")
    with zipfile.ZipFile(str(archive)) as packaged:
        assert sorted(packaged.namelist()) == [
            "test-module/module.json", "test-module/packs/data"]


def test_dry_run_does_not_package_or_require_a_key(tmp_path):
    module = make_module(tmp_path)
    result = publish(module, tmp_path / "dist")
    assert result["apply"] is False
    assert result["zip"] == "foundry-releases/test-module/test-module-1.2.3.zip"
    assert not (tmp_path / "dist").exists()


def test_module_directory_must_match_manifest_id(tmp_path):
    module = make_module(tmp_path)
    module.rename(tmp_path / "wrong-name")
    with pytest.raises(ValueError, match="must be named test-module"):
        publish(tmp_path / "wrong-name", tmp_path / "dist")


def test_apply_uploads_self_updating_archive_and_manifest(tmp_path):
    module = make_module(tmp_path)
    forge = FakeForge()
    result = publish(module, tmp_path / "dist", api_key="secret", apply=True,
                     session=forge)

    assert result["manifest_url"] == (
        "https://assets.forge.test/foundry-releases/test-module/module.json")
    published = json.loads(forge.assets[result["manifest"]].decode("utf-8"))
    assert published["manifest"] == result["manifest_url"]
    assert published["download"] == result["zip_url"]

    archive = tmp_path / "dist" / "test-module-1.2.3.zip"
    with zipfile.ZipFile(str(archive)) as packaged:
        embedded = json.loads(packaged.read("test-module/module.json").decode("utf-8"))
    assert embedded == published