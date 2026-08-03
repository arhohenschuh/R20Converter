import json
import os
import shutil

import foundry

class World(object):
    def __init__(self, converter):
        self._converter = converter
        self._path = converter.path
        self._name = converter.name
        self._title = converter.getArgument("campaign_title")
        if self._title is None:
            self._title = converter.campaign["campaign_title"]
        self._description = converter.getArgument("description")
        self._copy_templates = len(converter.chat.entities) > 0
            

    def toDict(self):
        """Build the ``world.json`` manifest in the Foundry v13 schema (ADR-002).

        Notable differences from the pre-v10 manifest this used to emit:
        ``id`` replaces ``name``; ``type`` is now required; the
        ``minimumCoreVersion``/``compatibleCoreVersion`` pair is replaced by the
        ``compatibility`` object; ``dependencies`` is replaced by
        ``relationships``. ``resetKeys``/``safeMode`` are dropped -- they are
        launch-time options Foundry manages itself, not manifest fields.
        """
        return {
            "id": self._name,
            "type": foundry.PACKAGE_TYPE_WORLD,
            "title": self._title,
            "description": self._description,
            "version": self._converter.getArgument("package_version", None)
                       or foundry.PACKAGE_VERSION,
            "system": self._converter.game_system,
            # Declares which document schema this world was written with, and so
            # which migrations Foundry runs on first launch. Must stay truthful.
            "coreVersion": foundry.DOCUMENT_SCHEMA_CORE_VERSION,
            "systemVersion": self._converter.game_system_version,
            "compatibility": foundry.compatibility(),
            "authors": [{
                "name": foundry.PACKAGE_AUTHOR,
            }],
            "packs": [],
            "scripts":  ["templates/roll20-templates.js"] if self._copy_templates else [],
            "esmodules": [],
            "styles": ["templates/roll20-templates.css"] if self._copy_templates else [],
            "languages": [],
            "socket": False,
            "flags": {},
            "relationships": {
                "systems": [foundry.systemRelationship(self._converter.game_system,
                                                       self._converter.game_system_version)]
            },
            "protected": False
        }

    # This is a json file, not a db file, so let's override the __str__ method
    def __str__(self):
        return json.dumps(self.toDict(), indent=2)

    def save(self):
        filename = os.path.join(self._path, "world.json")
        with open(filename, "w", encoding='utf-8') as f:
            f.write(str(self))

        if self._copy_templates:
            path = os.path.join(self._path, "templates")
            os.makedirs(path)
            # If running from the windows directory alone, there won't be a 'src' directory anymore
            parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            if not os.path.exists(os.path.join(parent, "templates")):
                parent = os.path.abspath(os.path.join(parent, ".."))
            templates_dir = os.path.join(parent, "templates")
            shutil.copy(os.path.join(templates_dir, "roll20-templates.css"), path)
            shutil.copy(os.path.join(templates_dir, "roll20-templates.js"), path)

        return self