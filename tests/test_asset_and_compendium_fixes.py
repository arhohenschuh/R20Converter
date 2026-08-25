"""Regression tests for the asset and compendium defects found rebuilding
*Wardens of the North* (B048, B049, B050).

All three were silent: the conversion exited 0 and the damage only showed up in
the finished world, so each test asserts the observable outcome rather than the
call sequence that produces it. No network access -- the session is stubbed.
"""

import copy
import os
from types import SimpleNamespace

import pytest

import entities.base as base
import entities.journal as journal
import entities.items as items_module
from entities.actors import Actor
from entities.items import Item, ItemActivation

from conftest import FakeDatabase
from test_base_download import StubResponse, StubSession, stub_session, clear_resource_cache  # noqa: F401


S3 = "https://s3.amazonaws.com/files.d20.io/images/1/original.png"
RENAMED = "https://files.d20.io/images/1/original.png"


class TestHostCandidates(object):
    """B048 -- the bucket name is the first path segment, so the current URL is
    recoverable from the old one without a lookup."""

    def test_s3_url_yields_the_renamed_host_first(self):
        assert base.Entity.hostCandidates(S3) == [RENAMED, S3]

    def test_staging_bucket_is_handled_too(self):
        url = "https://s3.amazonaws.com/files.staging.d20.io/images/2/max.png"
        assert base.Entity.hostCandidates(url) == [
            "https://files.staging.d20.io/images/2/max.png", url]

    def test_query_string_is_preserved(self):
        url = "https://s3.amazonaws.com/files.d20.io/images/1/original.png?148418"
        assert base.Entity.hostCandidates(url)[0] == RENAMED + "?148418"

    @pytest.mark.parametrize("url", [
        "https://files.d20.io/images/1/original.png",      # already renamed
        "https://example.invalid/picture.png",             # not Roll20
        "https://s3.amazonaws.com/some-other-bucket/x.png",  # unrelated bucket
    ])
    def test_unrelated_urls_are_left_alone(self, url):
        assert base.Entity.hostCandidates(url) == [url]


class TestHostFallbackRecoversArt(object):
    def test_image_is_recovered_when_only_the_new_host_answers(self, entity, stub_session):
        # The measured production case: the old host 403s for everything.
        session = stub_session({S3: StubResponse(403), RENAMED: StubResponse(200, b"PNG")})
        dest, config = entity.downloadResource(S3, "scenes/map.png")
        assert open(dest, "rb").read() == b"PNG"
        assert session.requested[0] == RENAMED, "the host that answers must be tried first"

    def test_full_resolution_is_not_sacrificed_to_the_rename(self, entity, stub_session):
        # A smaller resolution on the old host must never win over the original
        # on the new one.
        med_old = "https://s3.amazonaws.com/files.d20.io/images/1/med.png"
        stub_session({RENAMED: StubResponse(200, b"BIG"), med_old: StubResponse(200, b"SMALL")})
        dest, _ = entity.downloadResource(S3, "scenes/map.png")
        assert open(dest, "rb").read() == b"BIG"

    def test_genuinely_dead_asset_still_reports_failure(self, entity, stub_session):
        stub_session({})
        dest, config = entity.downloadResource(S3, "scenes/map.png")
        assert dest is None and config == ""


class FakeConverter(object):
    def __init__(self, members, zip_paths=None):
        self._members = members
        self._zip_paths = zip_paths or {}
        self.misses = []

    def getZipFile(self, filename):
        if filename not in self._members:
            raise KeyError(filename)
        return self._members[filename]

    def getZipPathForUrl(self, url):
        return self._zip_paths.get(url)

    def noteZipMiss(self, filename):
        self.misses.append(filename)


class FakeMember(object):
    def __init__(self, content):
        self._content = content

    def read(self):
        return self._content


class TestZipMissFallsBackToDownload(object):
    """B049 -- the export zip is not the only copy of an asset."""

    def test_missing_from_zip_is_downloaded_instead(self, entity, stub_session):
        entity._database._converter = FakeConverter({})
        stub_session({RENAMED: StubResponse(200, b"PNG")})
        dest, config = entity.copyZipFile(S3, "images/gone.png", "scenes/map.png")
        assert dest is not None, "a zip miss must not abandon a recoverable asset"
        assert open(dest, "rb").read() == b"PNG"
        assert config.endswith(".png")

    def test_zip_hit_does_not_hit_the_network(self, entity, stub_session):
        entity._database._converter = FakeConverter({"images/here.png": FakeMember(b"ZIP")})
        session = stub_session({RENAMED: StubResponse(200, b"NET")})
        dest, _ = entity.copyZipFile(S3, "images/here.png", "scenes/map.png")
        assert open(dest, "rb").read() == b"ZIP"
        assert session.requested == []

    def test_miss_with_no_url_still_gives_up(self, entity, stub_session):
        entity._database._converter = FakeConverter({})
        stub_session({})
        dest, config = entity.copyZipFile("", "images/gone.png", "scenes/map.png")
        assert dest is None and config == ""


class TestExportManifestPathWins(object):
    """B053 -- the exporter numbers every sibling in a journal folder, so a path we
    derive ourselves drifts as soon as the campaign holds an entity type we skip.
    When the export ships a manifest, the recorded path is authoritative."""

    def test_manifest_path_is_used_when_derivation_is_wrong(self, entity, stub_session, tmp_path):
        # The asset is in the zip at 007; our derivation says 006, as on Dragoncoast.
        converter = FakeConverter(
            {"journal/007 - Handouts/avatar.png": FakeMember(b"REAL")},
            zip_paths={S3: "journal/007 - Handouts/avatar.png"})
        entity._database._converter = converter
        stub_session({})  # any network use would be a failure
        dest, _ = entity.copyZipFile(S3, "journal/006 - Handouts/avatar.png", "scenes/map.png")
        assert dest is not None
        with open(dest, "rb") as f:
            assert f.read() == b"REAL"
        assert converter.misses == []

    def test_without_a_manifest_the_derived_path_is_still_used(self, entity, stub_session):
        converter = FakeConverter({"journal/006 - Handouts/avatar.png": FakeMember(b"LEGACY")})
        entity._database._converter = converter
        stub_session({})
        dest, _ = entity.copyZipFile(S3, "journal/006 - Handouts/avatar.png", "scenes/map.png")
        with open(dest, "rb") as f:
            assert f.read() == b"LEGACY"

    def test_a_miss_is_counted_so_bulk_drift_is_visible(self, entity, stub_session):
        converter = FakeConverter({})
        entity._database._converter = converter
        stub_session({RENAMED: StubResponse(200, b"PNG")})
        entity.copyZipFile(S3, "journal/006 - Handouts/avatar.png", "scenes/map.png")
        assert converter.misses == ["journal/006 - Handouts/avatar.png"]


class StubHandout(object):
    def __init__(self, database, handout, index, parent, path, zip_path=None, zip_index=None):
        self._id = handout["id"]
        self.index = index
        self.path = path

    def getID(self, normalize=True):
        return self._id


class FakeJournal(object):
    """Just enough of Journal to exercise the folder walk."""

    findID = base.DatabaseFile.findID
    addToFolder = journal.Journal.addToFolder

    def __init__(self, campaign):
        self._campaign = campaign
        self._handouts = campaign["handouts"]

    def logInfo(self, message):
        pass


def campaign(folder, handouts=(), pdfs=(), characters=()):
    return {
        "handouts": [{"id": h, "name": h} for h in handouts],
        "pdfs": [{"id": p} for p in pdfs],
        "characters": [{"id": c} for c in characters],
        "pages": [], "players": [], "jukebox": [],
        "journalfolder": folder,
    }


class TestJournalFolderNumbering(object):
    """B053 -- for legacy exports with no manifest we still derive the path, so the
    walk has to number siblings exactly the way the exporter did."""

    def test_a_pdf_sibling_still_consumes_an_index(self, monkeypatch):
        monkeypatch.setattr(journal, "Handout", StubHandout)
        c = campaign(["h1", "pdf1", "h2"], handouts=["h1", "h2"], pdfs=["pdf1"])
        result = FakeJournal(c).addToFolder(None, c["journalfolder"], "journal")
        assert [h.index for h in result] == [0, 2]

    def test_a_pdf_shifts_later_subfolder_names(self, monkeypatch):
        monkeypatch.setattr(journal, "Handout", StubHandout)
        folder = ["pdf1", {"n": "Handouts", "id": "f1", "i": ["h1"]}]
        c = campaign(folder, handouts=["h1"], pdfs=["pdf1"])
        result = FakeJournal(c).addToFolder(None, folder, "journal")
        assert [h.path for h in result] == [os.path.join("journal", "001 - Handouts")]

    def test_an_unknown_id_is_still_skipped_without_counting(self, monkeypatch):
        # Only types the exporter actually writes may consume an index; a dangling
        # reference must not, or we would re-introduce the drift in the other direction.
        monkeypatch.setattr(journal, "Handout", StubHandout)
        c = campaign(["h1", "ghost", "h2"], handouts=["h1", "h2"])
        result = FakeJournal(c).addToFolder(None, c["journalfolder"], "journal")
        assert [h.index for h in result] == [0, 1]


class StubItem(object):
    def __init__(self, database, handout, index, parent, source, path):
        self.index = index
        self.path = path


class FakeItems(object):
    """Just enough of Items to exercise the folder walk."""

    findID = base.DatabaseFile.findID
    addToFolder = items_module.Items.addToFolder

    def __init__(self, campaign, folders_as_items=("Magic Items",)):
        self._campaign = campaign
        self._handouts = campaign["handouts"]
        self._folders_as_items = list(folders_as_items)

    def getArgument(self, name, default=None):
        return self._folders_as_items if name == "folder_as_items" else default

    def logInfo(self, message):
        pass


class TestItemFolderNumbering(object):
    """B055 -- Items.addToFolder gated its index on is_items_folder, so siblings in an
    ordinary folder never advanced it and every later subfolder path was numbered low.
    Storm's "Magic Items" resolved to 029 while the zip held 074."""

    def test_handouts_in_a_plain_folder_still_consume_an_index(self, monkeypatch):
        monkeypatch.setattr(items_module.Item, "createItemFromHandout", StubItem)
        folder = ["h1", "h2", {"n": "Magic Items", "id": "f1", "i": ["h3"]}]
        c = campaign(folder, handouts=["h1", "h2", "h3"])
        result = FakeItems(c).addToFolder(None, None, folder, "journal")
        assert [i.path for i in result] == [os.path.join("journal", "002 - Magic Items")]

    def test_a_pdf_sibling_still_consumes_an_index(self, monkeypatch):
        monkeypatch.setattr(items_module.Item, "createItemFromHandout", StubItem)
        folder = ["pdf1", {"n": "Magic Items", "id": "f1", "i": ["h1"]}]
        c = campaign(folder, handouts=["h1"], pdfs=["pdf1"])
        result = FakeItems(c).addToFolder(None, None, folder, "journal")
        assert [i.path for i in result] == [os.path.join("journal", "001 - Magic Items")]

    def test_characters_consume_an_index_too(self, monkeypatch):
        monkeypatch.setattr(items_module.Item, "createItemFromHandout", StubItem)
        folder = ["c1", "c2", "c3", {"n": "Magic Items", "id": "f1", "i": ["h1"]}]
        c = campaign(folder, handouts=["h1"], characters=["c1", "c2", "c3"])
        result = FakeItems(c).addToFolder(None, None, folder, "journal")
        assert [i.path for i in result] == [os.path.join("journal", "003 - Magic Items")]

    def test_items_are_still_only_created_inside_an_items_folder(self, monkeypatch):
        # Numbering became unconditional; item *creation* must stay gated.
        monkeypatch.setattr(items_module.Item, "createItemFromHandout", StubItem)
        c = campaign(["h1", "h2"], handouts=["h1", "h2"])
        assert FakeItems(c).addToFolder(None, "Junk", c["journalfolder"], "journal") == []

    def test_an_items_folder_numbers_its_own_handouts(self, monkeypatch):
        monkeypatch.setattr(items_module.Item, "createItemFromHandout", StubItem)
        c = campaign(["h1", "pdf1", "h2"], handouts=["h1", "h2"], pdfs=["pdf1"])
        result = FakeItems(c).addToFolder(None, "Magic Items", c["journalfolder"], "journal")
        assert [i.index for i in result] == [0, 2]

    def test_an_unknown_id_is_still_skipped_without_counting(self, monkeypatch):
        monkeypatch.setattr(items_module.Item, "createItemFromHandout", StubItem)
        c = campaign(["h1", "ghost", "h2"], handouts=["h1", "h2"])
        result = FakeItems(c).addToFolder(None, "Magic Items", c["journalfolder"], "journal")
        assert [i.index for i in result] == [0, 1]


class FakeCompendiumItem(object):
    def __init__(self, entity):
        self.entity = entity


class StubOwnedItem(object):
    def __init__(self, entity):
        self.entity = entity

    def addToOwnedList(self, items):
        items.append(self.entity)
        return self.entity


class StubInventoryItems(object):
    def __init__(self):
        self.source_names = []
        self.replacements = 0

    def createItemInventory(self, identifier, name, description, inventory_type,
                            attributes, activation, attack, specific, **kwargs):
        self.source_names.append(name)
        return StubOwnedItem({
            "_id": "sourceitem000001",
            "name": name,
            "type": inventory_type,
            "img": None,
            "system": {
                "activities": {
                    "sourceAttack0001": {
                        "_id": "sourceAttack0001",
                        "type": "attack",
                    },
                },
                "damage": {"base": {"number": 1, "denomination": 6,
                                      "types": ["bludgeoning"]}},
            },
        })

    def createItemFromCompendium(self, identifier, compendium_item, custom_data):
        self.replacements += 1
        return StubOwnedItem(copy.deepcopy(compendium_item.entity))


class InventoryBoundaryActor(Actor):
    def __init__(self, database, donor=None):
        self._database = database
        self._converter = SimpleNamespace(items=StubInventoryItems())
        self._avatar_filename = "source.webp"
        self._donor = donor
        self.lookups = []
        self.warnings = []

    def findCompendiumItem(self, compendium, name):
        self.lookups.append((compendium, name))
        return self._donor

    def abilityMods(self):
        return {}

    def exportItem(self, item, folder_prefix, force=False):
        pass

    def getName(self):
        return "Fixture Actor"

    def logWarning(self, message):
        self.warnings.append(message)


def _inventory_donor(name, item_type):
    return FakeCompendiumItem({
        "_id": "donoritem0000001",
        "name": name,
        "type": item_type,
        "img": "icons/donor.webp",
        "system": {"activities": {
            "donorUtility001": {"_id": "donorUtility001", "type": "utility"},
        }},
        "_stats": {},
    })


class TestCompendiumTypeBoundary(object):
    """B090 -- a name match cannot erase source mechanics by changing type."""

    def _build(self, tmp_path, donor, name="Shovel"):
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)), donor)
        owned = []
        item = actor.createItemInventory(
            owned, name, "", "weapon", object(), object(), object(), object())
        return actor, item

    def test_equipment_donor_does_not_replace_source_weapon(self, tmp_path):
        actor, item = self._build(tmp_path, _inventory_donor("Shovel", "equipment"))
        assert item["type"] == "weapon"
        assert list(item["system"]["activities"]) == ["sourceAttack0001"]
        assert item["system"]["damage"]["base"]["denomination"] == 6
        assert actor._converter.items.replacements == 0
        assert any("incompatible" in warning.lower() for warning in actor.warnings)

    def test_compatible_weapon_donor_still_enriches(self, tmp_path):
        actor, item = self._build(tmp_path, _inventory_donor("Shovel", "weapon"))
        assert item["type"] == "weapon"
        assert list(item["system"]["activities"]) == ["donorUtility001"]
        assert actor._converter.items.replacements == 1


class TestNPCItemNameNormalization(object):
    """B091 -- source formatting whitespace is not part of an Item name."""

    def test_outer_whitespace_is_removed_before_lookup_and_creation(self, tmp_path):
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)))
        owned = []
        item = actor.createItemInventory(
            owned, "\nDagger (Ranged)\t", "", "weapon",
            object(), object(), object(), object())
        assert actor.lookups == [("Items", "Dagger (Ranged)")]
        assert actor._converter.items.source_names == ["Dagger (Ranged)"]
        assert item["name"] == "Dagger (Ranged)"

    def test_whitespace_only_name_uses_placeholder(self, tmp_path):
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)))
        assert actor.nameOrPlaceholder(" \n\t", "action") == "Unnamed Action"
        assert len(actor.warnings) == 1


class FeatBoundaryItems(object):
    def __init__(self, database):
        self.database = database
        self.replacements = 0

    def createItemFeat(self, identifier, name, description, activation, attack,
                       recharge, **kwargs):
        return Item.createItemFeat(
            self.database, identifier, name, description, activation, attack,
            recharge, **kwargs)

    def createItemFromCompendium(self, identifier, compendium_item, custom_data):
        self.replacements += 1
        return Item.createItemFromCompendium(
            self.database, identifier, compendium_item, custom_data)


class FeatBoundaryActor(InventoryBoundaryActor):
    def __init__(self, database, donor, npc):
        super(FeatBoundaryActor, self).__init__(database, donor)
        self._converter.items = FeatBoundaryItems(database)
        self._npc_fixture = npc

    def isNPC(self):
        return self._npc_fixture


def _hunter_multiattack_donor():
    return FakeCompendiumItem({
        "_id": "hunterMultiattak",
        "name": "Multiattack",
        "type": "feat",
        "img": "icons/hunter.webp",
        "system": {
            "description": {"value": "<p>Hunter 11 class feature.</p>"},
            "activities": {},
        },
        "_stats": {},
    })


class TestNPCClassFeatureBoundary(object):
    """B100 -- NPC actions cannot be replaced by same-name class features."""

    SOURCE = "Sildar makes two Longsword attacks."

    def _build(self, tmp_path, npc):
        database = FakeDatabase(str(tmp_path))
        database._arguments = {"no_compendium_overwrite": True}
        actor = FeatBoundaryActor(database, _hunter_multiattack_donor(), npc)
        owned = []
        item = actor.createItemFeat(
            owned, "Multiattack", self.SOURCE,
            ItemActivation(ItemActivation.ACTION, 1), None, None)
        return actor, item

    def test_npc_multiattack_keeps_source_text_and_utility(self, tmp_path):
        actor, item = self._build(tmp_path, True)
        assert actor.lookups == []
        assert self.SOURCE in item["system"]["description"]["value"]
        assert "Hunter 11" not in item["system"]["description"]["value"]
        assert len(item["system"]["activities"]) == 1
        activity = next(iter(item["system"]["activities"].values()))
        assert activity["type"] == "utility"
        assert activity["activation"] == {
            "type": "action", "value": 1, "condition": "", "override": True}
        assert activity["consumption"]["spellSlot"] is False

    def test_pc_class_feature_lookup_remains_available(self, tmp_path):
        actor, item = self._build(tmp_path, False)
        assert actor.lookups == [("Class Features", "Multiattack")]
        assert item["system"]["description"]["value"] == "<p>Hunter 11 class feature.</p>"
        assert actor._converter.items.replacements == 1


def _class_document():
    return {
        "_id": "compendiumid00000",
        "name": "Cleric",
        "type": "class",
        "img": "icons/cleric.webp",
        "system": {"levels": 1, "description": {"value": "<p>A priestly champion.</p>"},
                   "advancement": [{"type": "HitPoints"}] * 18},
        "_stats": {},
    }


def _spell_document():
    return {
        "_id": "compendiumid00001",
        "name": "Disguise Self",
        "type": "spell",
        "img": "icons/spell.webp",
        "system": {
            "method": "spell",
            "prepared": 0,
            "uses": {"spent": 0, "max": "", "recovery": []},
            "description": {"value": "<p>Compendium description.</p>"},
        },
        "_stats": {},
    }


def _multi_activity_spell_document():
    document = _spell_document()
    document["system"]["activities"] = {
        "mark": {"_id": "mark", "type": "utility",
                 "consumption": {"spellSlot": True, "targets": []}},
        "move": {"_id": "move", "type": "forward",
                 "consumption": {"spellSlot": True, "targets": []}},
    }
    return document


class TestCompendiumKeepsCharacterState(object):
    """B050 -- ``--no-compendium-overwrite`` protects template data, but must not
    discard state that describes one character."""

    def _build(self, database, custom, document=None):
        return Item.createItemFromCompendium(
            database, None, FakeCompendiumItem(document or _class_document()), custom)

    def test_class_level_survives_no_compendium_overwrite(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        item = self._build(entity._database, {"levels": 10})
        assert item.entity["system"]["levels"] == 10

    def test_template_data_still_yields_to_the_compendium(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        item = self._build(entity._database,
                           {"levels": 10, "description": {"value": "<p>Imported from Roll20</p>"}})
        assert item.entity["system"]["description"]["value"] == "<p>A priestly champion.</p>"
        assert len(item.entity["system"]["advancement"]) == 18

    def test_weapon_proficiency_survives(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        weapon = {"_id": "c2", "name": "Longsword", "type": "weapon", "img": None,
                  "system": {"proficient": 0, "equipped": False,
                             "description": {"value": "<p>Versatile.</p>"}},
                  "_stats": {}}
        item = self._build(entity._database, {"proficient": 1, "equipped": True}, weapon)
        assert item.entity["system"]["proficient"] == 1
        assert item.entity["system"]["equipped"] is True

    def test_without_the_flag_everything_is_overwritten(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": False}
        item = self._build(entity._database,
                           {"levels": 10, "description": {"value": "<p>Imported from Roll20</p>"}})
        assert item.entity["system"]["levels"] == 10
        assert item.entity["system"]["description"]["value"] == "<p>Imported from Roll20</p>"

    def test_unknown_keys_are_not_smuggled_through(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        item = self._build(entity._database, {"levels": 10, "spellcasting": {"progression": "full"}})
        assert "spellcasting" not in item.entity["system"]

    @pytest.mark.parametrize("method,prepared,uses", [
        ("innate", 1, {"spent": 0, "max": "1", "recovery": [{"period": "day", "type": "recoverAll"}]}),
        ("atwill", 1, {"spent": 0, "max": "", "recovery": []}),
        ("ritual", 1, {"spent": 0, "max": "", "recovery": []}),
        ("spell", 1, {"spent": 0, "max": "", "recovery": []}),
    ])
    def test_spell_casting_state_survives(self, entity, method, prepared, uses):
        entity._database._arguments = {"no_compendium_overwrite": True}
        custom = {
            "method": method,
            "prepared": prepared,
            "uses": uses,
            "description": {"value": "<p>Imported from Roll20</p>"},
        }
        document = _spell_document()
        if method == "innate" and uses.get("max"):
            target = {"type": "itemUses", "target": "", "value": "1",
                      "scaling": {"mode": "", "formula": ""}}
            custom["activities"] = {
                "source": {"type": "utility", "consumption": {"targets": [target]}},
            }
            document = _multi_activity_spell_document()
        item = self._build(entity._database, custom, document)
        assert item.entity["system"]["method"] == method
        assert item.entity["system"]["prepared"] == prepared
        assert item.entity["system"]["uses"] == uses
        assert item.entity["system"]["description"]["value"] == "<p>Compendium description.</p>"

    def test_limited_innate_use_merges_into_matching_compendium_activity(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "1", "recovery": []},
            "activities": {
                "source": {"type": "utility", "consumption": {"targets": [target]}},
            },
        }
        item = self._build(entity._database, custom, _multi_activity_spell_document())
        activities = item.entity["system"]["activities"]
        assert activities["mark"]["consumption"] == {"spellSlot": True, "targets": [target]}
        assert activities["move"]["consumption"] == {"spellSlot": False, "targets": []}

    def test_limited_innate_uses_canonical_primary_when_donor_types_differ(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "2", "recovery": []},
            "activities": {
                "source": {"type": "utility", "consumption": {"targets": [target]}},
            },
        }
        donor = _spell_document()
        donor["system"]["activities"] = {
            "dnd5eactivity000": {
                "_id": "dnd5eactivity000", "type": "attack",
                "consumption": {"spellSlot": True, "targets": []},
            },
            "dnd5eactivity100": {
                "_id": "dnd5eactivity100", "type": "save",
                "consumption": {"spellSlot": True, "targets": []},
            },
        }
        item = self._build(entity._database, custom, donor)
        activities = item.entity["system"]["activities"]
        assert activities["dnd5eactivity000"]["consumption"] == {
            "spellSlot": True, "targets": [target]}
        assert activities["dnd5eactivity100"]["consumption"] == {
            "spellSlot": False, "targets": []}

    def test_limited_innate_uses_unique_slot_consuming_donor_activity(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "3", "recovery": []},
            "activities": {
                "source": {"type": "save", "consumption": {"targets": [target]}},
            },
        }
        donor = _spell_document()
        donor["system"]["activities"] = {
            "initial": {
                "_id": "initial", "type": "save",
                "consumption": {"spellSlot": True, "targets": []},
            },
            "followup": {
                "_id": "followup", "name": "Concentration Action", "type": "save",
                "consumption": {"spellSlot": False, "targets": []},
            },
        }
        item = self._build(entity._database, custom, donor)
        activities = item.entity["system"]["activities"]
        assert activities["initial"]["consumption"] == {
            "spellSlot": True, "targets": [target]}
        assert activities["followup"]["consumption"] == {
            "spellSlot": False, "targets": []}

    def test_limited_innate_rejects_ambiguous_slot_consuming_activities(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "3", "recovery": []},
            "activities": {
                "source": {"type": "save", "consumption": {"targets": [target]}},
            },
        }
        donor = _spell_document()
        donor["system"]["activities"] = {
            "first": {
                "_id": "first", "type": "save",
                "consumption": {"spellSlot": True, "targets": []},
            },
            "second": {
                "_id": "second", "type": "save",
                "consumption": {"spellSlot": True, "targets": []},
            },
        }
        with pytest.raises(ValueError, match="Cannot select one primary donor activity"):
            self._build(entity._database, custom, donor)

    def test_limited_innate_preserves_alternative_placement_activities(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "1", "recovery": [
                {"period": "day", "type": "recoverAll", "formula": ""},
            ]},
            "activities": {
                "source": {"type": "save", "consumption": {"targets": [target]}},
            },
        }
        donor = _spell_document()
        donor["name"] = "Wall of Fire"
        donor["system"]["activities"] = {
            "saveWallOfFireII": {
                "_id": "saveWallOfFireII", "name": "Place Wall", "type": "save",
                "target": {"template": {"type": "wall", "size": "60"}},
                "consumption": {"spellSlot": True, "targets": []},
            },
            "addPlaceRing1III": {
                "_id": "addPlaceRing1III", "name": "Place Ring", "type": "save",
                "target": {"template": {"type": "cylinder", "size": "10"}},
                "consumption": {"spellSlot": True, "targets": []},
            },
            "addDamage2IIIIII": {
                "_id": "addDamage2IIIIII", "name": "Damage", "type": "damage",
                "consumption": {"spellSlot": False, "targets": []},
            },
        }
        item = self._build(entity._database, custom, donor)
        activities = item.entity["system"]["activities"]
        for activity_id in ("saveWallOfFireII", "addPlaceRing1III"):
            assert activities[activity_id]["consumption"] == {
                "spellSlot": True, "targets": [target]}
        assert activities["addDamage2IIIIII"]["consumption"] == {
            "spellSlot": False, "targets": []}

    def test_limited_innate_preserves_same_template_placement_geometries(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "1", "recovery": [
                {"period": "day", "type": "recoverAll", "formula": ""},
            ]},
            "activities": {
                "source": {"type": "save", "consumption": {"targets": [target]}},
            },
        }
        donor = _spell_document()
        donor["name"] = "Wall of Stone"
        donor["system"]["activities"] = {
            "saveWallOfStonII": {
                "_id": "saveWallOfStonII", "name": "Place Square Panels", "type": "save",
                "target": {"template": {
                    "type": "wall", "count": "10", "size": "10",
                    "width": "0.5", "height": "10", "units": "ft",
                }},
                "consumption": {"spellSlot": True, "targets": []},
            },
            "addPlacLongPane1": {
                "_id": "addPlacLongPane1", "name": "Place Long Panels", "type": "save",
                "target": {"template": {
                    "type": "wall", "count": "10", "size": "20",
                    "width": "0.25", "height": "10", "units": "ft",
                }},
                "consumption": {"spellSlot": True, "targets": []},
            },
        }

        item = self._build(entity._database, custom, donor)
        activities = item.entity["system"]["activities"]

        for activity_id in ("saveWallOfStonII", "addPlacLongPane1"):
            assert activities[activity_id]["consumption"] == {
                "spellSlot": True, "targets": [target]}

    @pytest.mark.parametrize("duplicate", ["name", "geometry"])
    def test_limited_innate_rejects_non_distinct_placement_choices(self, entity, duplicate):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "1", "recovery": []},
            "activities": {
                "source": {"type": "save", "consumption": {"targets": [target]}},
            },
        }
        square = {"type": "wall", "size": "10", "width": "0.5", "height": "10"}
        long = {"type": "wall", "size": "20", "width": "0.25", "height": "10"}
        donor = _spell_document()
        donor["system"]["activities"] = {
            "first": {
                "_id": "first", "name": "Place Square Panels", "type": "save",
                "target": {"template": square},
                "consumption": {"spellSlot": True, "targets": []},
            },
            "second": {
                "_id": "second",
                "name": "Place Square Panels" if duplicate == "name" else "Place Long Panels",
                "type": "save",
                "target": {"template": long if duplicate == "name" else square.copy()},
                "consumption": {"spellSlot": True, "targets": []},
            },
        }

        with pytest.raises(ValueError, match="Cannot select one primary donor activity"):
            self._build(entity._database, custom, donor)

    def test_limited_innate_prefers_cast_over_transform_followup(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        target = {"type": "itemUses", "target": "", "value": "1",
                  "scaling": {"mode": "", "formula": ""}}
        custom = {
            "method": "innate",
            "prepared": 1,
            "uses": {"spent": 0, "max": "1", "recovery": []},
            "activities": {
                "source": {"type": "utility", "consumption": {"targets": [target]}},
            },
        }
        donor = _spell_document()
        donor["system"]["activities"] = {
            "save": {
                "_id": "save", "type": "save",
                "consumption": {"spellSlot": True, "targets": []},
            },
            "transform": {
                "_id": "transform", "name": "Transform", "type": "transform",
                "consumption": {"spellSlot": True, "targets": []},
            },
        }
        item = self._build(entity._database, custom, donor)
        activities = item.entity["system"]["activities"]
        assert activities["save"]["consumption"] == {
            "spellSlot": True, "targets": [target]}
        assert activities["transform"]["consumption"] == {
            "spellSlot": False, "targets": []}

    def test_limited_innate_without_a_positive_consumer_is_rejected(self, entity):
        donor = _multi_activity_spell_document()
        donor["system"].update({
            "method": "innate",
            "uses": {"spent": 0, "max": "1", "recovery": []},
        })
        with pytest.raises(ValueError, match="limited innate spell has no positive item-use consumer"):
            self._build(entity._database, {}, donor)

    @pytest.mark.parametrize("method", ["atwill", "ritual"])
    def test_unlimited_non_slot_method_disables_slot_consumption(self, entity, method):
        entity._database._arguments = {"no_compendium_overwrite": True}
        custom = {
            "method": method,
            "prepared": 1,
            "uses": {"spent": 0, "max": "", "recovery": []},
            "activities": {},
        }
        item = self._build(entity._database, custom, _multi_activity_spell_document())
        assert all(activity["consumption"]["spellSlot"] is False
                   for activity in item.entity["system"]["activities"].values())

    def test_slot_spell_keeps_compendium_consumption(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        custom = {
            "method": "spell",
            "prepared": 1,
            "uses": {"spent": 0, "max": "", "recovery": []},
            "activities": {},
        }
        item = self._build(entity._database, custom, _multi_activity_spell_document())
        assert all(activity["consumption"]["spellSlot"] is True
                   for activity in item.entity["system"]["activities"].values())

    def test_self_use_without_a_pool_is_rejected(self, entity):
        document = _multi_activity_spell_document()
        document["system"]["activities"]["mark"]["consumption"]["targets"] = [{
            "type": "itemUses", "target": "", "value": "1",
            "scaling": {"mode": "", "formula": ""},
        }]
        with pytest.raises(ValueError, match="consumes item uses without a usable pool"):
            self._build(entity._database, {}, document)

    def test_standard_spell_cannot_spend_an_item_use_and_slot(self, entity):
        document = _multi_activity_spell_document()
        document["system"]["uses"]["max"] = "1"
        document["system"]["activities"]["mark"]["consumption"]["targets"] = [{
            "type": "itemUses", "target": "", "value": "1",
            "scaling": {"mode": "", "formula": ""},
        }]
        with pytest.raises(ValueError, match="consumes item uses and a standard spell slot"):
            self._build(entity._database, {}, document)

    def test_negative_item_use_target_can_generate_charges(self, entity):
        document = _multi_activity_spell_document()
        document["system"]["uses"]["max"] = "12"
        document["system"]["activities"]["mark"]["consumption"]["targets"] = [{
            "type": "itemUses", "target": "", "value": "-12",
            "scaling": {"mode": "", "formula": ""},
        }]
        item = self._build(entity._database, {}, document)
        assert item.entity["system"]["activities"]["mark"]["consumption"]["spellSlot"] is True

    def test_non_spell_donor_consumption_is_left_to_donor_qa(self, entity):
        document = _multi_activity_spell_document()
        document["type"] = "loot"
        document["system"].pop("method")
        document["system"]["activities"]["mark"]["consumption"]["targets"] = [{
            "type": "itemUses", "target": "", "value": "1",
            "scaling": {"mode": "", "formula": ""},
        }]
        item = self._build(entity._database, {}, document)
        assert item.entity["type"] == "loot"


class TestPropertiesAlwaysEmitAnArray(object):
    """B051 -- dnd5e 3.0+ calls Array#findSplice on the raw source, so a boolean
    map throws during migration and the item fails validation, reported only as a
    console warning. Guards the normalisation that keeps current output clean."""

    def test_legacy_boolean_map_becomes_an_array_of_set_keys(self):
        import dnd5e
        out = dnd5e.properties({"amm": False, "hvy": True, "fin": False, "two": True})
        assert isinstance(out, list)
        assert set(out) == {"hvy", "two"}

    def test_an_array_passes_through(self):
        import dnd5e
        assert set(dnd5e.properties(["fin", "lgt"])) == {"fin", "lgt"}

    def test_unknown_keys_are_dropped(self):
        # An invalid property fails validation for the whole item.
        import dnd5e
        assert "notAProperty" not in dnd5e.properties({"notAProperty": True, "fin": True})

    def test_empty_input_is_an_array_not_none(self):
        import dnd5e
        for value in ({}, [], None):
            assert dnd5e.properties(value) == []


class TestClassLevelsSumToCharacterLevel(object):
    """The assertion that would have caught B050 in the converter itself: a
    level-1 and a level-4 character share proficiency +2, so proficiency alone
    is not evidence."""

    @staticmethod
    def _levels(attrs):
        classes = {}
        primary = attrs.get("class")
        if primary:
            classes[primary] = int(attrs.get("base_level") or attrs.get("level") or 1)
        for i in (1, 2, 3):
            if str(attrs.get("multiclass%d_flag" % i, "0")) != "1":
                continue
            name = attrs.get("multiclass%d" % i)
            level = int(attrs.get("multiclass%d_lvl" % i) or 0)
            if name and level:
                classes[name] = level
        return classes

    def test_single_class(self):
        attrs = {"class": "Cleric", "base_level": "10", "level": "10",
                 "multiclass1_flag": "0", "multiclass1_lvl": "1"}
        levels = self._levels(attrs)
        assert levels == {"Cleric": 10}
        assert sum(levels.values()) == int(attrs["level"])

    def test_multiclass_uses_the_flag_not_the_default_level(self):
        attrs = {"class": "Rogue", "base_level": "7", "level": "10",
                 "multiclass1_flag": "1", "multiclass1": "Warlock", "multiclass1_lvl": "3",
                 "multiclass2_flag": "0", "multiclass2": "Bard", "multiclass2_lvl": "1"}
        levels = self._levels(attrs)
        assert levels == {"Rogue": 7, "Warlock": 3}
        assert sum(levels.values()) == int(attrs["level"])
