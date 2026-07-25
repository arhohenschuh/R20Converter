import json
import os

import foundry
from version import version

#: Default visibility for generated compendium packs. Replaces the pre-v10
#: ``private`` boolean. Players can browse the imported content but only the GM
#: and assistants can modify it, which matches how a converted Roll20 campaign
#: was shared.
DEFAULT_PACK_OWNERSHIP = {
    "PLAYER": "OBSERVER",
    "TRUSTED": "OBSERVER",
    "ASSISTANT": "OWNER",
    "GAMEMASTER": "OWNER",
}

class Module(object):
    def __init__(self, converter):
        self._converter = converter
        self._path = converter.path
        self._name = converter.name
        self._title = converter.getArgument("campaign_title")
        if self._title is None:
            self._title = converter.campaign["campaign_title"]
        self._description = converter.getArgument("description")
        self._packs = []
        
        if len(converter.journal.entities) > 0:
            converter.journal.save()
            self._packs.append(self._newPack("journal", "Handouts", "JournalEntry", "journal.db"))
        if len(converter.actors.entities) > 0:
            converter.actors.save()
            self._packs.append(self._newPack("actors", "Actors", "Actor", "actors.db"))
        if len(converter.items.entities) > 0:
            converter.items.save()
            self._packs.append(self._newPack("items", "Items", "Item", "items.db"))
        if len(converter.scenes.entities) > 0:
            converter.scenes.save()
            self._packs.append(self._newPack("scenes", "Scenes", "Scene", "scenes.db"))
        if len(converter.playlists.entities) > 0:
            converter.playlists.save()
            self._packs.append(self._newPack("playlists", "Jukebox", "Playlist", "playlists.db"))
        if len(converter.tables.entities) > 0:
            converter.tables.save()
            self._packs.append(self._newPack("tables", "Rollable Tables", "RollTable", "tables.db"))
        if len(converter.decks.entities) > 0:
            converter.decks.save()
            self._packs.append(self._newPack("decks", "Decks", "RollTable", "decks.db"))
        if len(converter.cards.entities) > 0:
            converter.cards.save()
            self._packs.append(self._newPack("cards", "Deck Cards", "Item", "cards.db"))


    def _newPack(self, name, label, entity, filename):
        """Build one v13 compendium pack definition (ADR-002).

        ``entity`` was renamed to ``type`` in v10 and removed in v13, and
        ``path`` now names a LevelDB *directory* rather than a NeDB ``.db``
        file, so the extension is stripped here. We still write the ``.db`` file
        itself -- Foundry v13 migrates it into a directory of that name on first
        launch (ADR-003).
        """
        path = os.path.join("packs", os.path.splitext(filename)[0])
        return {"name": name,
                "label": label + " (" + self._title + ")",
                "path": path.replace(os.path.sep, "/"),
                "type": entity,
                "system": self._converter.game_system,
                "ownership": DEFAULT_PACK_OWNERSHIP
            }

    def toDict(self):
        """Build the ``module.json`` manifest in the Foundry v13 schema (ADR-002)."""
        return {"id": self._name,
                "type": foundry.PACKAGE_TYPE_MODULE,
                "title": self._title,
                "description": self._description,
                "version": version,
                "authors": [{"name": foundry.PACKAGE_AUTHOR}],
                "compatibility": foundry.compatibility(),
                "relationships": {
                    "systems": [foundry.systemRelationship(self._converter.game_system,
                                                           self._converter.game_system_version)]
                },
                "packs": self._packs
            } 

    # This is a json file, not a db file, so let's override the __str__ method
    def __str__(self):
        return json.dumps(self.toDict(), indent=2)

    def save(self):
        filename = os.path.join(self._path, "module.json")
        with open(filename, "w", encoding='utf-8') as f:
            f.write(str(self))
        return self