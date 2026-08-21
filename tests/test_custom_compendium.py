"""Custom compendium package identity regressions."""

import json

from R20Converter import R20Converter


def test_path_based_compendium_uses_manifest_id(tmp_path):
    module = tmp_path / "human-readable-folder"
    packs = module / "packs"
    packs.mkdir(parents=True)
    (module / "module.json").write_text(json.dumps({
        "id": "real-package-id",
        "title": "Display Name",
    }), encoding="utf-8")
    assert R20Converter.customCompendiumId(
        str(packs), str(module)) == "real-package-id"


def test_id_based_compendium_without_manifest_keeps_id(tmp_path):
    packs = tmp_path / "missing-module" / "packs"
    packs.mkdir(parents=True)
    assert R20Converter.customCompendiumId(
        str(packs), "configured-package-id") == "configured-package-id"


def test_declared_rolltable_pack_is_retained_as_a_supplemental_donor():
    table = {"_id": "table00000000001", "name": "Behavior", "formula": "1d10"}
    assert R20Converter.customCompendiumRole(table, "RollTable") == "rolltables"
    assert R20Converter.customCompendiumRole(table, "JournalEntry") is None