from .base import DatabaseFile, Entity
import os


class Journal(DatabaseFile):
    def __init__(self, converter):
        DatabaseFile.__init__(self, converter, "journal.db")
        self._handouts = self._campaign["handouts"]
        self.entities = self.genEntities()

    def addToFolder(self, folder_id, folder, folder_path):
        handouts = []
        index = 0
        for item in folder:
            if isinstance(item, dict):
                dirname = "%03d - %s" % (index, item["n"])
                handouts.extend(self.addToFolder("handout" + item["id"], item["i"], os.path.join(folder_path, dirname)))
                index += 1
            else:
                handout = self.findID(item, "handout")
                if handout != None:
                    handouts.append(Handout(self, handout, index, folder_id, folder_path))
                    index += 1
                elif self.findID(item, "character") != None:
                    index += 1
                    
        # Look for orphan handouts and add them to the root folder
        if folder_id is None:
            handout_ids = [h.getID(False) for h in handouts]
            zip_index = 0
            zip_path = os.path.join(folder_path, "Orphaned Handouts")
            for handout in self._handouts:
                if handout["id"] not in handout_ids:
                    self.logInfo("Found Orphaned handout, adding to root; ")
                    handouts.append(Handout(self, handout, index, folder_id, folder_path, zip_path, zip_index))
                    index += 1
                    zip_index += 1

        return handouts

    def genEntities(self):
        return self.addToFolder(None, self._campaign["journalfolder"], "journal")

# TODO: handle Archived handouts differently?
class Handout(Entity):
    # CONST.JOURNAL_ENTRY_PAGE_FORMATS: 1 = HTML, 2 = Markdown.
    PAGE_FORMAT_HTML = 1
    PAGE_TYPE_TEXT = "text"
    PAGE_TYPE_IMAGE = "image"

    def __init__(self, database, handout, index, parent, path, zip_path=None, zip_index=None):
        Entity.__init__(self, database, handout["id"])
        self.logInfo("Creating Handout : %s" % handout["name"])
        zip_path = path if zip_path is None else zip_path
        zip_index = index if zip_index is None else zip_index
        content = handout["notes"]
        gmnotes = handout["gmnotes"]
        if gmnotes.strip() != "":
            content += "\n<section class=\"secret\"><p>GM Notes : </p>" + gmnotes + "</section>"
        content = self.replaceCompendiumLinks(self.replaceEntityLinks(content))
        permissions = {"default": Handout.OWNERSHIP_NONE}
        for player in handout.get("inplayerjournals", []):
            if player == "all":
                permissions["default"] = Handout.OWNERSHIP_OBSERVER
            elif player != "":
                player_id = Entity.normalizeID(player)
                permissions[player_id] = Handout.OWNERSHIP_OBSERVER
        for player in handout.get("controlledby", []):
            if player == "all":
                permissions["default"] = Handout.OWNERSHIP_OWNER
            elif player != "":
                player_id = Entity.normalizeID(player)
                permissions[player_id] = Handout.OWNERSHIP_OWNER
        avatar_filename = ""
        if handout["avatar"] != "":
            if self.getArgument("use_original_image_urls", False):
                avatar_filename = handout["avatar"]
            else:
                filename = self.getImageFilename(os.path.join(path, "%03d - %s" % (index, handout["name"])), handout["avatar"], "avatar")
                if self.getArgument("json", False):
                    (_, avatar_filename) = self.downloadResource(handout["avatar"], filename)
                else:
                    zip_filename = self.getImageFilename(os.path.join(zip_path, "%03d - %s" % (zip_index, handout["name"])), handout["avatar"], "avatar")
                    (_, avatar_filename) = self.copyZipFile(handout["avatar"], zip_filename, filename)
        if handout["archived"] and not self.getArgument("disable_archived", False):
            parent = "archived-handouts-folder-id"
        if self.getArgument("export_as_module", False):
            parent = None
        name = handout["name"] or "Handout"
        self.entity = {"_id": self._id,
                       "name": name,
                       "ownership": permissions,
                       "folder": Entity.normalizeID(parent),
                       "flags": {"R20Converter": 
                                 {"handout-order" : index, 
                                  "handout-archived": handout["archived"]}
                                 },
                       "sort": index * Entity.SORT_ORDER,
                       # Foundry v10 replaced the JournalEntry `content` and
                       # `img` fields with an ordered list of pages, and dropped
                       # the migration in 12.316 (ADR-002). A Roll20 handout maps
                       # to at most one text page plus one image page.
                       "pages": self.genPages(name, content, avatar_filename)
                       }

    def genPages(self, name, content, img):
        """Build the v13 `pages` array for a handout.

        Roll20 handouts carry a rich-text body and an optional avatar image, so
        the entry gets a text page and/or an image page. Pages are ordered the
        way Foundry's own v10 migration ordered them: text first, image second.
        An empty handout still needs at least one page, otherwise it opens as a
        blank sheet with no way to add content without editing the world.
        """
        pages = []
        if content.strip() != "" or img == "":
            pages.append(self.genPage(name, Handout.PAGE_TYPE_TEXT, len(pages),
                                      text={"format": Handout.PAGE_FORMAT_HTML,
                                            "content": content}))
        if img != "":
            pages.append(self.genPage(name, Handout.PAGE_TYPE_IMAGE, len(pages),
                                      src=img))
        return pages

    def genPage(self, name, page_type, index, text=None, src=None):
        """Build a single JournalEntryPage document.

        Page ownership defaults to `INHERIT` so that the permissions computed for
        the containing entry apply to its pages, rather than being duplicated on
        every page and drifting out of sync.
        """
        return {
            "_id": self.genID(),
            "name": name,
            "type": page_type,
            "title": {"show": False, "level": 1},
            "image": {},
            "text": text or {"format": Handout.PAGE_FORMAT_HTML, "content": ""},
            "video": {"controls": True, "volume": 0.5},
            "src": src,
            "system": {},
            "sort": index * Entity.SORT_ORDER,
            "ownership": {"default": Handout.OWNERSHIP_INHERIT},
            "flags": {}
        }
