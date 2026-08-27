from .base import DatabaseFile, Entity
from .actors import FULL_ANGLE, Token

from PIL import Image, ImageFont, ImageDraw

import copy
import html
import io
import json
import os
import math
import time

release = "legacy"
defaultLegacyEnabled = True

class PATH_TYPE:
    POLYGON = 0
    CIRCLE = 1
    RECTANGLE = 2
    FREEHAND = 3

def safeCast(t, v, d):
    try:
        return t(v)
    except:
        return d

class Scenes(DatabaseFile):
    def __init__(self, converter):
        DatabaseFile.__init__(self, converter, "scenes.db")
        self._pages = self._campaign["pages"]
        self.entities = self.genEntities()

    @staticmethod 
    def setRelease(_release):
        global release, defaultLegacyEnabled
        release = _release
        defaultLegacyEnabled = _release != "jumpgate"

    def genEntities(self):
        debug_page = self.getArgument("debug_page", None)
        if debug_page:
            debug_scene = None
            for index, page in enumerate(self._pages):
                if page["name"] == debug_page:
                    debug_scene = Scene(self, page, index, page["id"])
                    break
            return [debug_scene]
        return [Scene(self, page, index, self._campaign["playerpageid"]) for index, page in enumerate(self._pages)]

class Scene(Entity):
    # "isometric" and "dimetric" grids are not supported
    GRID_TYPES = {"square": 1, "hex": 2, "hexr": 4}
    PAD_X = 5
    PAD_Y = 5
    LEGACY_DOOR_COLOR = "#ff9900"

    token_ids = {}
    _auto_doors_warning_emitted = False

    def _mapPinTarget(self, pin):
        link = str(pin.get("link") or "")
        link_type = str(pin.get("linkType") or "")
        if not link or link_type not in ("", "handout"):
            raise ValueError("Map Pin %s has no supported Handout link" %
                             pin.get("id", "unknown"))
        journal = getattr(self._converter, "journal", None)
        target = journal.getById(Entity.normalizeID(link)) if journal is not None else None
        if target is None:
            raise ValueError("Map Pin %s links to missing Handout %s" %
                             (pin.get("id", "unknown"), link))
        pages = target.entity.get("pages", [])
        text_page = next((page for page in pages if page.get("type") == "text"), None)
        if text_page is None:
            raise ValueError("Map Pin %s Handout has no text page" %
                             pin.get("id", "unknown"))
        return target.entity["_id"], text_page["_id"]

    def _mapPinTexture(self, pin):
        label = str(pin.get("iconText") or "")[:3]
        shape = str(pin.get("shape") or "teardrop")
        background = Entity.color(pin.get("bgColor"), "#242424")
        foreground = Entity.color(pin.get("fgColor"), "#ffffff")
        identity = json.dumps({"label": label, "shape": shape,
                               "background": background,
                               "foreground": foreground}, sort_keys=True)
        filename = "%s.svg" % Entity.hashString(identity)
        directory = os.path.join(self._database._path, "assets", "map-pins")
        os.makedirs(directory, exist_ok=True)
        destination = os.path.join(directory, filename)
        if not os.path.exists(destination):
            shapes = {
                "circle": '<circle cx="40" cy="40" r="35" />',
                "diamond": '<path d="M40 3 77 40 40 77 3 40Z" />',
                "square": '<rect x="5" y="5" width="70" height="70" rx="7" />',
                "teardrop": '<path d="M40 3C19 3 5 18 5 38c0 25 35 39 35 39s35-14 35-39C75 18 61 3 40 3Z" />',
            }
            body = shapes.get(shape, shapes["teardrop"])
            escaped = html.escape(label)
            svg = ("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 80 80\">"
                   "<g fill=\"%s\" stroke=\"%s\" stroke-width=\"3\">%s</g>"
                   "<text x=\"40\" y=\"45\" text-anchor=\"middle\" "
                   "font-family=\"Arial,sans-serif\" font-size=\"22\" font-weight=\"700\" "
                   "fill=\"%s\">%s</text></svg>" %
                   (background, foreground, body, foreground, escaped))
            with open(destination, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(svg)
        package_type = "modules" if self.getArgument("export_as_module", False) else "worlds"
        return "%s/%s/assets/map-pins/%s" % (
            package_type, self._converter.name, filename)

    def createMapPinNotes(self, page, margin_left, margin_top, grid_multiplier):
        notes = []
        for index, pin in enumerate(page.get("pins", []) or []):
            pin_id = str(pin.get("id") or "")
            try:
                x = float(pin["x"])
                y = float(pin["y"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Map Pin %s has invalid coordinates" %
                                 (pin_id or "unknown"))
            if not pin_id or not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Map Pin %s has invalid id or coordinates" %
                                 (pin_id or "unknown"))
            entry_id, page_id = self._mapPinTarget(pin)
            scale = safeCast(float, pin.get("scale", 1), 1)
            label = str(pin.get("iconText") or pin.get("title")
                        or pin.get("subLink") or "")[:3]
            notes.append({
                "_id": Entity.normalizeID(pin_id),
                "author": None,
                "entryId": entry_id,
                "pageId": page_id,
                "x": int(round(margin_left + x * grid_multiplier)),
                "y": int(round(margin_top + y * grid_multiplier)),
                "elevation": 0,
                "levels": [],
                "sort": index * 10,
                "locked": True,
                "texture": Entity.texture(self._mapPinTexture(pin), anchor=0.5,
                                            fit="contain"),
                "iconSize": max(32, int(round(40 * max(scale, 0.25)))),
                "text": label,
                "fontFamily": "Signika",
                "fontSize": 32,
                "textAnchor": 1,
                "textColor": "#ffffff",
                "global": True,
                "flags": {"R20Converter": {"mapPin": copy.deepcopy(pin)}},
            })
        return notes

    def __init__(self, database, page, index, active_page):
        Entity.__init__(self, database, page["id"])
        self._page = page

        name = page["name"] if page["name"] != "" else "Untitled"
        # Replace / path characters in the name to avoid issues with os.path.join
        safe_name = name.replace("/", "_").replace(os.path.sep, "_")
        # On windows, if second letter is ':' then it thinks it's a path and os.path.join will ignore the first paths
        # so os.path.join("scenes", "backgrounds", "c:my scene", "image.png") gets written in the root
        if safe_name[1:2] == ":":
            safe_name = safe_name[0] + "_" + safe_name[2:]
        self.logInfo("Creating Scene : %s" % name)
        # Snapping increment gets set to 0 if grid is disabled
        snapping_increment = safeCast(float, page["snapping_increment"], 0)
        orig_grid_size = 70 * (snapping_increment if snapping_increment else 1)
        # Page grid size is hardcoded to 70px in Roll20
        width = 70 * int(safeCast(float, page["width"], 1))
        height = 70 * int(safeCast(float, page["height"], 1))

        # FVTT doesn't allow grid sizes < 50, so we need to double (or triple) everything
        # if that's the case, and adjust our width/height, margins, and tile positions accordingly
        grid_size = orig_grid_size
        grid_multiplier = 1
        if grid_size < 50:
            grid_multiplier = 50.0 / orig_grid_size
            grid_size = 50
        grid_size = int(grid_size)

        padding = self.getArgument("scene_padding", 0.25)
        margin_left = math.ceil(width * grid_multiplier / grid_size * padding) * grid_size
        margin_top = math.ceil(height * grid_multiplier / grid_size * padding) * grid_size
        grid_type = self.GRID_TYPES.get(page["grid_type"], -1)
        if grid_type == -1:
            self.logInfo("Unsupported grid type %s, disabling grid" % page["grid_type"])
            grid_type = 0
        if not page["showgrid"]:
            grid_type = 0
        map_layer = [g for g in page["graphics"] if g["layer"] == "map"]
        map_pin_notes = self.createMapPinNotes(
            page, margin_left, margin_top, grid_multiplier)

        zip_page_path = os.path.join("pages", "%03d - %s" % (index, name))
        bg = None
        bg_image = None
        for m in map_layer:
            if self.getArgument("all_backgrounds_as_tiles", False):
                break
            m_left = safeCast(int, m["left"], 0)
            m_top = safeCast(int, m["top"], 0)
            m_width = safeCast(int, m["width"], 0)
            m_height = safeCast(int, m["height"], 0)
            x = (m_left - (m_width / 2))
            y = (m_top - (m_height / 2))
            if m["imgsrc"] != "" and m_width == width and m_height == height and \
                x == 0 and y == 0 and not m["flipv"] and not m["fliph"]:
                bg = m
                if self.getArgument("use_original_image_urls", False):
                    bg_image = bg["imgsrc"]
                    break
                else:
                    filename = self.getImageFilename(os.path.join(zip_page_path, "graphics"), bg["imgsrc"], bg["id"])
                    dest = self.getImageFilename(os.path.join("scenes", "backgrounds"), bg["imgsrc"], safe_name)
                    if self.getArgument("json", False):
                        (_, bg_image) = self.downloadResource(bg["imgsrc"], dest, type="tiles")
                    else:
                        (_, bg_image) = self.copyZipFile(bg["imgsrc"], filename, dest, type="tiles")
                    if bg_image == "":
                        self.logInfo("Couldn't copy background image for page '%s'" % (name))
                        bg = None
                        bg_image = None
                    else:
                        break
        else:
            if len(map_layer) > 0:
                self.logInfo("Background does not match scene dimensions 100%. Will be set as a tile instead")

        if self.getArgument("use_original_image_urls", False):
            thumb_image = page["thumbnail"]
        else:
            filename = self.getImageFilename(zip_page_path, page["thumbnail"], "thumbnail")
            dest = self.getImageFilename(os.path.join("scenes", "thumbs"), page["thumbnail"], safe_name)
            if self.getArgument("json", False):
                (thumb_filename, thumb_image) = self.downloadResource(page["thumbnail"], dest, type="tiles")
            else:
                (thumb_filename, thumb_image) = self.copyZipFile(page["thumbnail"], filename, dest, type="tiles")
            try:
                generated_filename, generated_image = self.createThumbnail(thumb_filename, dest)
                if generated_filename:
                    thumb_filename = generated_filename
                if generated_image:
                    thumb_image = generated_image
            except Exception as e:
                self.logInfo("Unable to create thumbnail : %s" % e)
        
        map_tiles = []
        objects_tiles = []
        tokens = []
        walls = []
        expected_door_counts = {1: 0, 2: 0}
        lights = []
        drawings = []
        # Some graphics/paths/texts don't appear in the zorder (if drawn by other players?),
        # so let's add them at the end in the order they should appear, map, objects, gm and wall layers.
        ids_to_display = page["zorder"]
        ids_to_display.extend([i["id"] for i in self.filterItems("graphics", "map", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("graphics", "objects", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("graphics", "gmlayer", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("graphics", "walls", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("texts", "map", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("texts", "objects", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("texts", "gmlayer", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("paths", "map", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("paths", "objects", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("paths", "gmlayer", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("paths", "walls", ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("doors", None, ids_to_display)])
        ids_to_display.extend([i["id"] for i in self.filterItems("windows", None, ids_to_display)])

        # Explicit colours always win. Otherwise only Roll20's demonstrated orange
        # convention is inferred; frequency ranking inverted doors and walls on real maps.
        explicit_door_color = self.getArgument("door_color", None)
        explicit_secret_color = self.getArgument("secret_door_color", None)
        door_color = self.normalizeWallStroke(explicit_door_color) if explicit_door_color else None
        secret_door_colors = ([self.normalizeWallStroke(explicit_secret_color)]
                              if explicit_secret_color else [])
        page_has_native_doors = len(page.get("doors", []) or []) > 0
        classify_by_colour = self.shouldClassifyDoorsByColour(page, door_color)
        inferred_door_color = None
        if self.getArgument("auto_doors", False) and not Scene._auto_doors_warning_emitted:
            self.logWarning("--auto-doors is deprecated and no longer enables unsafe "
                            "frequency-based inference; use --door-color for custom campaigns")
            Scene._auto_doors_warning_emitted = True

        if self.getArgument("interactive", False) or classify_by_colour or page_has_native_doors:
            wall_colors = {}
            for zid in ids_to_display:
                path = self.findItemByID(page, zid, "paths")
                if path is None or path["layer"] != "walls":
                    continue
                # Don't check wall color for one way walls
                if path.get("barrierType", "wall") != "wall": 
                    continue
                stroke = self.normalizeWallStroke(path.get("stroke", ""))
                wall_colors.setdefault(stroke, 0)
                if path["path"] is not None:
                    wall_colors[stroke] += len(path["path"]) - 1
                else:
                    wall_colors[stroke] += len(path["points"])

            if page_has_native_doors:
                residue = {color: count for color, count in wall_colors.items()
                           if color != "#0000ff" and count > 0}
                if residue:
                    self.logWarning("Page '%s' has native doors plus unclassified wall-colour "
                                    "residue %s; native doors are preserved and residue remains walls"
                                    % (page.get("name", "Untitled"), residue))

            if wall_colors and (self.getArgument("interactive", False) or classify_by_colour):
                wall_colors_sorted = sorted(wall_colors.items(), key=lambda item: (-item[1], item[0]))
                self.logInfo("In the page, walls are available in these colors : ")
                for index, (color, count) in enumerate(wall_colors_sorted):
                    self.logInfo("%d: %s (%d lines)" % (index + 1, color, count))
                self.logInfo("")
                if self.getArgument("interactive", False):
                    choice = -1
                    while choice < 0 or choice > len(wall_colors):
                        choice = input("Select which color is a door (0 for none) : ")
                        try:
                            choice = int(choice)
                        except ValueError:
                            choice = -1
                    if choice > 0:
                        door_color = wall_colors_sorted[choice-1][0]
                    if len(wall_colors) > 2:
                        choice = -1
                        while choice < 0 and choice > len(wall_colors):
                            choice = input("Select which color is a secret door (0 for none) : ")
                            try:
                                choice = int(choice)
                            except ValueError:
                                choice = -1
                        if choice > 0:
                            secret_door_colors = [wall_colors_sorted[choice-1][0]]
                elif classify_by_colour:
                    inferred_door, inferred_secrets = self.inferDoorColors(page, wall_colors)
                    if inferred_door:
                        door_color = inferred_door
                        inferred_door_color = inferred_door
                        secret_door_colors = inferred_secrets
                        self.logInfo("Door color selected from Roll20's legacy convention: %s"
                                     % door_color)
                    elif len(wall_colors) > 1:
                        self.logWarning("Page '%s' has no native doors and multiple wall colours %s, "
                                        "but no canonical orange; no doors were inferred. "
                                        "Pass --door-color to classify this custom palette."
                                        % (page.get("name", "Untitled"), wall_colors))

        if self.getArgument("add_walls_around_map", False):
            positions = [
                ((0, 0), (width, 0)),
                ((width, 0), (width, height)),
                ((width, height), (0, height)),
                ((0, height), (0, 0))
            ]
            for (x0, x1) in positions:
                wall = {"_id": self.genID(),
                        "flags": {},
                        "c": [
                                int(margin_left + x0[0] * grid_multiplier),
                                int(margin_top + x0[1] * grid_multiplier),
                                int(margin_left + x1[0] * grid_multiplier),
                                int(margin_top + x1[1] * grid_multiplier),
                        ],
                        "move": 20,
                        "light": 20,
                        "sight": 20,
                        "sound": 20,
                        "door": 0,
                        "ds": 0,
                        "dir": 0
                        }
                walls.append(wall)
                
        total_walls = len(walls)
        grouped_door_paths_retained = 0
        grouped_door_segments_retained = 0
        for zid in ids_to_display:
            graphic = self.findItemByID(page, zid, "graphics")
            text = self.findItemByID(page, zid, "texts")
            path = self.findItemByID(page, zid, "paths")
            door = self.findItemByID(page, zid, "doors")
            window = self.findItemByID(page, zid, "windows")
            obj = graphic or text or path or door or window
            if obj is None or (graphic is not None and graphic["imgsrc"] == ""):
                continue
            tile_image = None
            if door or window:
                layer = "walls"
            else:
                layer = obj["layer"]
                left = safeCast(int, obj["left"], 0)
                top = safeCast(int, obj["top"], 0)
                # Jumpgate uses x/y instead of left/top
                x = safeCast(int, obj.get("x", 0), 0)
                y = safeCast(int, obj.get("y", 0), 0)
                if left == 0 and top == 0 and (x != 0 or y != 0):
                    left = x
                    top = y
                tile_width = safeCast(int, obj["width"], 0)
                tile_height = safeCast(int, obj["height"], 0)
                rotation = safeCast(float, obj["rotation"], 0)
            tiles = (map_tiles if layer == "map" else objects_tiles)

            if graphic and layer != "walls" and (bg is None or graphic != bg):
                # The character might have been deleted, but the graphic still represents a token
                char_id = graphic["represents"]
                emits_light = Token.emitsLight(graphic)
                has_status_markers = graphic.get("statusmarkers", "") != ""
                (dradius, lradius) = Token.getLightRadius(graphic)
                shows_name = graphic["showname"] and graphic["name"] != ""
                
                if emits_light:
                    if lradius == 0 and dradius == 0:
                        emits_light = False
                # This is a token, not a tile
                if char_id != "" or emits_light or shows_name or has_status_markers:
                    token = Token(Entity.normalizeID(char_id), "", graphic)
                    token.force_vision = self.getArgument("enable_token_vision", False)
                    # Actors are converted before scenes, so the placed token can
                    # follow its actor rather than defaulting everything hostile.
                    actor = self._converter.actors.getById(token.actor_id)
                    if actor is not None and actor.entity.get("type") == "character":
                        token.disposition = Token.DISPOSITION_FRIENDLY
                    # Redo the dim/bright depending on the token size in this map
                    token.setupLighting(lradius, dradius, 
                                        page["scale_number"], page["scale_units"], orig_grid_size)

                    if self.getArgument("use_original_image_urls", False):
                        token_image = graphic["imgsrc"]
                    else:
                        filename = self.getImageFilename(os.path.join(zip_page_path, "graphics"), graphic["imgsrc"], graphic["id"])
                        dest = self.getImageFilename(os.path.join("scenes", "tokens", safe_name), graphic["imgsrc"], "token_" + str(len(tokens)))
                        if self.getArgument("json", False):
                            (_, token_image) = self.downloadResource(graphic["imgsrc"], dest, type="actors")
                        else:
                            (_, token_image) = self.copyZipFile(graphic["imgsrc"], filename, dest, type="actors")
                    token.token_filename = token_image

                    # We drop the token object and make it into the dict
                    token = token.getDict()
                    bar1_link = graphic["bar1_link"]
                    bar2_link = graphic["bar2_link"]
                    char = self.findID(char_id, "character")
                    if char:
                        hp_id = "unknown"
                        npc = False
                        for attr in char["attributes"]:
                            if attr["name"] == "hp":
                                hp_id = attr["id"]
                            elif attr["name"] == "npc":
                                value = str(attr["current"]).lower()
                                npc = not (value == "0" or value == "" or value == "false" or value == "no")
                        if bar1_link == hp_id or self.getArgument("force_hp_for_token_bar1", False):
                            token["bar1"]["attribute"] = "attributes.hp"
                        if bar2_link == hp_id or self.getArgument("force_hp_for_token_bar2", False):
                            token["bar2"]["attribute"] = "attributes.hp"
                        if not npc:
                            token["actorLink"] = True
                            # A linked token stores no overrides of its own; v13
                            # persists `delta` as null in that case (ADR-002).
                            token["delta"] = None
                    token["_id"] = self.genID()
                    token["hidden"] = (layer == "gmlayer")
                    x = (left - (tile_width / 2))
                    y = (top - (tile_height / 2))
                    token["x"] = int(margin_left + x * grid_multiplier)
                    token["y"] = int(margin_top + y * grid_multiplier)
                    # Token size is in grid units, so we use snapping_increment instead of grid_multiplier
                    token["width"] = token["width"] / (snapping_increment if snapping_increment else 1)
                    token["height"] = token["height"] / (snapping_increment if snapping_increment else 1)
                    # Store the token id mapping for the Combat database
                    page_tokens = self.token_ids.setdefault(page["id"], {})
                    page_tokens[graphic["id"]] = token["_id"]
                    if not self._needsCleanup(x, y, tile_width, tile_height, width, height):
                        tokens.append(token)
                else:
                    if graphic["imgsrc"] == "/images/character.png":
                        tile_image = "icons/svg/mystery-man.svg"
                    elif graphic["imgsrc"] == "/images/dead.png":
                        tile_image = "icons/svg/light.svg"
                    elif self.getArgument("use_original_image_urls", False):
                        tile_image = graphic["imgsrc"]
                    else:
                        filename = self.getImageFilename(os.path.join(zip_page_path, "graphics"), graphic["imgsrc"], graphic["id"])
                        if self.isDrawing(graphic):
                            basename = "drawing_" + str(len(drawings))
                        else:
                            basename = "tile_" + str(len(tiles))
                        dest = self.getImageFilename(os.path.join("scenes", "tiles", safe_name), graphic["imgsrc"], basename)
                        if self.getArgument("json", False):
                            (_, tile_image) = self.downloadResource(graphic["imgsrc"], dest, type="tiles")
                        else:
                            (_, tile_image) = self.copyZipFile(graphic["imgsrc"], filename, dest, type="tiles")
            elif graphic and layer == "walls" and Token.emitsLight(graphic):
                # NOTE: We ignore tokens in the dynamic layer that are not emitting light.
                (dradius, lradius) = Token.getLightRadius(graphic)
                (dim, bright) = Token.computeLighting(lradius, dradius,
                                                      tile_width, tile_height,
                                                      page["scale_number"], page["scale_units"], orig_grid_size)
                if dim > 0 or bright > 0:
                    try:
                        angle = int(Token.lightAngle(graphic))
                    except:
                        angle = FULL_ANGLE
                    try:
                        rotation = graphic["rotation"]
                    except:
                        rotation = 0
                    if angle != FULL_ANGLE:
                        rotation = (rotation + 180) % 360
                    # Foundry v10 moved every AmbientLight emission property into
                    # a nested `config` object and dropped the migration in
                    # 12.316 (ADR-002).
                    light = {"_id": self.genID(),
                             "flags": {},
                             # light object get placed at the center of the graphic
                             "x": int(margin_left + left * grid_multiplier),
                             "y": int(margin_top + top * grid_multiplier),
                             "hidden": False,
                             "rotation": rotation,
                             "walls": True,
                             "vision": False,
                             "config": {
                                "dim": dim,
                                "bright": bright,
                                "angle": angle,
                                "alpha": 0.5,
                                "color": None,
                                "darkness": {"min": 0, "max": 1},
                                "animation": {
                                    "type": None,
                                    "speed": 5,
                                    "intensity": 5,
                                    "reverse": False
                                },
                             },
                             }
                    x = (left - (tile_width / 2))
                    y = (top - (tile_height / 2))
                    # Check if light spills into the scene even if the graphic itself is outside of it
                    if not self._needsCleanup(x, y, tile_width, tile_height, width, height):
                        lights.append(light)
            elif text and text["text"].strip() != "":
                # NOTE: We ignore text items without any text.. there's a lot of those...
                # graphic's left/top position is for the rotation point (center of image)

                if tile_width == 0 or tile_height == 0:
                    (tile_width, tile_height) = self.getTextSize(text["text"], text["font_family"], text["font_size"], rotation)

                x = (left - (tile_width / 2))
                y = (top - (tile_height / 2))
                # Drawing author can't be null or empty string, so give an invalid id instead
                drawing = {"_id": self.genID(),
                            "flags": {},
                            "x": int(margin_left + x * grid_multiplier),
                            "y": int(margin_top + y * grid_multiplier),
                            "elevation": 0,
                            "sort": 10 * len(drawings),
                            "shape": Entity.shape(int(tile_width * grid_multiplier),
                                                  int(tile_height * grid_multiplier)),
                            "rotation": rotation,
                            "hidden": layer == "gmlayer" or layer == "walls",
                            "locked": layer == "map",
                            "author": Entity.normalizeID(text["controlledby"]) or ""
                }
                drawing = self.createTextDrawing(drawing, text)
                drawings.append(drawing)
            elif path and layer != "walls":
                tile_width = tile_width * path["scaleX"]
                tile_height = tile_height * path["scaleY"]
                x = (left - (tile_width / 2))
                y = (top - (tile_height / 2))
                drawing = {"_id": self.genID(),
                            "flags": {},
                            "x": int(margin_left + x * grid_multiplier),
                            "y": int(margin_top + y * grid_multiplier),
                            "elevation": 0,
                            "sort": 10 * len(drawings),
                            "shape": Entity.shape(int(tile_width * grid_multiplier),
                                                  int(tile_height * grid_multiplier)),
                            "rotation": rotation,
                            "hidden": layer == "gmlayer" or layer == "walls",
                            "locked": layer == "map",
                            "author": Entity.normalizeID(path["controlledby"]) or ""
                }
                (drawing, drawing_width, drawing_height) = self.createPathDrawing(drawing, path)
                # Jumpgate uses x,y instead of top/left and a 0,0 width/height, so we need to get the size from the points
                tile_width = drawing_width * path["scaleX"]
                tile_height = drawing_height * path["scaleY"]
                x = (left - (tile_width / 2))
                y = (top - (tile_height / 2))
                points = drawing["shape"]["points"]
                if grid_multiplier != 1:
                    points = [int(p * grid_multiplier) for p in points]
                drawing.update({
                    "x": int(margin_left + x * grid_multiplier),
                    "y": int(margin_top + y * grid_multiplier),
                })
                drawing["shape"].update({
                    "width": int(tile_width * grid_multiplier),
                    "height": int(tile_height * grid_multiplier),
                    "points": points
                })
                drawings.append(drawing)
            elif path and layer == "walls":
                if self.isZeroAreaJumpgateEllipse(path):
                    self.logInfo("Skipping zero-area source ellipse '%s'" %
                                 path.get("id", "unknown"))
                    continue
                # Since Jumpgate, a path's width/height needs to be calculated
                (polygon, path_type, tile_width, tile_height) = self.pathToPolygonList(path, tile_width, tile_height)
                drawing_width = tile_width * path["scaleX"]
                drawing_height = tile_height * path["scaleY"]
                # path's left/top position is for the center of the image
                left = (left - (drawing_width / 2))
                top = (top - (drawing_height / 2))
                barrierType = path.get("barrierType", "wall")
                oneWayReversed = path.get("oneWayReversed", False)
                door_type = self.pathDoorType(
                    path, door_color, secret_door_colors, inferred_door_color)
                if self.pathIsGroupedDoorInferenceExclusion(path, inferred_door_color):
                    grouped_door_paths_retained += 1
                    grouped_door_segments_retained += len(polygon) - 1
                previous_point = None
                previous_point_idx = 0
                total_walls += len(polygon) - 1
                for point_idx, point in enumerate(polygon):
                    # Convert x/y positions according to the scaling factor
                    if path_type == PATH_TYPE.CIRCLE:
                        point = self.transformPathPoint(
                            point, path, drawing_width, drawing_height)
                    else:
                        point = (point[0] * path["scaleX"], point[1] * path["scaleY"])
                    if previous_point is None:
                        previous_point = point
                        previous_point_idx = point_idx
                        continue
                    # Finally, the Pythagore theorem from school is useful in real life
                    wall_length = math.sqrt(math.pow(point[0] - previous_point[0], 2) + math.pow(point[1] - previous_point[1], 2))
                    min_angle = 180.0 - self.getArgument("maximum_wall_angle")
                    #self.logInfo("Wall length : %.2f" % wall_length)
                    if (path_type != PATH_TYPE.CIRCLE
                            and wall_length < self.getArgument("minimum_wall_length", 0)):
                        #self.logInfo("Wall is too small, skipping.")
                        next_idx = point_idx + 1
                        # Don't skip if it's the last point of the polygon
                        if next_idx != len(polygon):
                            next_point = polygon[next_idx]
                            angles = []
                            for idx in range(previous_point_idx + 1, point_idx+1):
                                old_point = (polygon[idx][0] * path["scaleX"], polygon[idx][1] * path["scaleY"])
                                angles.append(self.getPointsAngle(previous_point, old_point, next_point))
                            if min(angles) >= min_angle:
                                continue
                    wall_a = [left + previous_point[0],
                                top + previous_point[1]]
                    wall_b = [left + point[0],
                                top + point[1]]
                    wall = self.createPathWall(
                        path, page, path_type, point_idx - 1, wall_a, wall_b,
                        margin_left, margin_top, grid_multiplier, door_type)
                    if door_type != 0:
                        wall["ds"] = 0
                    wall_x = min(wall_a[0], wall_b[0])
                    wall_y = min(wall_a[1], wall_b[1])
                    wall_width = max(wall_a[0], wall_b[0]) - wall_x
                    wall_height = max(wall_a[1], wall_b[1]) - wall_y
                    if not self._needsCleanup(wall_x, wall_y, wall_width, wall_height, width, height):
                        if door_type:
                            expected_door_counts[door_type] += 1
                        walls.append(wall)
                    previous_point = point
                    previous_point_idx = point_idx
            elif door or window:
                total_walls += 1
                door_type = 0 if window else (2 if door['isSecret'] else 1)
                door_state = 0 if window else (2 if door['isLocked'] else (1 if door['isOpen'] else 0))
                move_restriction = 20 if door else (0 if window['isOpen'] else 20)
                sense_restriction = 0 if window else 20
                x = obj['x']
                y = obj['y'] * -1 # For some reason, x/y is top-left corner, and y is in the negatives
                wall_a = [x - obj['path']['handle0']['x'],
                          y + obj['path']['handle0']['y']] # y is negative when it goes up so negate it 
                wall_b = [x - obj['path']['handle1']['x'],
                          y + obj['path']['handle1']['y']] # y is negative when it goes up so negate it
                wall = {
                    "_id": self.genID(),
                    "flags": {},
                    "c": [
                            int(margin_left + wall_a[0] * grid_multiplier),
                            int(margin_top + wall_a[1] * grid_multiplier),
                            int(margin_left + wall_b[0] * grid_multiplier),
                            int(margin_top + wall_b[1] * grid_multiplier),
                    ],
                    "move": move_restriction,
                    "light": sense_restriction,
                    "sight": sense_restriction,
                    "sound": sense_restriction,
                    "door": door_type,
                    "ds": door_state,
                    "dir": 0
                }
                wall_x = min(wall_a[0], wall_b[0])
                wall_y = min(wall_a[1], wall_b[1])
                wall_width = max(wall_a[0], wall_b[0]) - wall_x
                wall_height = max(wall_a[1], wall_b[1]) - wall_y
                if not self._needsCleanup(wall_x, wall_y, wall_width, wall_height, width, height):
                    if door_type:
                        expected_door_counts[door_type] += 1
                    walls.append(wall)

            if tile_image:
                # graphic's left/top position is for the rotation point (center of image)
                x = (left - (tile_width / 2))
                y = (top - (tile_height / 2))
                if not self._needsCleanup(x, y, tile_width, tile_height, width, height):
                    if self.isDrawing(graphic):
                        drawing = {"_id": self.genID(),
                                    "flags": {
                                        "furnace": {
                                            "fillType": 3,
                                            "textureAlpha": 1,
                                            "mirrorVert": obj["flipv"],
                                            "mirrorHoriz": obj["fliph"],
                                        }
                                    },
                                    "x": int(margin_left + x * grid_multiplier),
                                    "y": int(margin_top + y * grid_multiplier),
                                    "elevation": 0,
                                    "sort": 10 * len(drawings),
                                    "shape": Entity.shape(int(tile_width * grid_multiplier),
                                                          int(tile_height * grid_multiplier)),
                                    "rotation": rotation,
                                    "hidden": layer == "gmlayer" or layer == "walls",
                                    "locked": layer == "map",
                                    "author": Entity.normalizeID(obj["controlledby"]) or "", # invalid user (or export-as-module) will be invalid author, which means all GM
                                    "fillType": 2,
                                    "fillColor": "#ffffff",
                                    "fillAlpha": 0,
                                    "strokeColor": "#ffffff",
                                    "strokeAlpha": 0,
                                    "strokeWidth": 0,
                                    "texture": tile_image,
                                    "fontFamily": "Signika",
                                    "fontSize": 45,
                                    "text": "",
                                    "textAlpha": 1,
                                    "textColor": "#ffffff",
                                    "bezierFactor": 0,
                                }
                        drawings.append(drawing)
                    else:
                        # v9 expressed a flip as a negative width/height. v13
                        # requires both to be positive and takes the mirroring
                        # from the texture scale instead (ADR-002).
                        tile = {
                            "_id": self.genID(),
                            "flags": {},
                            "texture": Entity.texture(tile_image,
                                                      scale_x=-1 if graphic["fliph"] else 1,
                                                      scale_y=-1 if graphic["flipv"] else 1,
                                                      anchor=0.5,
                                                      alpha_threshold=0.75),
                            "width": int(tile_width * grid_multiplier),
                            "height": int(tile_height * grid_multiplier),
                            "x": int(margin_left + x * grid_multiplier),
                            "y": int(margin_top + y * grid_multiplier),
                            # v12 replaced the Tile `z` index with `sort`, and
                            # `overhead`/`roof` with `elevation`/`restrictions`.
                            "elevation": 0,
                            "sort": 10 * len(tiles),
                            "rotation": rotation,
                            "locked": layer == "map",
                            "hidden": layer == "gmlayer" or layer == "walls",
                            "alpha": 1,
                            "restrictions": {
                                "light": False,
                                "weather": False
                            },
                            "occlusion": {
                                "mode": 1,
                                "alpha": 0
                            },
                            "video": {
                                "loop": True,
                                "autoplay": True,
                                "volume": 0
                            }
                        }
                        tiles.append(tile)
                
                    
        page_name = page.get("name", "Untitled")
        actual_door_counts = self.assertDoorConservation(
            walls, expected_door_counts, page_name)
        if grouped_door_paths_retained:
            self.logWarning(
                "Page '%s' retained %d grouped canonical-orange paths (%d segments) "
                "as walls instead of automatically inferring doors; explicit --door-color "
                "still overrides this safeguard."
                % (page_name, grouped_door_paths_retained, grouped_door_segments_retained))
        self.logInfo(
            "Scene barrier summary for '%s': %d walls, %d ordinary doors, %d secret doors, "
            "%d native door objects, %d grouped inferred-door segments retained as walls."
            % (page_name, len(walls), actual_door_counts[1], actual_door_counts[2],
               len(page.get("doors", []) or []), grouped_door_segments_retained))
        if len(walls) != total_walls:
            self.logInfo("With a minimum wall length of %d pixels and a maximum angle between continuous walls of %d degrees, the total number of walls was decreased from %d to %d walls." % (self.getArgument("minimum_wall_length", 0), self.getArgument("maximum_wall_angle", 0), total_walls, len(walls)))
        tiles = map_tiles + objects_tiles

        folder = None
        sort = page.get("placement", 0) * Entity.SORT_ORDER
        if page["archived"] and not self.getArgument("disable_archived", False):
            folder = "archived-scenes-folder-id"
        # Roll20 has no folders for pages, so grouping is declared, not derived
        # (ADR-011). Unassigned pages keep their Roll20 placement order.
        folders = getattr(self._converter, "folders", None)
        assignment = folders.sceneAssignment(page["id"]) if folders else None
        if assignment is not None:
            (folder, sort) = assignment

        if release == "jumpgate":
            globalLight = page.get("daylight_mode_enabled", False)
        else:
            globalLight = page.get("lightglobalillum", False)
        # A converted map is expected to be ready for token-based play. Foundry
        # ignores every token's sight settings when Scene token vision is off.
        tokenVision = True
        # Foundry 14 stores fog exploration as an enum: 0=None, 1=Individual,
        # 2=Shared. The removed `fog.exploration` boolean migrates to 0, which
        # silently disables exploration even when Roll20 Advanced Fog was on.
        disableFog = (self.getArgument("disable_fog", False)
                      and not self.getArgument("export_as_module", False))
        fogMode = 0 if disableFog else 1
        self.entity = {"_id": self._id,
                       "name": name or "Unnamed Scene",
                       "navName": name,
                       "ownership": {"default": 0},
                       "folder": Entity.normalizeID(folder),
                       "flags": {},
                       "sort": sort,
                       "navOrder": page.get("placement", 0),
                       "navigation": not page["archived"],
                       "active": active_page == page["id"],
                       # Foundry v10 folded the scene image and its offsets into
                       # a TextureData object; the migration was dropped in
                       # 12.316 (ADR-002).
                       "background": Entity.texture(bg_image),
                       "foreground": None,
                       "initial": None,
                       "thumb": thumb_image,
                       "width": int(width * grid_multiplier),
                       "height": int(height * grid_multiplier),
                       "padding": padding,
                       "backgroundColor": self.color(page["background_color"]),
                       # Likewise the seven flat grid* fields became one object.
                       "grid": {
                           "type": grid_type,
                           "size": grid_size,
                           "style": "solidLines",
                           "thickness": 1,
                           "color": self.color(page["gridcolor"]),
                           "alpha": page["grid_opacity"],
                           "distance": page["scale_number"] if float(page["scale_number"]) >= 1 else 1,
                           "units": page["scale_units"] if float(page["scale_number"]) >= 1 else ("(" + str(page["scale_number"]) + " " + page["scale_units"] + ")"),
                       },
                       "tokenVision": tokenVision,
                       # v12 grouped the fog and lighting settings. Emit the
                       # current Foundry 14 shape directly.
                       "fog": {
                           "reset": int(time.time() * 1000),
                           "mode": fogMode,
                           "colors": {
                               "explored": None,
                               "unexplored": None,
                           },
                       },
                       "environment": {
                           "darknessLevel": 0,
                           "globalLight": {
                               "enabled": globalLight,
                               "darkness": {"min": 0, "max": 1},
                           },
                       },
                       "tiles": tiles,
                       "tokens": tokens,
                       "walls": walls,
                       "lights": lights,
                       "drawings": drawings,
                       "sounds": [],
                       "templates": [],
                       "notes": map_pin_notes,
                       "playlist": None,
                       "playlistSound": None,
                       "journal": None,
                       "weather": "",
                              "_stats": self.documentStats(),
                    }

    def filterItems(self, type, layer=None, exclude=None):
        return [i for i in self._page.get(type, []) if (layer is None or i["layer"] == layer) and (exclude is None or i["id"] not in exclude)]

    @staticmethod
    def findItemByID(page, id, type):
        for g in page.get(type, []):
            if g["id"] == id:
                return g
        return None

    def _needsCleanup(self, x, y, obj_width, obj_height, width, height):
        if not self.getArgument("cleanup_scenes", False):
            return False
        if x + obj_width < 0 or x > width or y + obj_height < 0 or y > height:
            return True
        return False

    @staticmethod
    def normalizeWallStroke(stroke):
        """Return a canonical comparison token while preserving non-colour sentinels."""
        if not isinstance(stroke, str):
            return ""
        token = stroke.strip().lower()
        return Entity.color(token, default=token)

    def shouldClassifyDoorsByColour(self, page, door_color):
        """Whether this page is eligible for conservative legacy-door inference.

        The page says which encoding it uses, so the caller does not have to. Roll20's
        legacy dynamic lighting had no door objects -- a door was a wall drawn in a
        different colour -- while Jumpgate/UDL pages carry real ``doors``.

        This used to require ``--auto-doors``, which the GUI defaulted on and the CLI
        defaulted off, so the same campaign kept or lost its doors depending on which
        one you ran (B058). The official-module baseline has 155 legacy-colour pages
        among 314 walled pages.

        Classifying a page that *already* has door objects is the other half of the
        problem: on *Dungeon of the Mad Mage*'s Crystal Labyrinth it would turn 39
        green and 1 black wall segments into secret doors. So a page with native doors
        is left alone and its residue is reported; one campaign can legitimately mix
        both -- that module's Twisted Caverns has no door objects and 12 orange
        segments that are doors.
        """
        if self.getArgument("no_auto_doors", False):
            return False
        if door_color is not None:
            return False
        return not (page.get("doors") or [])

    def inferDoorColors(self, page, wall_colors):
        """Return the conservative inferred ordinary and secret door colours."""
        if not self.shouldClassifyDoorsByColour(page, None):
            return (None, [])
        normalized = {self.normalizeWallStroke(color) for color in wall_colors}
        if self.LEGACY_DOOR_COLOR in normalized:
            return (self.LEGACY_DOOR_COLOR, [])
        return (None, [])

    @staticmethod
    def pathIsGrouped(path):
        """Whether Roll20 declares a wall path as part of a grouped assembly."""
        group = path.get("groupwith")
        if isinstance(group, str):
            return bool(group.strip())
        if isinstance(group, (list, tuple, set)):
            return bool(group)
        return group is not None and group is not False

    def pathDoorType(self, path, door_color, secret_door_colors,
                     inferred_door_color=None):
        """Classify one source path without turning grouped machinery into doors."""
        if path.get("barrierType", "wall") != "wall":
            return 0
        stroke = self.normalizeWallStroke(path.get("stroke", ""))
        if stroke in secret_door_colors:
            return 2
        if stroke != door_color:
            return 0
        if self.pathIsGroupedDoorInferenceExclusion(path, inferred_door_color):
            return 0
        return 1

    def pathIsGroupedDoorInferenceExclusion(self, path, inferred_door_color):
        """Whether an inferred door candidate is grouped wall machinery."""
        return bool(inferred_door_color
                    and path.get("barrierType", "wall") == "wall"
                    and self.normalizeWallStroke(path.get("stroke", "")) == inferred_door_color
                    and self.pathIsGrouped(path))

    @staticmethod
    def assertDoorConservation(walls, expected, page_name):
        """Fail when classified post-cleanup doors differ from emitted doors."""
        actual = {
            1: sum(1 for wall in walls if wall.get("door") == 1),
            2: sum(1 for wall in walls if wall.get("door") == 2),
        }
        if actual != expected:
            raise ValueError("Door conservation failed on page '%s': expected %s, emitted %s"
                             % (page_name, expected, actual))
        return actual

    def wallMovementRestriction(self, page):
        """Return Foundry's ``move`` value for a barrier drawn on the walls layer.

        A wall on the dynamic-lighting layer is a wall, so it blocks movement.

        This used to read Roll20's page-level ``lightrestrictmove``, which is a
        **legacy** field: measured across 24 archived exports it is ``true`` on 52
        pages and ``null`` on 616, and is never once written as ``false``. An "off"
        state that cannot be told apart from "never set" is not a boolean, and
        Jumpgate stopped maintaining it -- the live setting is the per-barrier
        ``barrierType``. Trusting it emitted ``move: 0`` for 136,884 of 248,169 wall
        segments, which Foundry draws purple and walks straight through (B057).

        ``--no-restrict-movement`` restores the old behaviour for a campaign that
        really was played with movement unrestricted.
        """
        if self.getArgument("no_restrict_movement", False):
            return 0
        if self.getArgument("restrict_movement", False):
            return 20
        # Only a legacy campaign can express "off"; Jumpgate has no page-level flag.
        if release != "jumpgate" and page.get("lightrestrictmove") is False:
            return 0
        return 20

    @staticmethod
    def transformPathPoint(point, path, width, height):
        """Scale and rotate a path-local point around the path center."""
        x = point[0] * path.get("scaleX", 1)
        y = point[1] * path.get("scaleY", 1)
        rotation = float(path.get("rotation", 0) or 0)
        if not all(math.isfinite(value) for value in (x, y, rotation, width, height)):
            raise ValueError("Path '%s' contains non-finite geometry" %
                             path.get("id", "unknown"))
        if not rotation:
            return (x, y)
        center_x = width / 2.0
        center_y = height / 2.0
        radians = math.radians(rotation)
        delta_x = x - center_x
        delta_y = y - center_y
        return (
            center_x + delta_x * math.cos(radians) - delta_y * math.sin(radians),
            center_y + delta_x * math.sin(radians) + delta_y * math.cos(radians),
        )

    def createPathWall(self, path, page, path_type, segment_ordinal,
                       wall_a, wall_b, margin_left, margin_top,
                       grid_multiplier, door_type):
        """Build one Wall from a source path segment."""
        barrier_type = path.get("barrierType", "wall")
        if path_type == PATH_TYPE.CIRCLE:
            identifier = Entity.strToID("%s:circle-wall:%d" %
                                        (path.get("id"), segment_ordinal))
            movement = self.circleMovementRestriction(page)
        else:
            identifier = self.genID()
            movement = self.wallMovementRestriction(page)
        return {
            "_id": identifier,
            "flags": {},
            "c": [
                int(margin_left + wall_a[0] * grid_multiplier),
                int(margin_top + wall_a[1] * grid_multiplier),
                int(margin_left + wall_b[0] * grid_multiplier),
                int(margin_top + wall_b[1] * grid_multiplier),
            ],
            "move": movement,
            "door": door_type,
            "light": 0 if barrier_type == "transparent" else 20,
            "sight": 0 if barrier_type == "transparent" else 20,
            "sound": 0 if barrier_type == "transparent" else 20,
            "ds": 0,
            "dir": 0 if barrier_type == "wall" else (
                2 if path.get("oneWayReversed", False) else 1),
        }

    def circleMovementRestriction(self, page):
        """Movement policy for source circles, with CLI overrides first.

        Roll20's circle source uses a missing ``lightrestrictmove`` value as a
        vision-only barrier. Preserve that measured meaning while honoring the
        same explicit converter overrides as ordinary Walls.
        """
        if self.getArgument("no_restrict_movement", False):
            return 0
        if self.getArgument("restrict_movement", False):
            return 20
        return 20 if page.get("lightrestrictmove") is True else 0

    def isDrawing(self, graphic):
        if self.getArgument("images_as_drawings", False):
            return True
        return False

    def getRotatedBoxSize(self, w, h, r):
        # Convert rotation angle from degrees to radians
        r_rad = math.radians(r)
        
        # Calculate the new width and height
        new_width = abs(w * math.cos(r_rad)) + abs(h * math.sin(r_rad))
        new_height = abs(w * math.sin(r_rad)) + abs(h * math.cos(r_rad))
    
        return new_width, new_height
    
    def getTextSize(self, text, font_family, font_size, rotation):
        #Find the path for a specific font:
        font_family = font_family.strip().strip("'").strip('"')
        try:
            # Imported lazily: matplotlib is only needed to resolve a font file,
            # and importing it at module scope would make every consumer of
            # `entities` (including the test suite) depend on it.
            from matplotlib import font_manager
            file = font_manager.findfont(font_family)
        except:
            file = None
        if file is None:
            # A safe default size, just in case it all fails
            return (100, 50)
        try:
            font_size = int(font_size)
        except:
            font_size = 12

        # Load the font
        font = ImageFont.truetype(file, font_size)
        size = (0, 0)

        # Get the size of the text
        # in Newer pillow getsize is deprecated
        try:
            # Pillow >= 10
            size = font.getsize(text)
            # Add some padding to the width of the text
            size = (size[0] + font_size, size[1] + font_size)
        except AttributeError:
            # Pillow >= 10
            # Create a dummy image to measure text accurately
            img = Image.new("RGBA", (1, 1))
            draw = ImageDraw.Draw(img)
            
            bbox = draw.textbbox((0, 0), text, font=font)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            
            # Add padding (matching your original logic)
            width += font_size
            height += font_size
            size = (width, height)
        
        if rotation != 0:
            # If the text is rotated, we need to calculate the bounding box
            size = self.getRotatedBoxSize(size[0], size[1], rotation)
        return size

    @staticmethod
    def isZeroAreaJumpgateEllipse(path):
        points = path.get("points") or []
        return (path.get("path") is None and path.get("shape") == "eli"
            and path.get("width") == 0 and path.get("height") == 0
            and len(points) >= 2
            and all(len(point) >= 2 and math.isfinite(point[0])
                and math.isfinite(point[1]) for point in points)
            and len(set((point[0], point[1]) for point in points)) == 1)

    def pathToPolygonList(self, path, width, height):
        polygon = []
        (w, h) = (width, height)
        def add_point(x, y, w, h):
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Path '%s' contains non-finite geometry" %
                                 path.get("id", "unknown"))
            w = w if w > x else math.ceil(x)
            h = h if h > y else math.ceil(y)
            polygon.append((x, y))
            return (int(w), int(h))
        if path["path"] is None:
            # Jumpgate uses path.points instead of path.path
            source_points = path.get("points") or []
            SHAPE_TO_PATH_TYPE = {
                "pol": PATH_TYPE.POLYGON,
                "eli": PATH_TYPE.CIRCLE,
                "rec": PATH_TYPE.RECTANGLE,
                "free": PATH_TYPE.FREEHAND,
            }
            path_type = SHAPE_TO_PATH_TYPE.get(path["shape"], PATH_TYPE.POLYGON)
            if path_type == PATH_TYPE.CIRCLE:
                if len(source_points) >= 2:
                    if not all(len(point) >= 2 and math.isfinite(point[0])
                               and math.isfinite(point[1]) for point in source_points):
                        raise ValueError("Path '%s' contains non-finite geometry" %
                                         path.get("id", "unknown"))
                    min_x = min(point[0] for point in source_points)
                    max_x = max(point[0] for point in source_points)
                    min_y = min(point[1] for point in source_points)
                    max_y = max(point[1] for point in source_points)
                    w = max_x - min_x
                    h = max_y - min_y
                elif all(math.isfinite(value) and value > 0 for value in (w, h)):
                    min_x, min_y = 0, 0
                    max_x, max_y = w, h
                else:
                    raise ValueError("Path '%s' is a degenerate ellipse" %
                                     path.get("id", "unknown"))
                if w <= 0 or h <= 0:
                    raise ValueError("Path '%s' is a degenerate ellipse" %
                                     path.get("id", "unknown"))
                center_x = min_x + w / 2.0
                center_y = min_y + h / 2.0
                points = [
                    (center_x + w / 2.0 * math.cos(math.pi + step * math.pi / 8.0),
                     center_y + h / 2.0 * math.sin(math.pi + step * math.pi / 8.0))
                    for step in range(17)
                ]
                points[-1] = points[0]
            else:
                points = source_points
                min_x = min(point[0] for point in points)
                max_x = max(point[0] for point in points)
                min_y = min(point[1] for point in points)
                max_y = max(point[1] for point in points)
                w = max_x - min_x
                h = max_y - min_y
            for point in points:
                # Remove the points's minimum x/y to the polygon to make it relative to the top-left corner
                polygon.append((point[0] - min_x, point[1] - min_y))
        else:
            points = path["path"]
            path_type = PATH_TYPE.POLYGON
            current = None
            for point in points:
                if point[0] == "M": # First Point
                    if point[1] is not None and point[2] is not None:
                        (w, h) = add_point(point[1], point[2], w, h)
                        current = (point[1], point[2])
                elif point[0] == "L": # A line
                    if point[1] is not None and point[2] is not None:
                        (w, h) = add_point(point[1], point[2], w, h)
                        current = (point[1], point[2])
                elif point[0] == "Q": # Freehand
                    if point[1] is not None and point[2] is not None and \
                        point[3] is not None and point[4] is not None:
                        (w, h) = add_point(point[1], point[2], w, h)
                        (w, h) = add_point(point[3], point[4], w, h)
                        path_type = PATH_TYPE.FREEHAND
                elif point[0] == "C": # Circle
                    if current is None or len(point) < 7 or any(
                            value is None for value in point[1:7]):
                        raise ValueError("Path '%s' has an incomplete cubic curve" %
                                         path.get("id", "unknown"))
                    controls = [float(value) for value in point[1:7]]
                    if not all(math.isfinite(value) for value in controls):
                        raise ValueError("Path '%s' contains non-finite geometry" %
                                         path.get("id", "unknown"))
                    x0, y0 = current
                    x1, y1, x2, y2, x3, y3 = controls
                    for step in range(1, 5):
                        t = step / 4.0
                        inverse = 1.0 - t
                        x = (inverse ** 3 * x0
                             + 3 * inverse ** 2 * t * x1
                             + 3 * inverse * t ** 2 * x2
                             + t ** 3 * x3)
                        y = (inverse ** 3 * y0
                             + 3 * inverse ** 2 * t * y1
                             + 3 * inverse * t ** 2 * y2
                             + t ** 3 * y3)
                        (w, h) = add_point(x, y, w, h)
                    current = (x3, y3)
                    path_type = PATH_TYPE.CIRCLE
                elif point[0] == "Z": # End drawing (empty)
                    pass
                else:
                    self.logInfo("Unknown path type: %s" % str(point))
            if path_type == PATH_TYPE.POLYGON and len(points) == 5 and \
                points[0][1] == 0 and points[0][2] == 0 and \
                points[1][1] == width and points[1][2] == 0 and \
                points[2][1] == width and points[2][2] == height and \
                points[3][1] == 0 and points[3][2] == height and \
                points[4][1] == 0 and points[4][2] == 0:
                path_type = PATH_TYPE.RECTANGLE
        if path_type == PATH_TYPE.CIRCLE:
            if polygon and polygon[0] != polygon[-1]:
                polygon.append(polygon[0])
            unique = set(polygon[:-1]) if len(polygon) > 1 else set()
            if len(polygon) < 4 or len(unique) < 3:
                raise ValueError("Path '%s' is a degenerate circle" %
                                 path.get("id", "unknown"))
            span_x = max(point[0] for point in polygon) - min(point[0] for point in polygon)
            span_y = max(point[1] for point in polygon) - min(point[1] for point in polygon)
            if span_x <= 0 or span_y <= 0:
                raise ValueError("Path '%s' is a degenerate circle" %
                                 path.get("id", "unknown"))
        return (polygon, path_type, w, h)

    # Get angle between points P1, P2, P3 with the angle at P2 being returned in degrees
    def getPointsAngle(self, p1, p2, p3):
        # Let's do some trigonometry! the law of cosinus: c^2 = a^2 + b^2 - 2ab*cos(C)
        a = math.sqrt(math.pow(p1[0] - p2[0], 2) + math.pow(p1[1] - p2[1], 2))
        b = math.sqrt(math.pow(p2[0] - p3[0], 2) + math.pow(p2[1] - p3[1], 2))
        c = math.sqrt(math.pow(p1[0] - p3[0], 2) + math.pow(p1[1] - p3[1], 2))
    	#self.logInfo("Points : (%.2f, %.2f) - (%.2f, %.2f) - (%.2f, %.2f)" % (p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]))
        #self.logInfo("Lengths : %.2f - %.2f - %2.f" % (a, b, c))
        # Now to get the angle : C = acos((a^2 + b^2 - c^2) / 2ab)
        if a == 0 or b == 0:
            # Avoid a division by 0
            angle = 180
        else:
            # Looks like we need to clamp it to [-1, 1] because of floating point rounding, I got a -1.00000000004 once which gave "math domain error" exception
            cos_c = (math.pow(a, 2) + math.pow(b, 2) - math.pow(c, 2)) / (2 * a * b)
            clamped = min(max(cos_c, -1), 1)
            angle = math.degrees(math.acos(clamped))
        #self.logInfo("Angle is : %.2f" % angle )
        return angle

    def createTextDrawing(self, drawing, text):
        color = self.color(text["color"], "#ffffff", True)
        # v13 has no "t" shape type: a text drawing is a rectangle that carries
        # text (ADR-002).
        drawing["shape"]["type"] = Entity.SHAPE_RECTANGLE
        drawing.update({"fillType": 0,
                        "fillColor": color,
                        "fillAlpha": 1.0,
                        "strokeColor": "#000000",
                        "strokeAlpha": 1.0,
                        "strokeWidth": 0,
                        "texture": None,
                        "fontFamily": text["font_family"],
                        "fontSize": text["font_size"],
                        "text": text["text"],
                        "textAlpha": 1,
                        "textColor": color,
                        "bezierFactor": 0,
                    })
        return drawing

    def createPathDrawing(self, drawing, path):
        outline = self.color(path["stroke"], "#ffffff", True)
        fill = self.color(path["fill"], "#ffffff", True)
        line_width = path["stroke_width"]
        scaleX = path["scaleX"]
        scaleY = path["scaleY"]
        tile_width = safeCast(int, path["width"], 0)
        tile_height = safeCast(int, path["height"], 0)
        (points, path_type, width, height) = self.pathToPolygonList(path, tile_width, tile_height)
        # v13 dropped the freehand shape type; a freehand path is a polygon
        # smoothed by a non-zero bezierFactor (ADR-002).
        freehand = path_type == PATH_TYPE.FREEHAND
        if path_type == PATH_TYPE.CIRCLE:
            drawing_type = Entity.SHAPE_ELLIPSE
            points = []
        elif path_type == PATH_TYPE.RECTANGLE:
            drawing_type = Entity.SHAPE_RECTANGLE
            points = []
        else:
            drawing_type = Entity.SHAPE_POLYGON

        if scaleX != 1 or scaleY != 1:
            points = [(x * scaleX, y * scaleY) for (x, y) in points]

        drawing["shape"].update({"type": drawing_type,
                                 # v13 stores polygon points as a flat
                                 # [x0, y0, x1, y1, ...] array of numbers.
                                 "points": [int(c) for point in points for c in point]})
        drawing.update({"fillType": 0 if fill is None else 1,
                        "fillColor": fill,
                        "fillAlpha": 1.0,
                        "strokeColor": outline,
                        "strokeAlpha": 1.0,
                        "strokeWidth": line_width,
                        "texture": None,
                        "fontFamily": "Signika",
                        "fontSize": 45,
                        "textAlpha": 1,
                        "textColor": "#ffffff",
                        "bezierFactor": 0.5 if freehand else 0,
                    })
        return (drawing, width, height)

    def createThumbnail(self, filename, destination=None):
        temporary = filename + ".thumbnail"
        try:
            with Image.open(filename) as source:
                ratio = source.width / source.height
                if ratio > 3:
                    thumb_size = (int(100 * ratio), 100)
                    left = int((thumb_size[0] - 300) / 2)
                    crop_region = (left, 0, left + 300, 100)
                else:
                    thumb_size = (300, int(300 / ratio))
                    top = int((thumb_size[1] - 100) / 2)
                    crop_region = (0, top, 300, top + 100)
                thumbnail = source.resize(thumb_size).crop(crop_region)
                extension = os.path.splitext(filename)[1].lower()
                image_format = Image.registered_extensions().get(extension) or source.format
                if image_format == "JPEG" and thumbnail.mode not in ("RGB", "L"):
                    thumbnail = thumbnail.convert("RGB")
                if destination is not None and self.getArgument("dedup_assets", False):
                    content = io.BytesIO()
                    thumbnail.save(content, format=image_format)
                    return self._storeAssetContent(
                        None, destination, content.getvalue(), type="tiles", dedup=True)
                thumbnail.save(temporary, format=image_format)
            os.replace(temporary, filename)
            return (filename, None)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)