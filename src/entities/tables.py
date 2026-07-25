from .base import DatabaseFile, Entity
import os


class Tables(DatabaseFile):
    def __init__(self, converter):
        DatabaseFile.__init__(self, converter, "tables.db")
        self._tables = RollableTables(converter)
        self._decks = Decks(converter)
        self.entities = self.genEntities()

    def genEntities(self):
        return self._tables.entities + self._decks.entities

class RollableTables(DatabaseFile):
    def __init__(self, converter):
        DatabaseFile.__init__(self, converter, "tables.db")
        self._tables = self._campaign.get("tables", [])
        self.entities = self.genEntities()

    def genEntities(self):
        tables = []
        for index, r20table in enumerate(self._tables):
            table = Table(self, r20table, index, "tables-rollable-tables", True)
            items = r20table["items"]
            # Older exporter was creating an object of {id: item_data}, newer exports the tables and decks as arrays instead
            if isinstance(items, dict):
                items = items.values()
            if not isinstance(items, list):
                items = []
            for item_index, entry in enumerate(items):
                name = entry.get("name", "")
                img = entry.get("avatar", "")
                weight = entry.get("weight", 1)
                try:
                    weight = int(weight)
                except:
                    weight = 1
                if img != "":
                    if not self.getArgument("use_original_image_urls", False):
                        filename = Entity.getImageFilename(os.path.join("tables", "%03d - %s" % (index, r20table["name"])), img, name)
                        if self.getArgument("json", False):
                            (_, img) = table.downloadResource(img, filename)
                        else:
                            zip_filename = Entity.getImageFilename(os.path.join("tables", "%03d - %s" % (index, r20table["name"])), img, "%03d - %s" % (item_index, name))
                            (_, img) = table.copyZipFile(img, zip_filename, filename)
                table.addEntry(name, img, weight)
            tables.append(table)
        return tables

class Decks(DatabaseFile):
    def __init__(self, converter):
        DatabaseFile.__init__(self, converter, "decks.db")
        self._decks = self._campaign.get("decks", [])
        self.entities = self.genEntities()

    def genEntities(self):
        tables = []
        for index, deck in enumerate(self._decks):
            table = Table(self, deck, index, "tables-decks", False)
            cards = deck["cards"]
            # Older exporter was creating an object of {id: item_data}, newer exports the tables and decks as arrays instead
            if isinstance(cards, dict):
                cards = cards.values()
            if not isinstance(cards, list):
                cards = []
            for card_index, card in enumerate(cards):
                name = card.get("name", "")
                img = card.get("avatar", "")
                weight = 1
                drawn = card["id"] in deck["discardPile"]
                if img != "":
                    if not self.getArgument("use_original_image_urls", False):
                        filename = Entity.getImageFilename(os.path.join("decks", "%03d - %s" % (index, deck["name"])), img, name)
                        if self.getArgument("json", False):
                            (_, img) = table.downloadResource(img, filename, type="cards")
                        else:
                            zip_filename = Entity.getImageFilename(os.path.join("decks", "%03d - %s" % (index, deck["name"])), img, "%03d - %s" % (card_index, name))
                            (_, img) = table.copyZipFile(img, zip_filename, filename, type="cards")
                item = self._converter.cards.createItemInventory(card["id"], name, name, "loot", None)
                collection = "{}.cards".format(self._converter.name) if self.getArgument("export_as_module", False) else "Item"
                table.addEntry(name, img, weight, item, collection, drawn)

                item.entity["img"] = img
                item.entity["folder"] = Entity.normalizeID("items-" + deck["id"])
                item.entity["ownership"] = table.entity["ownership"]
                self._converter.cards.addEntity(item)


            tables.append(table)
        return tables

class Table(Entity):
    # Foundry v12 changed CONST.TABLE_RESULT_TYPES from numbers to strings, and
    # v13 merged the former "pack"/COMPENDIUM type into "document" (ADR-005).
    RESULT_TYPE_TEXT = "text"
    RESULT_TYPE_DOCUMENT = "document"
    def __init__(self, database, table, index, parent, with_replacement=True):
        Entity.__init__(self, database, table["id"])
        self.logInfo("Creating Rollable Table : %s" % table["name"])
        permissions = {"default": Table.OWNERSHIP_OWNER if table["showplayers"] else Table.OWNERSHIP_NONE}
        if self.getArgument("export_as_module", False):
            parent = None
        self.entity = {
            "_id": self._id,
            "name": table["name"] or "Unnamed Table",
            "ownership": permissions,
            "folder": Entity.normalizeID(parent),
            "flags": {},
            "sort": index * Entity.SORT_ORDER,
            "formula": "0",
            "replacement": with_replacement,
            "displayRoll": False,
            "results": []
        }

    def addEntry(self, name, img=None, weight=1, entity=None, collection=None, drawn=False):
        minRoll = 1
        for result in self.entity["results"]:
            minRoll = result["range"][1] + 1
        maxRoll = minRoll + weight - 1
        result_type = Table.RESULT_TYPE_DOCUMENT if entity else Table.RESULT_TYPE_TEXT
        entry = {
            "_id": self.genID(),
            "flags": {},
            "type": result_type,
            # v13 replaced the documentCollection/documentId pair with a single
            # document UUID (ADR-005). Text results carry no reference at all.
            "documentUuid": Table.resultUuid(collection, entity) if entity else None,
            # v13 split the old `text` field into `name` (document results) and
            # `description` (plain text results); populating both is harmless.
            "name": name,
            "description": name,
            "img": img,
            "weight": weight,
            "range": [minRoll, maxRoll],
            "drawn": drawn
        }
        self.entity["results"].append(entry)
        self.entity["formula"] = "1d{}".format(maxRoll)
        return entry

    @staticmethod
    def resultUuid(collection, entity):
        """Build the Foundry v13 UUID referenced by a table result.

        `collection` is either a world collection name (e.g. "Item") or a
        compendium key of the form "<packageId>.<packName>". World documents use
        "<Collection>.<id>" while compendium documents use the longer
        "Compendium.<packageId>.<packName>.<DocumentName>.<id>" form.
        """
        if not collection:
            return None
        if "." not in collection:
            return "{}.{}".format(collection, entity._id)
        return Entity.compendiumUuid("{}.{}".format(collection, entity._id), "Item")
