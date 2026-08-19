from .base import DatabaseFile, Entity
from slugify import slugify
import os
import copy

import dnd5e


#: Item types whose damage lives on the item itself (``system.damage.base``)
#: rather than entirely inside the activity. dnd5e only auto-appends ``@mod`` to
#: a weapon's damage, and only a weapon carries a base damage field.
_BASE_DAMAGE_TYPES = ("weapon",)


def identifierFor(name):
    """Slugify a class or subclass name into a dnd5e ``identifier``.

    dnd5e links a subclass to its class by matching the subclass's
    ``system.classIdentifier`` against the class's ``system.identifier``
    (ADR-006), so both sides have to derive the same string from the same name.
    Mirrors Foundry's ``String#slugify({strict: true})``: lower case, runs of
    non-alphanumerics collapsed to a single dash, no leading or trailing dash.
    """
    return slugify(name or "")


def _versatileDamage(attack, damage_type):
    """Build ``system.damage.versatile`` from the legacy versatile string."""
    formula = getattr(attack.damages, "versatile", "") or ""
    if not formula:
        return dnd5e.damageData()
    number, denomination, bonus, remainder = dnd5e.parseDamageFormula(formula)
    return dnd5e.damageData(number, denomination, bonus,
                            [damage_type] if damage_type else [],
                            custom_formula=remainder or None)


def _utilityOnly(item_name, activation_type):
    """The ``{id: activity}`` map for an item that is activated but not rollable.

    dnd5e treats "has an activation, has no action type" as a **utility**
    activity — see ``ActivitiesTemplate.#createInitialActivity``. Passive traits,
    which have no activation at all, correctly get nothing.
    """
    if not activation_type:
        return {}
    activity_id = dnd5e.activityId("%s:utility" % (item_name or ""))
    return {activity_id: dnd5e.utilityActivity(activity_id)}


def _applyMetadata(activities, item_type, activation):
    """Copy the activated-effect block from the item onto each activity.

    Only ``SpellData`` declares ``activation`` / ``range`` / ``duration`` /
    ``target`` at the document root. On a weapon, feat, equipment or consumable
    those keys are not in the schema, so Foundry drops them and the activity
    keeps its defaults: every reaction becomes an action and every ranged attack
    reads "self". Writing them onto the activity is what dnd5e's own migration
    does.
    """
    if activation is None or not activities:
        return activities
    on_item = item_type in dnd5e.ROOT_ACTIVATED_TYPES
    block = activation.getDict()
    for activity in activities.values():
        dnd5e.applyActivityMetadata(
            activity,
            activation=block.get("activation"),
            range_=block.get("range") if item_type != "weapon" else None,
            duration=block.get("duration"),
            target=block.get("target"),
            uses=block.get("uses"),
            on_item=on_item)
    return activities


def _mergeRecharge(data, recharge):
    """Fold a recharge rule into whatever ``uses`` block the item already has.

    A monster feature can have both a charge count ("2/day") and a recharge
    ("Recharge 5-6"). Replacing the whole ``uses`` object loses one of them, so
    the recovery rule is appended and the existing maximum kept.
    """
    fragment = recharge.getDict()
    if not fragment:
        return data
    existing = data.get("uses")
    if not existing or not existing.get("max"):
        data["uses"] = fragment["uses"]
        return data
    recoveries = list(existing.get("recovery") or [])
    for rule in fragment["uses"]["recovery"]:
        if rule not in recoveries:
            recoveries.append(rule)
    existing["recovery"] = recoveries
    return data


def _buildActivities(item_type, item_name, attack, ability_mods=None, ranged=None,
                     activation=None, scaling=None, level=None):
    """Turn a legacy :class:`ItemAttack` into ``system.activities`` (ADR-008).

    dnd5e 4.0 moved ``actionType``, ``attackBonus``, ``formula``, ``save``,
    ``range``, ``target``, ``duration`` and ``uses`` off the item and into an
    activity. It builds a weapon's default attack in ``WeaponData#_preCreate``,
    which fires on document *creation* — so a migrated document never gets one
    and every converted weapon arrives unrollable. We create documents, so the
    activity is written here and the gap cannot occur.

    Returns ``(system_fragment, activities)``. ``system_fragment`` carries
    ``damage.base``/``versatile`` for item types that have them; ``activities``
    is the ``{id: activity}`` map.
    """
    scaling_mode = getattr(scaling, "mode", "") or ""
    scaling_formula = getattr(scaling, "formula", "") or ""
    activation_type = getattr(activation, "activation", "") or ""

    if attack is None:
        return {}, _applyMetadata(
            _utilityOnly(item_name, activation_type), item_type, activation)

    mods = ability_mods or {}
    is_weapon = item_type in _BASE_DAMAGE_TYPES
    parts = list(attack.damages.damages or [])
    action = attack.type or ""

    if ranged is None:
        ranged = action in (ItemAttack.RANGED_WEAPON, ItemAttack.RANGED_SPELL)
    classification = "weapon" if action.endswith("wak") else "spell"

    # The sheet's own to-hit already told actors.py which ability this attack
    # uses; trust it rather than re-deriving one from the damage.
    ability = attack.ability if attack.ability in dnd5e.ABILITIES else ""

    system = {}
    activity_parts = []
    base_written = False

    for index, part in enumerate(parts):
        formula, damage_type = (list(part) + [None])[:2]
        number, denomination, bonus, remainder = dnd5e.parseDamageFormula(formula)
        embedded_type = dnd5e.normalizeDamageType(remainder)
        if not damage_type and embedded_type and remainder.strip().lower() == embedded_type:
            damage_type = embedded_type
            remainder = ""
        symbolic_match = dnd5e.ABILITY_MOD_RE.search(str(formula or ""))
        symbolic = symbolic_match.group(1).lower() if symbolic_match else None
        if symbolic:
            # The symbolic term IS the ability contribution; leaving it in the
            # formula as well would count it twice.
            remainder = dnd5e.ABILITY_MOD_RE.sub("", remainder).strip(" +")

        has_dice = number is not None
        extraction = dnd5e.extractAbilityModifier(
            bonus, mods, ranged=ranged, symbolic=symbolic, remainder=remainder,
            is_weapon=is_weapon and index == 0, has_dice=has_dice,
            required=ability or None)
        if not ability and extraction.ability:
            ability = extraction.ability

        custom = None
        if extraction.remainder:
            # A second damage die on the same part ("1d6 + 3 + 1d8") has no home
            # in the dice fields, so the whole part becomes a custom formula.
            pieces = []
            if has_dice:
                pieces.append("%dd%d" % (number, denomination))
            if extraction.bonus:
                pieces.append(str(extraction.bonus))
            pieces.append(extraction.remainder)
            custom = " + ".join(p for p in pieces if p)

        scale_mode, scale_number, scale_formula = dnd5e.damageScaling(
            scaling_mode, scaling_formula, None if custom else denomination)
        damage = dnd5e.damageData(
            number=None if custom else number,
            denomination=None if custom else denomination,
            bonus="" if custom else extraction.bonus,
            types=[damage_type] if damage_type else [],
            custom_formula=custom,
            scaling_mode=scale_mode,
            scaling_number=scale_number,
            scaling_formula=scale_formula)

        if is_weapon and not base_written:
            system["damage"] = {"base": damage,
                                "versatile": _versatileDamage(attack, damage_type)}
            base_written = True
        else:
            activity_parts.append(damage)

    if is_weapon and not base_written:
        # A weapon with no damage at all still needs the field to exist.
        system["damage"] = {"base": dnd5e.damageData(),
                            "versatile": _versatileDamage(attack, None)}

    activity_id = dnd5e.activityId("%s:%s" % (item_name or "", action or "attack"))
    save_ability = getattr(attack.save, "ability", None)

    if action == ItemAttack.SAVE and save_ability in dnd5e.ABILITIES:
        # dnd5e sets a cantrip's save to "no damage on a success" in
        # SaveActivityData#_preCreate, but only when the key is absent — and we
        # always write one, so the cantrip case has to be handled here.
        on_save = "none" if (item_type == "spell" and level == 0) else "half"
        activity = dnd5e.saveActivity(activity_id, save_ability, dc=attack.save.dc,
                                      damage_parts=activity_parts,
                                      on_save=on_save)
    elif action in (ItemAttack.MELEE_WEAPON, ItemAttack.RANGED_WEAPON,
                    ItemAttack.MELEE_SPELL, ItemAttack.RANGED_SPELL):
        activity = dnd5e.attackActivity(activity_id, ability, ranged=ranged,
                                        classification=classification,
                                        bonus=attack.bonus or "",
                                        critical_threshold=attack.critical)
        activity["damage"]["parts"] = activity_parts
        activity["damage"]["includeBase"] = is_weapon
    elif action == ItemAttack.HEALING:
        # The healing amount lives in the same damage list as everything else;
        # dropping it leaves Cure Wounds healing nothing.
        healing = activity_parts[0] if activity_parts else None
        if healing is not None:
            healing = copy.deepcopy(healing)
            healing["types"] = ["healing"]
        activity = dnd5e.healActivity(activity_id, healing=healing)
    elif activity_parts or base_written:
        activity = dnd5e.damageActivity(activity_id, damage_parts=activity_parts)
    elif activation_type:
        # dnd5e's own migration gives anything with an activation but no action
        # type a utility activity (ActivitiesTemplate.#createInitialActivity).
        # Without one a utility spell has no button on the sheet at all.
        return system, _applyMetadata(
            _utilityOnly(item_name, activation_type), item_type, activation)
    else:
        # Nothing rollable and nothing to activate: emit no activity rather than
        # an empty one that puts an unusable button on the sheet.
        return system, {}

    return system, _applyMetadata({activity_id: activity}, item_type, activation)


class Items(DatabaseFile):
    def __init__(self, converter, filename="items.db"):
        DatabaseFile.__init__(self, converter, filename)
        self._handouts = self._campaign["handouts"]
        # We can't generate them here because an Item could have cross links to another item
        # which could make it generate a new item which will try to get it added to the database
        # which hasn't been created yet. So we need to start empty and have the entities generated
        # in a separate call
        self.entities = []
        
    def addToFolder(self, folder_id, folder_name, folder, folder_path):
        items = []
        index = 0
        is_items_folder = folder_name and folder_name.strip() in self.getArgument("folder_as_items", [])
        for item in folder:
            if isinstance(item, dict):
                dirname = "%03d - %s" % (index, item["n"])
                items.extend(self.addToFolder("item" + item["id"], item["n"], item["i"], os.path.join(folder_path, dirname)))
                index += 1
            else:
                # The exporter numbers every sibling it writes, so the index must advance
                # for entries this folder does not convert -- gating it on is_items_folder
                # put "Magic Items" at 029 when the zip held 074 (B055, same cause as B053).
                handout = self.findID(item, "handout")
                if handout != None:
                    if is_items_folder:
                        items.append(Item.createItemFromHandout(self, handout, index, folder_id, folder_name, folder_path))
                    index += 1
                elif self.findID(item, "character") != None or self.findID(item, "pdf") != None:
                    index += 1

        return items

    def genEntities(self):
        return self.addToFolder(None, None, self._campaign["journalfolder"], "journal")

    def createEntities(self):
        new_entities = self.genEntities()
        self.entities.extend(new_entities)

    def addEntity(self, entity):
        self.entities.append(entity)
        entity.setPosition(len(self.entities))
        
    def createItemFromCompendium(self, id, compendium_item, custom_data=None):
        return Item.createItemFromCompendium(self, id, compendium_item, custom_data)

    def createItemInventory(self, id, name, description, inventory_type, attributes,
                            activation=None, attack=None, specific=None, **kwargs):
        if inventory_type == "loot":
            return Item.createItemLoot(self, id, name, description, attributes, **kwargs)
        elif inventory_type == "weapon":
            return Item.createItemWeapon(self, id, name, description, activation, attack, attributes, specific, **kwargs)
        elif inventory_type == "equipment":
            return Item.createItemEquipment(self, id, name, description, activation, attack, attributes, specific, **kwargs)
        elif inventory_type == "consumable":
            consumable = specific if isinstance(specific, ItemConsumable) else None
            return Item.createItemConsumable(self, id, name, description, activation, attack, attributes, consumable, **kwargs)
        elif inventory_type == "tool":
            return Item.createItemTool(self, id, name, description, attributes, specific, **kwargs)
        elif inventory_type == "backpack":
            return Item.createItemBackpack(self, id, name, description, attributes, specific, **kwargs)
        else:
            raise Exception("Unknown Inventory type")
        

    def createItemFeat(self, id, name, description, activation, attack, recharge, **kwargs):
        return Item.createItemFeat(self, id, name, description, activation, attack, recharge, **kwargs)

    def createItemSpell(self, id, name, description, activation, attack,
                        level, school, components, preparation, scaling, **kwargs):
        return Item.createItemSpell(self, id, name, description, activation, attack,
                        level, school, components, preparation, scaling, **kwargs)

    def createItemClass(self, id, name, description, level, **kwargs):
        return Item.createItemClass(self, id, name, description, level, **kwargs)

    def createItemSubclass(self, id, name, description, class_name, **kwargs):
        return Item.createItemSubclass(self, id, name, description, class_name, **kwargs)

    def createItemRace(self, id, name, description="", **kwargs):
        return Item.createItemRace(self, id, name, description, **kwargs)

    def createItemBackground(self, id, name, description="", **kwargs):
        return Item.createItemBackground(self, id, name, description, **kwargs)

class Item(Entity):
    #: Per-character state, by item type. A compendium document is a template and
    #: cannot know any of this, so these keys survive `--no-compendium-overwrite`
    #: while everything else still yields to the compendium (B050).
    CHARACTER_STATE_KEYS = {
        "class": ("levels", "hitDiceUsed"),
        "weapon": ("proficient", "equipped", "quantity", "attuned", "attunement"),
        "equipment": ("proficient", "equipped", "quantity", "attuned", "attunement"),
        "consumable": ("quantity", "uses"),
        "tool": ("proficient", "equipped", "quantity"),
        "container": ("equipped", "quantity"),
        "spell": ("preparation",),
    }

    def __init__(self, database, item_id, name, item_type="loot", img=None, data={}):
        Entity.__init__(self, database, item_id)
        # Don't want to print for every item created in a character sheet
        #self.logInfo("Creating %s Item : %s" % (item_type, name))
        
        self.entity = {"_id": self._id,
                "name":  name or "Unknown Item",
                "ownership": {"default": Item.OWNERSHIP_NONE},
                "folder": None,
                "flags": {},
                "type": item_type,
                "img": img,
                "system": data,
                "sort": 0,
                "effects": [],
                "_stats": self.documentStats()
                }

    def getName(self):
        return self.entity["name"]

    def setPosition(self, index):
        self.entity["sort"] = index * Entity.SORT_ORDER

    @staticmethod
    def createStandardData(description="", source="", activation=None, attack=None,
                           item_type=None, item_name=None, ability_mods=None,
                           scaling=None, spell_level=None, **kwargs):
        data = {
            "description": {"value": description, "chat": "", "unidentified": ""},
            "source": dnd5e.sourceData(custom=source),
        }
        if activation:
            # `activation`, `range`, `duration` and `target` live on the document
            # root only for spells — SpellData is the one item type that declares
            # them. Everywhere else they are not in the schema, get dropped on
            # load, and belong on the activity instead. `uses` is the exception:
            # ActivitiesTemplate puts it on every activatable item.
            block = activation.getDict()
            if item_type in dnd5e.ROOT_ACTIVATED_TYPES:
                data.update(block)
            else:
                data["uses"] = block["uses"]
        # dnd5e 4.0 moved every action field into an activity (ADR-008), so the
        # legacy `actionType`/`attackBonus`/`formula`/`save` block is replaced
        # rather than accompanied. This runs even without an attack: an item that
        # is merely activated still needs a utility activity.
        if attack:
            data.update(attack.getDict())
        if attack or activation:
            system_fragment, activities = _buildActivities(
                item_type, item_name, attack, ability_mods,
                activation=activation, scaling=scaling, level=spell_level)
            data.update(system_fragment)
            data["activities"] = activities

        data.update(kwargs)
        return data

    @staticmethod
    def createItemFromHandout(database, handout, index, parent, source, path):
        item = Item(database, handout["id"], handout["name"], "loot")
        
        item.logInfo("Creating Item from Handout : %s" % item.getName())

        content = handout["notes"]
        gmnotes = handout["gmnotes"]
        if gmnotes.strip() != "":
            content += "\n<section class=\"secret\"><p>GM Notes : </p>" + gmnotes + "</section>"
        content = item.replaceCompendiumLinks(item.replaceEntityLinks(content))
        permissions = {"default": Item.OWNERSHIP_NONE}
        for player in handout.get("inplayerjournals", []):
            if player == "all":
                permissions["default"] = Item.OWNERSHIP_OBSERVER
            elif player != "":
                player_id = Entity.normalizeID(player)
                permissions[player_id] = Item.OWNERSHIP_OBSERVER
        for player in handout.get("controlledby", []):
            if player == "all":
                permissions["default"] = Item.OWNERSHIP_OWNER
            elif player != "":
                player_id = Entity.normalizeID(player)
                permissions[player_id] = Item.OWNERSHIP_OWNER
        avatar_filename = None
        if handout["avatar"] != "":
            if item.getArgument("use_original_image_urls", False):
                avatar_filename = handout["avatar"]
            else:
                filename = item.getImageFilename(os.path.join(path, "%03d - %s" % (index, handout["name"])), handout["avatar"], "avatar")
                if item.getArgument("json", False):
                    (_, avatar_filename) = item.downloadResource(handout["avatar"], filename)
                else:
                    (_, avatar_filename) = item.copyZipFile(handout["avatar"], filename, filename)
                if avatar_filename == "":
                    avatar_filename = None
        if item.getArgument("export_as_module", False):
            parent = None

        attributes = ItemInventoryAttributes()
        data = Item.createStandardData(content, source, **attributes.getDict())
        item.entity = {
            "_id": item._id,
            "name":  handout["name"],
            "ownership": permissions,
            "folder": Entity.normalizeID(parent),
            "flags": {},
            "type": "loot",
            "img": avatar_filename,
            "sort": index * Entity.SORT_ORDER,
            "system": data,
            "effects": [],
            "_stats": item.documentStats()
        }
        return item

    @staticmethod
    def createItemFromCompendium(database, id, compendium_item, custom_data=None):
        item = Item(database, id, compendium_item.entity["name"])
        item.entity = copy.deepcopy(compendium_item.entity)
        item.entity["_id"] = item.getID()
        item.entity["ownership"] = {"default": Item.OWNERSHIP_NONE}
        item.entity["folder"] = None
        # Older compendium packs may still use the pre-v10 `data` key (ADR-002).
        Entity.normalizeSystemData(item)
        if custom_data:
            if item.getArgument("no_compendium_overwrite", False) is False:
                item.entity["system"].update(custom_data)
            else:
                # B050: the flag protects the compendium's *template* data, but
                # `update()` is all-or-nothing, so it was also discarding state that
                # describes this one character and can never come from a template --
                # a class's levels, a weapon's proficiency. Those always win.
                for key in Item.CHARACTER_STATE_KEYS.get(item.entity["type"], ()):
                    if key in custom_data:
                        item.entity["system"][key] = custom_data[key]
        # The compendium copy carries whatever `_stats` its pack was built with.
        # If that is older than the version we claim, dnd5e migrates the item —
        # the exact outcome this port exists to avoid.
        item.entity["_stats"] = item.documentStats()

        return item


    @staticmethod
    def createItemLoot(database, id, name, description, attributes, **kwargs):
        source = kwargs.pop("source", "")
        attributes = attributes if attributes else ItemInventoryAttributes()
        kwargs.update(attributes.getDict())
        data = Item.createStandardData(description, source, **kwargs)
        return Item(database, id, name, "loot", None, data)

    @staticmethod
    def createItemWeapon(database, id, name, description, activation, attack, attributes, weapon, **kwargs):
        ability_mods = kwargs.pop("ability_mods", None)
        source = kwargs.pop("source", "")
        activation = activation if activation else ItemActivation()
        attack = attack if attack else ItemAttack()
        attributes = attributes if attributes else ItemInventoryAttributes()
        weapon = weapon if weapon else ItemWeapon()
        weapon.name = name
        kwargs.update(ItemConsume().getDict()) 
        kwargs.update(ItemObject().getDict()) 
        kwargs.update(attributes.getDict())
        kwargs.update(weapon.getDict())
        if activation is not None:
            # WeaponData declares its own numeric range with `reach` and `long`,
            # not the shared RangeField. The shared shape puts a formula string
            # into a NumberField and loses both extra distances.
            legacy_range = activation.range
            kwargs["range"] = dnd5e.weaponRange(
                value=legacy_range.range, long=legacy_range.max,
                units=legacy_range.units)
        data = Item.createStandardData(description, source, activation, attack,
                                       item_type="weapon", item_name=name,
                                       ability_mods=ability_mods, **kwargs)
        return Item(database, id, name, "weapon", None, data)

    @staticmethod
    def createItemEquipment(database, id, name, description, activation, attack, attributes, equipment, **kwargs):
        ability_mods = kwargs.pop("ability_mods", None)
        source = kwargs.pop("source", "")
        activation = activation if activation else ItemActivation()
        attack = attack if attack else ItemAttack()
        attributes = attributes if attributes else ItemInventoryAttributes()
        equipment = equipment if equipment else ItemEquipment()
        equipment.name = name
        kwargs.update(ItemConsume().getDict()) 
        kwargs.update(ItemObject().getDict()) 
        kwargs.update(attributes.getDict())
        kwargs.update(equipment.getDict())
        data = Item.createStandardData(description, source, activation, attack,
                                       item_type="equipment", item_name=name,
                                       ability_mods=ability_mods, **kwargs)
        return Item(database, id, name, "equipment", None, data)

    @staticmethod
    def createItemConsumable(database, id, name, description, activation, attack, attributes, consumable, **kwargs):
        ability_mods = kwargs.pop("ability_mods", None)
        source = kwargs.pop("source", "")
        activation = activation if activation else ItemActivation()
        attack = attack if attack else ItemAttack()
        attributes = attributes if attributes else ItemInventoryAttributes()
        consumable = consumable if consumable else ItemConsumable()
        kwargs.update(ItemConsume().getDict()) 
        kwargs.update(attributes.getDict())
        kwargs.update(consumable.getDict())
        data = Item.createStandardData(description, source, activation, attack,
                                       item_type="consumable", item_name=name,
                                       ability_mods=ability_mods, **kwargs)
        return Item(database, id, name, "consumable", None, data)

    @staticmethod
    def createItemTool(database, id, name, description, attributes, tool, **kwargs):
        source = kwargs.pop("source", "")
        attributes = attributes if attributes else ItemInventoryAttributes()
        tool = tool if tool else ItemTool()
        kwargs.update(attributes.getDict())
        kwargs.update(tool.getDict())
        data = Item.createStandardData(description, source, None, None, **kwargs)
        return Item(database, id, name, "tool", None, data)

    @staticmethod
    def createItemBackpack(database, id, name, description, attributes, backpack, **kwargs):
        source = kwargs.pop("source", "")
        attributes = attributes if attributes else ItemInventoryAttributes()
        backpack = backpack if backpack else ItemBackpack()
        kwargs.update(attributes.getDict())
        kwargs.update(backpack.getDict())
        data = Item.createStandardData(description, source, None, None, **kwargs)
        # dnd5e renamed backpack -> container in 3.0. Emitting the old type does
        # not fail: `_initializeSource` rewrites it and sets
        # `persistSourceMigration`, queueing the document for a rewrite.
        return Item(database, id, name, "container", None, data)

    @staticmethod
    def createItemFeat(database, id, name, description, activation, attack, recharge, **kwargs):
        ability_mods = kwargs.pop("ability_mods", None)
        kwargs.setdefault("requirements", "")
        source = kwargs.pop("source", "")
        activation = activation if activation else ItemActivation()
        attack = attack if attack else ItemAttack()
        recharge = recharge if recharge else ItemFeatRecharge()
        kwargs.update(ItemConsume().getDict()) 
        data = Item.createStandardData(description, source, activation, attack,
                                       item_type="feat", item_name=name,
                                       ability_mods=ability_mods, **kwargs)
        _mergeRecharge(data, recharge)
        return Item(database, id, name, "feat", None, data)

    @staticmethod
    def createItemSpell(database, id, name, description, activation, attack,
                        level, school, components, preparation, scaling, **kwargs):
        ability_mods = kwargs.pop("ability_mods", None)
        source = kwargs.pop("source", "")
        activation = activation if activation else ItemActivation()
        attack = attack if attack else ItemAttack()
        components = components if components else ItemSpellComponents()
        preparation = preparation if preparation else ItemSpellPreparation()
        scaling = scaling if scaling else ItemSpellScaling()
        kwargs.setdefault("level", level)
        kwargs.setdefault("school", school)
        kwargs.update(ItemConsume().getDict()) 
        kwargs.update(components.getDict())
        kwargs.update(preparation.getDict())
        kwargs.update(scaling.getDict())
        data = Item.createStandardData(description, source, activation, attack,
                                       item_type="spell", item_name=name,
                                       ability_mods=ability_mods,
                                       scaling=scaling, spell_level=level, **kwargs)
        return Item(database, id, name, "spell", None, data)

        
    @staticmethod
    def createItemClass(database, id, name, description, level, **kwargs):
        classData = ItemClass(name, level)
        kwargs.update(classData.getDict())
        data = Item.createStandardData(description, **kwargs)
        return Item(database, id, name, "class", None, data)

    @staticmethod
    def createItemSubclass(database, id, name, description, class_name, **kwargs):
        """Build the ``subclass`` document that dnd5e 2.1+ expects (ADR-006).

        ``class_name`` is the *class* this subclass belongs to, not the
        subclass itself; it is slugified into ``classIdentifier``, which is the
        only thing tying the two documents together on the sheet.
        """
        subclassData = ItemSubclass(name, class_name)
        kwargs.update(subclassData.getDict())
        data = Item.createStandardData(description, **kwargs)
        return Item(database, id, name, "subclass", None, data)

    @staticmethod
    def createItemRace(database, id, name, description="", **kwargs):
        """Build the ``race`` document dnd5e 4.0+ expects (ADR-007).

        The actor's ``system.details.race`` holds this document's id, not its
        name; the caller is responsible for writing that link.
        """
        kwargs.update(ItemOrigin(name).getDict())
        data = Item.createStandardData(description, **kwargs)
        return Item(database, id, name, "race", None, data)

    @staticmethod
    def createItemBackground(database, id, name, description="", **kwargs):
        """Build the ``background`` document dnd5e 4.0+ expects (ADR-007)."""
        kwargs.update(ItemOrigin(name).getDict())
        data = Item.createStandardData(description, **kwargs)
        return Item(database, id, name, "background", None, data)


# Generic item variables

class ItemAbility:
    NONE = ""
    STRENGTH = "str"
    DEXTERITY = "dex"
    CONSITUTION = "con"
    INTELLIGENCE = "int"
    WISDOM = "wis"
    CHARISMA = "cha"

    @staticmethod
    def fromString(string):
        string = str(string).lower()
        abbr = string[0:3]
        if abbr in ["str", "dex", "con", "wis", "int", "cha"]:
            return abbr

        # Use case of "@{strength_mod}" for example
        for ability in ["strength", "dexterity", "constitution", "wisdom", "intelligence", "charisma"]:
            if ability in string:
                return ability[0:3]
        return ItemAbility.NONE

        
class ItemDamage:
    def __init__(self, versatile=""):
        self.damages = []
        self.versatile = versatile

    def addDamage(self, formula, type):
        self.damages.append((formula, type))

    def getDict(self):
        # dnd5e 5.x replaced the ``[[formula, type], ...]`` pair list with
        # ``damage.base``/``damage.versatile`` DamageData objects, which are
        # written by _buildActivities() because they need the actor's ability
        # modifiers. Emitting nothing here keeps the legacy ``parts`` key out of
        # the output (ADR-008).
        return {}
    
class ItemSave:
    def __init__(self, ability=ItemAbility.NONE, dc=None, scaling=None):
        self.ability = ability
        self.dc = dc
        self.scaling = scaling if scaling else "spell"

    def getDict(self):
        return {
            "save": {
                "ability": self.ability,
                "dc": self.dc,
                "scaling": self.scaling
            }
        }

        
# Unused
class ItemConsume:
    def __init__(self):
        pass

    def getDict(self):
        """5.x has no ``system.consume``; consumption moved into the activity."""
        return {}
class ItemObject:
    def __init__(self):
        pass

    def getDict(self):
        """5.x has no weapon ``hp``, and ``armor.value`` is the item's own AC."""
        return {}

class ItemAttack:
    EMPTY = ""
    MELEE_WEAPON = "mwak"
    RANGED_WEAPON = "rwak"
    MELEE_SPELL = "msak"
    RANGED_SPELL = "rsak"
    SAVE = "save"
    HEALING = "heal"
    ABILITY = "abil"
    UTILITY = "util"
    OTHER = "other"

    def __init__(self, type=EMPTY, ability=ItemAbility.NONE, damages=None, save=None,
                 bonus=0, formula="", critical=None, chatFlavor=""):
        self.type = type
        self.ability = ability
        self.damages = damages if damages else ItemDamage()
        self.save = save if save else ItemSave()
        self.bonus = bonus
        self.formula = formula
        self.critical = critical
        self.chatFlavor = chatFlavor

    def getDict(self):
        # dnd5e 4.0 moved every one of these onto the activity (ADR-008):
        # actionType, attackBonus, formula, chatFlavor and critical are gone
        # from the item, and save moved into a save activity. Only the fields
        # the item itself still owns are emitted here.
        data = {}
        data.update(self.damages.getDict())
        return data

class ItemRange:
    EMPTY = ""
    NONE = "none"
    SELF = "self"
    TOUCH = "touch"
    FEET = "ft"
    MILES = "mi"
    SPECIAL = "spec"
    ANY = "any"

    def __init__(self, range=None, max=None, units=EMPTY):
        self.range = range
        self.max = max
        self.units = units

    def getDict(self):
        return {"range": dnd5e.rangeData(self.range, self.units)}

class ItemTarget:
    EMPTY = ""
    NONE = "none"
    SELF = "self"
    CREATURE = "creature"
    ALLY = "ally"
    ENEMY = "enemy"
    OBJECT = "object"
    SPACE = "space"
    RADIUS = "radius"
    SPHERE = "sphere"
    CYLINDER = "cylinder"
    CONE = "cone"
    SQUARE = "square"
    CUBE = "cube"
    LINE = "line"
    WALL = "wall"

    def __init__(self, type=EMPTY, range=None, width=None):
        self.range = range if range else ItemRange()
        self.width = width
        self.type = type

    def getDict(self):
        return {
            "target": dnd5e.targetData(self.type, self.range.range,
                                       self.width, self.range.units)
        }
        
class ItemDuration:
    NONE = ""
    INSTANTANEOUS = "inst"
    TURN = "turn"
    ROUND = "round"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    PERMANENT = "perm"
    SPECIAL = "spec"

    def __init__(self, duration=0, units=NONE):
        self.duration = duration
        self.units = units

    def getDict(self):
        return {"duration": dnd5e.durationData(self.duration, self.units)}
        
class ItemUses:
    PER_NONE = ""
    PER_SHORT_REST = "sr"
    PER_LONG_REST = "lr"
    PER_DAY = "day"
    PER_CHARGES = "charges"

    def __init__(self, uses=0, max=0, per=PER_NONE):
        self.uses = uses
        self.max = max
        self.per = per

    def getDict(self):
        return {"uses": dnd5e.usesFromLegacy(self.uses, self.max, self.per)}

class ItemActivation:
    EMPTY = ""
    NONE = "none"
    ACTION = "action"
    BONUS_ACTION = "bonus"
    REACTION = "reaction"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    SPECIAL = "special"
    LEGENDARY = "legendary"
    LAIR = "lair"

    def __init__(self, activation=EMPTY, cost=0, condition="",
                 target=None, range=None, duration=None, uses=None):
        self.activation = activation
        self.cost = cost
        self.condition = condition
        self.target = target if target else ItemTarget()
        self.range = range if range else ItemRange()
        self.duration = duration if duration else ItemDuration()
        self.uses = uses if uses else ItemUses()

    def getDict(self):
        data = {
            "activation": dnd5e.activationData(self.activation, self.cost,
                                               self.condition)
        }
        data.update(self.target.getDict())
        data.update(self.range.getDict())
        data.update(self.duration.getDict())
        data.update(self.uses.getDict())
        return data


# Feat specific item variables

class ItemFeatRecharge:
    def __init__(self, recharges=0, charged=False):
        self.recharges = recharges
        self.charged = charged

    def getDict(self):
        """5.x has no ``system.recharge``; a recharge is a ``uses.recovery`` rule.

        Emitting the legacy block leaves the feature with no recharge at all, so
        the uses block is rewritten here instead. ``recharges`` is the minimum d6
        roll that restores the feature.
        """
        if not self.recharges:
            return {}
        entry = dnd5e.recovery("recharge", self.recharges)
        spent = 0 if self.charged else 1
        return {"uses": dnd5e.usesData(spent, 1, [entry])}

# Spell specific item variables

class ItemSpellSchool:
    ABJURATION = "abj"
    CONJURATION = "con"
    DIVINATION = "div"
    ENCHANTMENT = "enc"
    EVOCATION = "evo"
    ILLUSION = "ill"
    NECROMANCY = "nec"
    TRANSMUTATION = "trs"

class ItemSpellComponents:
    def __init__(self, concentration=False, ritual=False,
                 v=False, s=False, m=False, materials="",
                 consumed=False, cost=0, supply=0):
        self.concentration = concentration
        self.ritual = ritual
        self.v = v
        self.s = s
        self.m = m
        self.materials = materials
        self.consumed = consumed
        self.cost = cost
        self.supply = supply

    def getDict(self):
        """5.x folds the component booleans into the shared ``properties`` set."""
        return {
            "properties": dnd5e.spellProperties(
                vocal=self.v, somatic=self.s, material=self.m,
                concentration=self.concentration, ritual=self.ritual),
            "materials": {
                "value": self.materials,
                "consumed": self.consumed,
                "cost": self.cost,
                "supply": self.supply
            }
        }
    
class ItemSpellScaling:
    NONE = "none"
    CANTRIP = "cantrip"
    LEVEL = "level"

    def __init__(self, mode=NONE, formula=""):
        self.mode = mode
        self.formula = formula

    def getDict(self):
        """``system.scaling`` does not exist in 5.x.

        Scaling moved onto the activity's damage parts, so this contributes
        nothing to ``system``; :func:`_buildActivities` reads the object
        directly. Emitting the legacy key would leave a field dnd5e never reads
        and a spell that does not scale.
        """
        return {}

class ItemSpellPreparation:
    NONE = ""
    PREPARED_SPELL = "prepared"
    INNATE_SPELLCASTING = "innate"
    ALWAYS_AVAILABLE = "always"
    PACT_MAGIC = "pact"

    def __init__(self, mode=PREPARED_SPELL, prepared=False):
        self.mode = mode
        self.prepared = prepared

    def getDict(self):
        """5.x replaced ``preparation`` with ``method`` plus a numeric ``prepared``."""
        return dnd5e.spellPreparation(self.mode, self.prepared)

# Physical Item specific attributes
class ItemInventoryAttributes:
    def __init__(self, rarity="", quantity=1, weight=1, price=0,
                equipped=False, identified=True, attunement=0):
        self.rarity = rarity
        self.quantity = quantity
        self.weight = weight
        self.price = price
        self.attunement = attunement
        self.equipped = equipped
        self.identified = identified

    def getDict(self):
        return {
            "rarity": self.rarity,
            "quantity": self.quantity,
            "weight": dnd5e.weightData(self.weight),
            "price": dnd5e.priceData(self.price),
            "attunement": dnd5e.attunement(self.attunement),
            "equipped": self.equipped,
            "identified": self.identified
        }


# Weapon specific item variables

class ItemWeaponProperties:
    AMMUNITION = "amm"
    FINESSE = "fin"
    FIREARM = "fir"
    FOCUS = "foc"
    HEAVY = "hvy"
    LIGHT = "lgt"
    REACH = "rch"
    RELOAD = "rel"
    RETURNING = "ret"
    SPECIAL = "spc"
    THROWN = "thr"
    TWO_HANDED = "two"
    VERSATILE = "ver"

    def __init__(self):
        self.properties = []

    def addProperty(self, weapon_property):
        self.properties.append(weapon_property)

    def addFromString(self, string):
        string = string.lower()
        if string == "ammunication":
            self.addProperty(self.AMMUNITION)
        elif string == "finesse":
            self.addProperty(self.FINESSE)
        elif string == "firearm":
            self.addProperty(self.FIREARM)
        elif string == "focus":
            self.addProperty(self.FOCUS)
        elif string == "heavy":
            self.addProperty(self.HEAVY)
        elif string == "light":
            self.addProperty(self.LIGHT)
        elif string == "reach":
            self.addProperty(self.REACH)
        elif string == "reload":
            self.addProperty(self.RELOAD)
        elif string == "returning":
            self.addProperty(self.RETURNING)
        elif string == "special":
            self.addProperty(self.SPECIAL)
        elif string == "thrown":
            self.addProperty(self.THROWN)
        elif string == "two-handed":
            self.addProperty(self.TWO_HANDED)
        elif string == "versatile":
            self.addProperty(self.VERSATILE)

    def getDict(self):
        # dnd5e 5.x expects an array of the set keys, not an object of booleans
        # over every key. An unrecognised key fails validation for the item.
        return {"properties": dnd5e.properties(
            {prop: True for prop in self.properties})}

class ItemWeapon:
    AMMUNITION = "ammo"
    IMPROVISED = "improv"
    MARTIAL_MELEE = "martialM"
    MARTIAL_RANGED = "martialR"
    NATURAL = "natural"
    SIMPLE_MELEE = "simpleM"
    SIMPLE_RANGED = "simpleR"

    def __init__(self, _type=NATURAL, proficient=True, properties=None):
        self.type = _type
        self.proficient = proficient
        self.properties = properties if properties else ItemWeaponProperties()


    def getDict(self):
        # ``name`` is set by createItemWeapon so the SRD baseItem can be looked
        # up; without it dnd5e applies no mastery or proficiency (AD-7).
        data = {
            "type": dnd5e.itemType(self.type, dnd5e.weaponBaseItem(getattr(self, "name", ""))),
            "proficient": self.proficient
        }
        data.update(self.properties.getDict())
        return data

# Consumable specific item variables

class ItemConsumableUses(ItemUses):
    def __init__(self, uses=0, max=0, per=ItemUses.PER_NONE, autoDestroy=True, autoUse=True):
        ItemUses.__init__(self, uses, max, per)
        self.autoDestroy = autoDestroy
        self.autoUse = autoUse

    def getDict(self):
        data = super().getDict()
        data["uses"].update({
            "autoUse": self.autoUse,
            "autoDestroy": self.autoDestroy
        })
        return data

class ItemConsumable:
    POISON = "poison"
    POTION = "potion"
    ROD = "rod"
    SCROLL = "scroll"
    TRINKET = "trinket"
    WAND = "wand"

    def __init__(self, _type=TRINKET, uses=None):
        self.type = _type
        self.uses = uses if uses else ItemConsumableUses()

    def getDict(self):
        data = {
            "type": dnd5e.itemType(self.type),
        }
        data.update(self.uses.getDict())
        return data

# Equipment specific item variables
class ItemEquipment:
    CLOTHING = "clothing"
    HEAVY_ARMOR = "heavy"
    LIGHT_ARMOR = "light"
    MAGICAL_BONUS = "bonus"
    MEDIUM_ARMOR = "medium"
    NATURAL_ARMOR = "natural"
    SHIELD = "shield"
    TRINKET = "trinket"

    def __init__(self, _type=CLOTHING, dexterity=None, ac=10, strength=0, stealth=False, proficient=True,
                 magical_bonus=None):
        self.type = _type
        self.dexterity = dexterity
        self.ac = ac
        self.strength = strength
        self.stealth = stealth
        self.proficient = proficient
        self.magical_bonus = magical_bonus

    def getDict(self):
        # `dex` is nullable: None is uncapped, 0 is a real cap of +0 (B033).
        dexterity = self.dexterity
        if dexterity is None:
            dexterity = dnd5e.armorDexLimit(self.type)
        return {
            "armor": {
                "value": self.ac,
                "dex": dexterity,
                "magicalBonus": self.magical_bonus
            },
            "type": dnd5e.itemType(self.type, dnd5e.armorBaseItem(getattr(self, "name", ""))),
            "properties": [dnd5e.STEALTH_DISADVANTAGE] if self.stealth else [],
            "strength": self.strength,
            "proficient": self.proficient
        }
        

# Tool specific item variables
class ItemTool:
    def __init__(self, ability=ItemAbility.NONE, proficiency=0, flavor=""):
        self.proficiency = proficiency
        self.ability = ability
        self.flavor = flavor

    def getDict(self):
        return {
            "proficient": self.proficiency,
            "ability": self.ability,
            "chatFlavor": self.flavor,
            "type": dnd5e.itemType(""),
            "bonus": ""
        }

# Tool specific item variables
class ItemBackpack:
    ITEMS = "items"
    WEIGHT = "weight"
    
    def __init__(self, _type=ITEMS, capacity=0, weightless=False, cp=0, sp=0, ep=0, gp=0, pp=0):
        self.type = _type
        self.capacity = capacity
        self.weightless = weightless
        self.cp = cp
        self.sp = sp
        self.ep = ep
        self.gp = gp
        self.pp = pp

    def getDict(self):
        """Build ``ContainerData``.

        5.x replaced the ``{type, value, weightless}`` capacity with separate
        ``count`` / ``volume`` / ``weight`` fields and moved ``weightless`` into
        ``properties``. The translation below is the one dnd5e's own
        ``#migrateCapacity`` performs, done up front so no migration is queued.
        """
        capacity = {}
        if self.capacity:
            if self.type == self.WEIGHT:
                capacity["weight"] = dnd5e.weightData(self.capacity)
            elif self.type == self.ITEMS:
                capacity["count"] = self.capacity
        data = {
            "capacity": capacity,
            "currency": {
                "cp": self.cp,
                "sp": self.sp,
                "ep": self.ep,
                "gp": self.gp,
                "pp": self.pp
            },
            # ContainerData clamps quantity to exactly 1.
            "quantity": 1,
        }
        if self.weightless:
            data["properties"] = ["weightlessContents"]
        return data

# Class specific item variables
#: The primary ability each class uses, from the PHB multiclassing table. dnd5e
#: 5.x stores this in ``system.primaryAbility``; it is not derivable from the
#: spellcasting ability (a Fighter has one and no spellcasting; a Paladin's
#: spellcasting ability is not its only primary).
CLASS_PRIMARY_ABILITY = {
    "artificer": ["int"],
    "barbarian": ["str"],
    "bard": ["cha"],
    "cleric": ["wis"],
    "druid": ["wis"],
    "fighter": ["str"],
    "monk": ["dex"],
    "paladin": ["str", "cha"],
    "ranger": ["dex"],
    "rogue": ["dex"],
    "sorcerer": ["cha"],
    "warlock": ["cha"],
    "wizard": ["int"],
}


class ItemClass:
    def __init__(self, name, level, hitdice=None):
        try:
            self.level = int(level)
        except:
            self.level = 1
        self.identifier = identifierFor(name)
        self.hitdice = hitdice
        cl = name.strip().lower()
        self.primary_ability = CLASS_PRIMARY_ABILITY.get(cl, [])
        # Set class hitdice
        if self.hitdice is None:
            if cl in ["artificer", "bard", "cleric", "druid", "monk", "rogue", "warlock"]:
                self.hitdice = "d8"
            elif cl in ["fighter", "paladin", "ranger"]:
                self.hitdice = "d10"
            elif cl == "barbarian":
                self.hitdice = "d12"
            else: # name == "sorcerer" or name == "wizard" or default:
                self.hitdice = "d6"
        # Set spellcasting progression type
        if cl in ["sorcerer", "bard", "cleric", "wizard", "druid"]:
            self.spell_progression = "full"
        elif cl in ["ranger", "paladin"]:
            self.spell_progression = "half"
        elif cl == "warlock":
            self.spell_progression = "pact"
        elif cl == "artificer":
            self.spell_progression = "artificer"
        else: # monk, fighter, barbarian, rogue
            self.spell_progression = "none"
        # Set spellcasting ability
        if cl in ["sorcerer", "warlock", "bard", "paladin"]:
            self.spell_ability = "cha"
        elif cl in ["ranger", "cleric", "druid"]:
            self.spell_ability = "wis"
        elif cl in ["wizard", "artificer"]:
            self.spell_ability = "int"
        else: # monk, fighter, barbarian, rogue
            self.spell_ability = ""

    def getDict(self):
        return {
            "levels": self.level,
            # dnd5e dropped `subclass` in 2.1; the subclass is its own document
            # now and finds this class by matching `identifier` (ADR-006).
            "identifier": self.identifier,
            # 5.x replaced `hitDice`/`hitDiceUsed` with the `hd` block. The old
            # keys are not in ClassData, so they are dropped on load and the
            # class arrives with the d6 default whatever it really is.
            "hd": {
                "additional": "",
                "denomination": self.hitdice,
                "spent": 0,
            },
            "primaryAbility": {
                "value": list(self.primary_ability),
                "all": True,
            },
            "properties": [],
            "spellcasting": {
                "progression": self.spell_progression,
                "ability": self.spell_ability,
                "preparation": {"formula": ""},
            }
        }


class ItemSubclass:
    """The ``subclass`` document dnd5e has expected since 2.1 (ADR-006).

    Deliberately thin. Roll20's OGL sheet stores the subclass as a bare string,
    so a name is genuinely all we have; inventing features here would mean
    guessing which book the table plays with. The GM links it to real content.
    """

    def __init__(self, name, class_name):
        self.identifier = identifierFor(name)
        self.class_identifier = identifierFor(class_name)

    def getDict(self):
        return {
            "identifier": self.identifier,
            "classIdentifier": self.class_identifier,
            "advancement": [],
        }


class ItemOrigin:
    """Shared shape for the ``race`` and ``background`` documents (ADR-007).

    Thin for the same reason ``ItemSubclass`` is: Roll20 stores both as bare
    strings, so a name is all we have, and guessing at traits would attach
    mechanics the character never had. ``identifier`` is required by
    ``ItemDescriptionTemplate``, which dnd5e mixes into every item type.
    """

    def __init__(self, name):
        self.identifier = identifierFor(name)

    def getDict(self):
        return {
            "identifier": self.identifier,
            "advancement": [],
        }
