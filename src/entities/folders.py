import json

from .base import DatabaseFile, Entity

class Folders(DatabaseFile):
    #: Schema an explicit scene-folder manifest must declare (ADR-011). Roll20
    #: has no folders for pages, so chapter structure is input, never inferred.
    SCENE_FOLDER_SCHEMA = "r20converter-scene-folders/v1"

    def __init__(self, converter):
        DatabaseFile.__init__(self, converter, "folders.db")
        self._preserve_order = self.getArgument("preserve_folder_order", False)
        self._scene_assignments = {}
        self.entities = self.genEntities()
        self.entities.extend(self.genSceneFolders())

    def forType(self, folder_type):
        """Folder documents of one type, for that type's compendium pack."""
        return [folder.entity for folder in self.entities
                if folder.entity["type"] == folder_type]

    def sceneAssignment(self, page_id):
        """``(folder id, sort)`` the manifest gave a page, or ``None``."""
        return self._scene_assignments.get(page_id)

    def addJournalFolder(self, folder, parent, index, depth=0):
        folders = []
        name = folder["n"].strip()
        is_items_folder = name in self.getArgument("folder_as_items", [])
        has_characters = False
        has_handouts = False
        has_items = is_items_folder
            
        for item in folder["i"]:
            if isinstance(item, dict):
                # Found a folder
                folder_id = folder["id"]
                if depth >= 2:
                    self.logInfo("Folder '%s' has a depth of %d. Dropping it to parent" % (item["n"], depth))
                    folder_id = parent
                (children, child_handouts, child_characters, child_items) = self.addJournalFolder(item, folder_id, index + 1 + len(folders), depth + 1)
                folders.extend(children)
                has_characters |= child_characters
                has_handouts |= child_handouts
                has_items |= child_items
            else:
                if self.findID(item, "character") != None:
                    has_characters = True
                elif self.findID(item, "handout") != None:
                    has_handouts = True
                else:
                    self.logInfo("Unknown ID in Journal folder: %s"  % item)

        # By default, an empty folder would appear in the journal
        if has_handouts or (not has_characters and not has_items):
            has_handouts = True
            folders.append(Folder(self, "handout" + folder["id"], name or "Handouts", "JournalEntry", ("handout" + parent) if parent else None, index))
        if has_characters:
            folders.append(Folder(self, "character" + folder["id"], name or "Characters", "Actor", ("character" + parent) if parent else None, index))
        if has_items:
            folders.append(Folder(self, "item" + folder["id"], name or "Items", "Item", ("item" + parent) if parent else None, index))
        return (folders, has_handouts, has_characters, has_items)

    def ensureFolder(self, id, name, folder_type, parent=None):
        for folder in self.entities:
            if folder.getID(False) == id:
                return folder
        return self.addFolder(id, name, folder_type, parent)

    def addFolder(self, id, name, folder_type, parent=None):
        folder = Folder(self, id, name, folder_type, parent)
        self.entities.append(folder)
        return folder

    def genEntities(self):
        folders = []
        for item in self._campaign["journalfolder"]:
            if isinstance(item, dict):
                (children, _, _, _) = self.addJournalFolder(item, None, len(folders))
                folders.extend(children)

        if not self.getArgument("disable_archived", False):
            for page in self._campaign["pages"]:
                if page["archived"]:
                    folders.append(Folder(self, "archived-scenes-folder-id", "Archived Scenes", "Scene", None, len(folders)))
                    break
            for handout in self._campaign["handouts"]:
                if handout["archived"]:
                    folders.append(Folder(self, "archived-handouts-folder-id", "Archived Handouts", "JournalEntry", None, len(folders)))
                    break
            for character in self._campaign["characters"]:
                if character["archived"]:
                    folders.append(Folder(self, "archived-characters-folder-id", "Archived Actors", "Actor", None, len(folders)))
                    break
            if len(self._campaign.get("tables", [])) > 0:
                folders.append(Folder(self, "tables-rollable-tables", "Rollable Tables", "RollTable", None, len(folders)))
            if len(self._campaign.get("decks", [])) > 0:
                folders.append(Folder(self, "tables-decks", "Decks", "RollTable", None, len(folders)))
                folders.append(Folder(self, "items-decks", "Decks", "Item", None, len(folders)))
                for deck in self._campaign.get("decks", []):
                    folders.append(Folder(self, "items-" + deck["id"], deck["name"], "Item", "items-decks", len(folders)))
        return folders

    def genSceneFolders(self):
        """Scene folders declared by ``--scene-folders`` (ADR-011).

        Every reference must resolve to exactly one page. A name that matches
        nothing, matches twice, or is claimed by two folders aborts the
        conversion: a mis-filed scene is invisible in a module that otherwise
        looks correctly organized.
        """
        path = self.getArgument("scene_folders", None)
        if not path:
            return []
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if manifest.get("schema") != Folders.SCENE_FOLDER_SCHEMA:
            raise ValueError("--scene-folders needs schema '%s', found '%s'"
                             % (Folders.SCENE_FOLDER_SCHEMA, manifest.get("schema")))

        by_id = {}
        by_name = {}
        for page in self._campaign["pages"]:
            by_id[page["id"]] = page
            by_name.setdefault((page["name"] or "").strip(), []).append(page)

        folders = []
        root_id = None
        root_name = (manifest.get("root") or "").strip()
        if root_name:
            root_id = "scene-folder-root"
            folders.append(Folder(self, root_id, root_name, "Scene", None, 0))

        groups = manifest.get("folders", [])
        for index, group in enumerate(groups):
            name = (group.get("name") or "").strip()
            if not name:
                raise ValueError("scene folder %d in the manifest has no name" % index)
            folder_id = "scene-folder-%s" % name
            folders.append(Folder(self, folder_id, name, "Scene", root_id, index))
            for position, reference in enumerate(group.get("scenes", [])):
                self.assignScene(reference, folder_id, position, by_name, by_id)
        for position, reference in enumerate(manifest.get("rootScenes", [])):
            self.assignScene(reference, root_id, len(groups) + position, by_name, by_id)

        assigned = len(self._scene_assignments)
        unplaced = len(by_id) - assigned
        if unplaced:
            self.logInfo("Scene folder manifest placed %d scenes; %d stay at the root"
                         % (assigned, unplaced))
        return folders

    def assignScene(self, reference, folder_id, position, by_name, by_id):
        page = self.resolveScenePage(reference, by_name, by_id)
        if page["id"] in self._scene_assignments:
            raise ValueError("scene folder manifest declares '%s' more than once"
                             % page["name"])
        self._scene_assignments[page["id"]] = (folder_id,
                                               (position + 1) * Entity.SORT_ORDER)

    @staticmethod
    def resolveScenePage(reference, by_name, by_id):
        """The one page a manifest entry names, by Roll20 id or page name."""
        if isinstance(reference, dict) and reference.get("id"):
            identifier = reference["id"]
            if identifier not in by_id:
                raise ValueError("scene folder manifest references unknown page id '%s'"
                                 % identifier)
            return by_id[identifier]
        if isinstance(reference, dict):
            name = (reference.get("name") or "").strip()
        else:
            name = str(reference).strip()
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise ValueError("scene folder manifest reference '%s' matches %d pages"
                             % (name, len(matches)))
        return matches[0]


class Folder(Entity):
    #: Gap between siblings. Wide enough that a folder can be dragged between
    #: two others in Foundry without renumbering the tree.
    SORT_INCREMENT = 100000

    def __init__(self, database, id, name, folder_type, parent, index=None):
        Entity.__init__(self, database, id)
        # TODO: add hierarchy for journal
        #if folder_type == "JournalEntry" and parent is not None:
        #    name = "|_ " + name
        #    parent = None
        self.entity = {"_id": self._id,
                       "name": name,
                       "flags": {},
                       "type": folder_type,
                       "color": "",
                       # Foundry renamed Folder#parent to Folder#folder in v10
                       # and dropped the migration in 12.316 (ADR-002).
                       "folder": Entity.normalizeID(parent),
                       # Foundry defaults Folder#sorting to "a", which re-sorts a
                       # correctly restored tree alphabetically (ADR-010).
                       "sorting": "m",
                       "sort": Folder.SORT_INCREMENT * (1 if index is None else index + 1)
                       }