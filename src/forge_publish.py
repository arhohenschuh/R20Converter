#!/usr/bin/python3
"""Package and publish a finished Foundry module through Forge Assets Library."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import requests


FORGE_API = "https://forge-vtt.com/api"
CHUNK_SIZE = 5 * 1024 * 1024
DEFAULT_PREFIX = "foundry-releases"


def s3_etag(path, chunk_size=CHUNK_SIZE):
    """Return the S3-style ETag Forge uses for asset de-duplication."""
    digests = []
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digests.append(hashlib.md5(chunk).digest())
    if len(digests) <= 1:
        return digests[0].hex() if digests else hashlib.md5(b"").hexdigest()
    return "%s-%d" % (hashlib.md5(b"".join(digests)).hexdigest(), len(digests))


def load_module(module_dir):
    module_dir = Path(module_dir).resolve()
    manifest_path = module_dir / "module.json"
    if not manifest_path.is_file():
        raise ValueError("module.json is missing from %s" % module_dir)
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    for field in ("id", "title", "version"):
        if not manifest.get(field):
            raise ValueError("module.json has no %s" % field)
    if manifest.get("type", "module") != "module":
        raise ValueError("module.json does not describe a module")
    if module_dir.name != manifest["id"]:
        raise ValueError("module directory must be named %s" % manifest["id"])
    return module_dir, manifest


def package_module(module_dir, destination, manifest_override=None):
    """Create a ZIP containing one root directory named after the module id."""
    module_dir, manifest = load_module(module_dir)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(destination), "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for source in sorted(module_dir.rglob("*")):
            if not source.is_file() or source.name == "LOCK" or source == destination:
                continue
            relative = source.relative_to(module_dir)
            if manifest_override is not None and relative == Path("module.json"):
                archive.writestr(str(Path(manifest["id"]) / relative),
                                 json.dumps(manifest_override, indent=2) + "\n")
                continue
            archive.write(str(source), str(Path(manifest["id"]) / relative))
    with zipfile.ZipFile(str(destination), "r") as archive:
        names = archive.namelist()
        expected_manifest = "%s/module.json" % manifest["id"]
        if expected_manifest not in names:
            raise RuntimeError("archive verification failed: module.json is absent")
        if any(name.split("/", 1)[0] != manifest["id"] for name in names):
            raise RuntimeError("archive verification failed: more than one root directory")
        if archive.testzip() is not None:
            raise RuntimeError("archive verification failed: corrupt entry")
    return destination


def _response_url(payload):
    if isinstance(payload, dict):
        if payload.get("url"):
            return payload["url"]
        for key in ("results", "result", "assets", "asset"):
            if key in payload:
                found = _response_url(payload[key])
                if found:
                    return found
    elif isinstance(payload, list):
        for value in payload:
            found = _response_url(value)
            if found:
                return found
    return None


class ForgeClient(object):
    def __init__(self, api_key, session=None, api_url=FORGE_API):
        if not api_key:
            raise ValueError("FORGE_API_KEY is not set")
        self.session = session or requests.Session()
        self.api_url = api_url.rstrip("/")
        self.headers = {"Access-Key": api_key}

    def upload(self, local_path, remote_path):
        local_path = Path(local_path)
        descriptor = {"path": remote_path, "size": local_path.stat().st_size,
                      "etag": s3_etag(local_path)}
        response = self.session.post(self.api_url + "/assets/create",
                                     headers=self.headers,
                                     json={"assets": [descriptor]})
        response.raise_for_status()
        existing_url = _response_url(response.json())
        if existing_url:
            return existing_url, False

        with local_path.open("rb") as stream:
            response = self.session.post(self.api_url + "/assets/upload",
                                         headers=self.headers,
                                         data={"path": remote_path},
                                         files={"file": (local_path.name, stream)})
        response.raise_for_status()
        url = _response_url(response.json())
        if not url:
            raise RuntimeError("Forge upload response did not contain an asset URL")
        return url, True

    def verify(self, url, expected):
        response = self.session.get(url)
        response.raise_for_status()
        if response.content != expected:
            raise RuntimeError("published asset differs from the local artifact: %s" % url)


def release_paths(manifest, prefix=DEFAULT_PREFIX):
    root = "%s/%s" % (prefix.strip("/"), manifest["id"])
    return ("%s/%s-%s.zip" % (root, manifest["id"], manifest["version"]),
            "%s/module.json" % root)


def publish(module_dir, output_dir, api_key=None, apply=False, prefix=DEFAULT_PREFIX,
            session=None):
    module_dir, manifest = load_module(module_dir)
    output_dir = Path(output_dir).resolve()
    zip_path = output_dir / ("%s-%s.zip" % (manifest["id"], manifest["version"]))
    zip_remote, manifest_remote = release_paths(manifest, prefix)
    plan = {"module": manifest["id"], "version": manifest["version"],
            "zip": zip_remote, "manifest": manifest_remote, "apply": apply}
    if not apply:
        return plan

    package_module(module_dir, zip_path)
    client = ForgeClient(api_key, session=session)
    zip_url, _ = client.upload(zip_path, zip_remote)

    published = dict(manifest)
    published["download"] = zip_url
    with tempfile.TemporaryDirectory() as temporary:
        temporary_manifest = Path(temporary) / "module.json"
        temporary_manifest.write_text(json.dumps(published, indent=2) + "\n",
                                      encoding="utf-8")
        manifest_url, _ = client.upload(temporary_manifest, manifest_remote)
        published["manifest"] = manifest_url
        package_module(module_dir, zip_path, manifest_override=published)
        final_zip_url, _ = client.upload(zip_path, zip_remote)
        if final_zip_url != zip_url:
            raise RuntimeError("Forge returned an unstable URL for the release archive")
        temporary_manifest.write_text(json.dumps(published, indent=2) + "\n",
                                      encoding="utf-8")
        final_url, _ = client.upload(temporary_manifest, manifest_remote)
        if final_url != manifest_url:
            raise RuntimeError("Forge returned an unstable URL for module.json")
        manifest_bytes = temporary_manifest.read_bytes()

    client.verify(zip_url, zip_path.read_bytes())
    client.verify(final_url, manifest_bytes)
    plan.update({"zip_url": zip_url, "manifest_url": final_url})
    return plan


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", help="finished module directory containing module.json")
    parser.add_argument("--output", default="dist", help="local archive directory")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX,
                        help="Forge Assets Library release prefix")
    parser.add_argument("--apply", action="store_true",
                        help="package, upload, and verify (default: print a dry-run plan)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = publish(args.module, args.output,
                         api_key=os.environ.get("FORGE_API_KEY"),
                         apply=args.apply, prefix=args.prefix)
    except (OSError, ValueError, RuntimeError, requests.RequestException) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())