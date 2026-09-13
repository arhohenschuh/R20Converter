import hashlib
import json
import zipfile
from types import SimpleNamespace

import pytest


INDEX_URL = "https://app.roll20.net/compendium/dnd5e/Test%20Book?expansion=42"
ENTRY_URL = "https://app.roll20.net/compendium/dnd5e/Rules:Test%20Entry?expansion=42"
IMAGE_URL = "https://s3.amazonaws.com/files.d20.io/images/123/test.png"
IMAGE = b"\x89PNG\r\n\x1a\ncompendium-image"


def compendium_archive(tmp_path, change=None):
    members = {}

    def store(name, content):
        payload = content.encode("utf-8") if isinstance(content, str) else content
        members[name] = payload
        return {"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}

    pages = []
    for page_id, title, url, kind, content in [
        ("10", "Test Book", INDEX_URL, "index", '<h2>Rules</h2><a href="%s#details">Entry</a>' % ENTRY_URL),
        ("20", "Test Entry", ENTRY_URL, "entry", '<h2 id="details">Details</h2><p>Book text.</p><img src="%s">' % IMAGE_URL),
    ]:
        prefix = "pages/%s-example/" % page_id
        attributes = [{"name": "Category", "value": "Rules", "html": "Rules"}] if kind == "entry" else []
        pages.append({
            "requestUrl": url, "responseUrl": url, "kind": kind, "outcome": "captured",
            "title": title, "pageId": page_id, "expansion": "42", "attributeCount": len(attributes),
            "links": [] if kind == "index" else [{"href": url, "label": title, "category": "Rules"}],
            "files": [store(prefix + "pagecontent.html", content),
                      store(prefix + "pageattrs.html", '<p>Category: Rules</p>' if attributes else ""),
                      store(prefix + "attributes.json", json.dumps(attributes)),
                      store(prefix + "illustrations.html", "")],
        })
    asset = {"url": IMAGE_URL, "outcome": "bundled", "references": [
        {"page": ENTRY_URL, "attribute": "src", "element": "img"}],
        **store("assets/image.png", IMAGE)}
    source = {"indexUrl": INDEX_URL, "expansion": "42", "title": "Test Book", "pageId": "10"}
    manifest = {"R20Compendium_format": "1.0", "exporter_version": "1.5.0",
                "capture_format": "dom-serialized-html-and-ordered-attributes",
                "scope": "selected-index-and-direct-links", "source": source,
                "pages": pages, "assets": [asset], "excludedLinks": []}
    report = {"format_version": "1.0", "exporter_version": "1.5.0", "status": "complete-within-index",
              "source": source, "scope": "selected-index-and-direct-links", "issues": [], "failures": [],
              "pages": {"planned": 2, "captured": 2, "failed": 0, "cancelled": 0},
              "assets": {"planned": 1, "bundled": 1, "embedded": 0, "failed": 0, "unsupported": 0, "cancelled": 0}}
    if change:
        change(manifest, report, members)
    destination = tmp_path / "compendium.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("compendium.json", json.dumps(manifest))
        archive.writestr("export_report.json", json.dumps(report))
        for name, content in members.items():
            archive.writestr(name, content)
    return destination


def test_reads_exporter_pages_attributes_and_images(tmp_path):
    from compendium_export import CompendiumExport

    archive = CompendiumExport(str(compendium_archive(tmp_path)))

    assert archive.source["title"] == "Test Book"
    assert [page["title"] for page in archive.pages] == ["Test Book", "Test Entry"]
    assert "Book text." in archive.pages[1]["contentHtml"]
    assert archive.pages[1]["attributes"] == [{"name": "Category", "value": "Rules", "html": "Rules"}]
    assert archive.assets[0]["content"] == IMAGE


@pytest.mark.parametrize("defect", ["partial", "hash", "missing"])
def test_rejects_incomplete_or_corrupt_exports(tmp_path, defect):
    from compendium_export import CompendiumExport

    def change(manifest, report, members):
        if defect == "partial":
            report["status"] = "partial"
        elif defect == "hash":
            members["assets/image.png"] = b"changed-image"
        else:
            del members["pages/20-example/pagecontent.html"]

    with pytest.raises(ValueError, match="Compendium export"):
        CompendiumExport(str(compendium_archive(tmp_path, change)))


def campaign_converter(tmp_path, archive, enabled=True, module=False, **options):
    from R20Converter import R20Converter
    from test_conversion_log import _Collector

    system = tmp_path / "foundry/Data/systems/dnd5e"
    system.mkdir(parents=True)
    (system / "system.json").write_text(json.dumps({"id": "dnd5e", "version": "5.3.3", "packs": []}), encoding="utf-8")
    campaign = {
        "campaign_title": "Test Campaign", "release": "legacy", "playerspecificpages": False,
        "playerpageid": None, "turnorder": [], "players": [{"id": "-gm", "d20userid": "1",
            "displayname": "Gamemaster", "color": "#000000", "macrobar": []}],
        "handouts": [{"id": "-note", "name": "Campaign note", "notes": '<a href="%s">Book entry</a>' % ENTRY_URL,
                      "gmnotes": "", "avatar": "", "archived": False, "inplayerjournals": [], "controlledby": []}],
        "journalfolder": ["-note"], "characters": [], "pages": [], "decks": [], "rollabletables": [],
        "tables": [], "jukebox": [], "jukeboxfolder": [], "macros": [], "chat_archive": [],
    }
    source = tmp_path / "campaign.json"
    source.write_text(json.dumps(campaign), encoding="utf-8")
    arguments = dict(path=str(tmp_path / "converted"), zip_file=str(source), json=True, srd_edition="2014",
                     fvtt_data_path=str(tmp_path / "foundry"), export_as_module=module,
                     convert_compendium=enabled, compendium_zip=str(archive) if archive else None)
    arguments.update(options)
    return R20Converter(SimpleNamespace(**arguments), _Collector()), source


@pytest.mark.parametrize("module", [False, True])
def test_campaign_and_compendium_convert_together(tmp_path, module):
    from pathlib import Path
    from entities.base import Entity

    converter, source = campaign_converter(tmp_path, compendium_archive(tmp_path), module=module)
    original_source = source.read_bytes()
    try:
        converter.convert()
    finally:
        converter.closeLog()

    assert source.read_bytes() == original_source
    journals = [entry.entity for entry in converter.journal.entities]
    assert [journal["name"] for journal in journals] == ["Campaign note", "Test Book", "Test Entry"]
    reference = journals[2]
    page = reference["pages"][0]
    prefix = "Compendium.converted.journal." if module else ""
    target = "%sJournalEntry.%s.JournalEntryPage.%s" % (prefix, reference["_id"], page["_id"])
    assert "@UUID[%s]{Book entry}" % target in journals[0]["pages"][0]["text"]["content"]
    assert "@UUID[%s#details]{Entry}" % target in journals[1]["pages"][0]["text"]["content"]
    assert reference["flags"]["R20Converter"]["compendium"]["expansion"] == "42"
    assert "Book text." in page["text"]["content"] and "Category: Rules" in page["text"]["content"]
    image_files = list((Path(converter.path) / "assets").rglob("*.png"))
    assert len(image_files) == 1 and image_files[0].read_bytes() == IMAGE
    assert IMAGE_URL not in page["text"]["content"]
    expected_prefix = "modules/converted/" if module else "worlds/converted/"
    assert expected_prefix in page["text"]["content"]
    assert any(folder.entity["name"] == "Test Book (Compendium)" for folder in converter.folders.entities)
    assert any(folder.entity["name"] == "Rules" and folder.entity["type"] == "JournalEntry"
               for folder in converter.folders.entities)
    assert all(journal["ownership"]["default"] == Entity.OWNERSHIP_NONE for journal in journals)
    if module:
        from module_assembly import ModuleAssembler
        assert ModuleAssembler(converter).buildAdventure()["journal"] == journals
    else:
        saved = [json.loads(line) for line in (Path(converter.path) / "data/journal.db").read_text(encoding="utf-8").splitlines()]
        assert saved == journals


def test_disabled_compendium_ignores_stale_path(tmp_path):
    converter, _source = campaign_converter(tmp_path, "missing.zip", enabled=False)
    try:
        converter.convert()
    finally:
        converter.closeLog()
    assert converter.compendium_export is None
    assert len(converter.journal.entities) == 1


def test_enabled_compendium_requires_path_before_output(tmp_path):
    with pytest.raises(ValueError, match="requires a compendium ZIP path"):
        campaign_converter(tmp_path, None)
    assert not (tmp_path / "converted").exists()


def test_gui_validation_uses_the_archive_contract(tmp_path):
    from GUI import validateCompendiumExport

    result = validateCompendiumExport(str(compendium_archive(tmp_path)))

    assert result == {"valid": True, "error": None, "title": "Test Book", "pages": 2, "images": 1}
    assert validateCompendiumExport("")["valid"] is False
    assert validateCompendiumExport(str(tmp_path / "missing.zip"))["valid"] is False


@pytest.mark.parametrize("defect", ["format", "source", "counts", "traversal", "extra-file", "fragment"])
def test_rejects_invalid_archive_boundaries(tmp_path, defect):
    from compendium_export import CompendiumExport

    def change(manifest, report, members):
        if defect == "format":
            manifest["R20Compendium_format"] = "99"
        elif defect == "source":
            manifest["pages"][1]["expansion"] = "43"
        elif defect == "counts":
            report["pages"]["captured"] = 1
        elif defect == "traversal":
            members["../outside.txt"] = b"outside"
        elif defect == "extra-file":
            members["unlisted.txt"] = b"unlisted"
        else:
            manifest["pages"][1]["files"].pop()

    with pytest.raises(ValueError, match="Compendium export"):
        CompendiumExport(str(compendium_archive(tmp_path, change)))


def test_rejects_duplicate_archive_members(tmp_path):
    from compendium_export import CompendiumExport

    filename = compendium_archive(tmp_path)
    with zipfile.ZipFile(filename, "a") as archive, pytest.warns(UserWarning, match="Duplicate name"):
        archive.writestr("compendium.json", "{}")
    with pytest.raises(ValueError, match="duplicate ZIP member"):
        CompendiumExport(str(filename))


def test_rejects_oversized_archive_before_reading_payloads(tmp_path, monkeypatch):
    from compendium_export import CompendiumExport

    filename = compendium_archive(tmp_path)
    monkeypatch.setattr(CompendiumExport, "MAX_TOTAL_BYTES", 1)
    with pytest.raises(ValueError, match="archive exceeds size limit"):
        CompendiumExport(str(filename))


def replace_fragment(manifest, members, name, text):
    payload = text.encode("utf-8")
    members[name] = payload
    descriptor, = [descriptor for page in manifest["pages"] for descriptor in page["files"] if descriptor["path"] == name]
    descriptor.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def test_imported_html_is_inert_and_preserves_content(tmp_path):
    from bs4 import BeautifulSoup

    def change(manifest, _report, members):
        replace_fragment(manifest, members, "pages/20-example/pagecontent.html",
                         '<script>unsafe()</script><h2 id="details" onclick="unsafe()">Details</h2>'
                         '<a href="javascript:unsafe()">Label</a><a href="#details">Local section</a>'
                         '<table><tr><td colspan="2">Table text</td></tr></table>'
                         '<img src="%s" onerror="unsafe()"><style>body{display:none}</style>' % IMAGE_URL)

    converter, _source = campaign_converter(tmp_path, compendium_archive(tmp_path, change))
    try:
        converter.convert()
    finally:
        converter.closeLog()
    entry = converter.journal.entities[2].entity
    content = entry["pages"][0]["text"]["content"]
    document = BeautifulSoup(content, "html.parser")
    assert not document.find_all(("script", "style"))
    assert all(not any(name.startswith("on") for name in tag.attrs) for tag in document.find_all(True))
    assert "javascript:" not in content and "unsafe()" not in content
    assert "Table text" in content and document.find("td")["colspan"] == "2"
    assert document.find("h2")["id"] == "details"
    assert "#details]{Local section}" in content


def test_missing_declared_image_fails_without_network(tmp_path):
    def change(manifest, _report, members):
        replace_fragment(manifest, members, "pages/20-example/pagecontent.html", '<img src="https://example.invalid/absent.png">')

    converter, _source = campaign_converter(tmp_path, compendium_archive(tmp_path, change))
    try:
        with pytest.raises(ValueError, match="image is not bundled"):
            converter.convert()
    finally:
        converter.closeLog()


def test_reference_links_do_not_cross_expansions(tmp_path):
    from compendium_export import CompendiumExport

    archive = CompendiumExport(str(compendium_archive(tmp_path)))
    converter = SimpleNamespace(name="converted", getArgument=lambda _name, default=None: default)
    content = '<a href="%s">Other book</a><a href="%s#details">Selected book</a>' % (
        ENTRY_URL.replace("expansion=42", "expansion=43"), ENTRY_URL)

    result = archive.rewrite_links(content, converter)

    assert 'expansion=43">Other book</a>' in result
    assert "#details]{Selected book}" in result
    assert result.count("@UUID[") == 1


def test_reference_journals_ignore_item_folder_policy_and_retain_local_images(tmp_path):
    converter, _source = campaign_converter(tmp_path, compendium_archive(tmp_path), module=True,
                                             folder_as_items=["Rules", "Test Book (Compendium)"],
                                             use_original_image_urls=True)
    try:
        converter.convert()
    finally:
        converter.closeLog()
    assert len(converter.journal.entities) == 3
    assert not converter.items.entities
    assert IMAGE_URL not in converter.journal.entities[2].entity["pages"][0]["text"]["content"]


@pytest.mark.parametrize("options,error", [
    ({"module": True, "disable_module_journal": True}, "requires module Journals"),
    ({"game_system": "pf2e"}, "supports dnd5e exports only"),
])
def test_compendium_conflicts_fail_before_creating_output(tmp_path, options, error):
    with pytest.raises(ValueError, match=error):
        campaign_converter(tmp_path, compendium_archive(tmp_path), **options)
    assert not (tmp_path / "converted").exists()


def test_saved_pack_pages_and_adventure_share_reference_ids(tmp_path):
    import plyvel

    converter, _source = campaign_converter(tmp_path, compendium_archive(tmp_path), module=True)
    try:
        converter.convert()
    finally:
        converter.closeLog()
    with plyvel.DB(str(tmp_path / "converted/packs/journal"), create_if_missing=False) as database:
        for entity in converter.journal.entities:
            journal = entity.entity
            stored = json.loads(database.get(("!journal!" + journal["_id"]).encode("utf-8")))
            for page in journal["pages"]:
                assert page["_id"] in stored["pages"]
                saved = json.loads(database.get(("!journal.pages!%s.%s" % (journal["_id"], page["_id"])).encode("utf-8")))
                assert saved == page
    with plyvel.DB(str(tmp_path / "converted/packs/adventure"), create_if_missing=False) as database:
        adventures = [json.loads(value) for _key, value in database.iterator(prefix=b"!adventures!")]
    assert len(adventures) == 1
    assert adventures[0]["journal"] == [entity.entity for entity in converter.journal.entities]


def test_url_identity_matches_exporter_segment_boundaries():
    from compendium_export import CompendiumExport

    identity = CompendiumExport.page_identity
    root = "https://app.roll20.net/compendium/dnd5e/"
    assert identity(root + "Rules:A%2FB?expansion=42", "42") != identity(root + "Rules:A/B?expansion=42", "42")
    assert identity(root + "Rules:Test%20Entry?expansion=42", "42") == identity(root + "Rules:Test Entry#details", "42")


@pytest.mark.parametrize("selection", ["C:/Book-compendium.zip", ""])
def test_compendium_picker_filters_zip_and_handles_cancel(monkeypatch, selection):
    import GUI

    calls = []
    root = SimpleNamespace(wm_attributes=lambda *args: None, withdraw=lambda: None,
                           destroy=lambda: calls.append("destroyed"))
    monkeypatch.setattr(GUI, "useWx", False)
    monkeypatch.setattr(GUI, "Tk", lambda: root)

    def choose(**options):
        assert options["parent"] is root
        assert options["title"] == "Browse Compendium ZIP"
        assert options["filetypes"] == (("ZIP File", "*.zip"),)
        return selection

    monkeypatch.setattr(GUI, "askopenfilename", choose)

    assert GUI.ask_compendium_zip() == (selection or None)
    assert calls == ["destroyed"]