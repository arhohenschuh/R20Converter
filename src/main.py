#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import zipfile
import sys
import os
import platform
import argparse

# If we're in windowed mode, we need to have stdout/stderr because the
# GUI/argparse/anything will try to write to stderr/stdout whenever it feels
# like it and will cause a crash on import
if sys.stdout is None:
    try:
        sys.stdout = open('stdout.log', 'w')
        sys.stderr = open('stderr.log', 'w')
    except:
        # Installing to C:\Program Files (for example) or other permission error could cause this to fail
        import io
        sys.stdout = io.BytesIO()
        sys.stderr = io.BytesIO()

import messages
import foundry
from version import version
from R20Converter import R20Converter

# The GUI is optional: it pulls in eel/tkinter/wx, which are not installed in
# headless or CLI-only environments, and which cx_freeze sometimes fails to
# resolve on the first import attempt inside a frozen bundle. A failure here is
# not fatal — we simply lose the "launch the GUI when given no arguments"
# behaviour and remain a pure CLI tool.
try:
    from GUI import GUI
    GUI_IMPORT_ERROR = None
except Exception:
    import traceback
    # Record *why* the GUI was unavailable. Swallowing this silently makes a
    # failed GUI launch look identical to "user ran us with no arguments",
    # which surfaces to the user as the executable doing nothing at all.
    GUI_IMPORT_ERROR = traceback.format_exc()
    GUI = None

parser = argparse.ArgumentParser(prog="R20Converter",
                                 description="R20Converter v{}".format(version), epilog="Convert Roll20 campaigns into Foundry VTT worlds or modules.")
parser.add_argument("path", metavar="destination-directory", help="The destination directory in Data/worlds/ or Data/modules/")
parser.add_argument("zip_file", metavar="exported.zip", help="The exported ZIP file from R20Exporter")
parser.add_argument("--json", action="store_true", help="Use campaign.json as input instead of a ZIP file (playlist will be empty due to audio tracks being accessible only when logged into Roll20)")
parser.add_argument("--export-as-module", action="store_true", help="Export the campaign as a module (instead of a world) with Compendium packs for all handouts/characters/scenes/playlists")
parser.add_argument("--campaign-title", default=None, help="Override the Campaign title")
parser.add_argument("--description", default="Imported from Roll20 using R20Converter", help="World Desription")
parser.add_argument("--gm-password", default="", help="Default GM password")
parser.add_argument("--player-password", default="", help="Default player password")
parser.add_argument("--restrict-movement", action="store_true", help="Force all walls to restrict movement")
parser.add_argument("--force-hp-for-token-bar1", action="store_true", help="Forces the use of HP attribute for all tokens' first bar")
parser.add_argument("--force-hp-for-token-bar2", action="store_true", help="Forces the use of HP attribute for all tokens' second bar")
parser.add_argument("--add-walls-around-map", action="store_true", help="Add 4 walls to enclose the map and cut off view/movement to the side table")
# --enable-fog and --disable-fog are direct opposites; passing both used to be
# accepted silently with undefined precedence. argparse now rejects the
# combination for us.
fog_group = parser.add_mutually_exclusive_group()
fog_group.add_argument("--enable-fog", action="store_true", help="Enable Fog Exploration on all Scenes with Dynamic Lighting regardless of Advanced Fog of War setting")
fog_group.add_argument("--disable-fog", action="store_true", help="Disable Fog Exploration on all Scenes with Dynamic Lighting regardless of Advanced Fog of War setting")
parser.add_argument("--cleanup-scenes", action="store_true", help="Remove any tiles, tokens or walls that are outside of a scene's boundary")
parser.add_argument("--interactive", action="store_true", help="Ask questions about decisions to be made during the conversion process.")
parser.add_argument("--auto-doors", action="store_true", help="Automatically detect doors and set them as such.")
parser.add_argument("--door-color", default=None, help="Sets the color of the dynamic lighting walls to convert into doors. For example, set it to '#ff0000' for Red walls.")
parser.add_argument("--secret-door-color", default=None, help="Sets the color of the dynamic lighting walls to convert into secret doors")
parser.add_argument("--disable-archived", action="store_true", help="Disable the automatic move of archived scenes/handouts/characters to an Archived folder.")
parser.add_argument("--all-backgrounds-as-tiles",  action="store_true", help="Set all page backgrounds as tiles.")
parser.add_argument("--minimum-wall-length", default=0, type=float, help="Minimum distance for walls (in pixels).\n"
                    "If a wall is smaller and part of a longer chain of walls, it will get merged with the adjacent wall.\n"
                    "This is useful if there are a lot of small/jagged walls or freehand-drawn walls (Default: 0 (disabled))")
parser.add_argument("--maximum-wall-angle", default=30, type=float, help="Maximum angle (in degrees) between walls before they are merged (when using --minimum-wall-distance option).\n"
                    "This is to prevent small walls at high angles (a small triangle or U shape) from being merged and becoming a line that cuts through the map.\n"
                    "The angle is calculated with every point in the wall that is skipped, so a circle drawn with small lines and small angles will not be removed.\n"
                    "Note that the angle here is related to a straight line, so a maximum angle of 30 means an angle between 150 and 210 degrees between the 3 points (Default: 30)")
parser.add_argument("--scene-padding", default=0.25, type=float, help="Side-table padding around each scene")
parser.add_argument("--debug-page", default=None, help="Only convert a specific page. Useful for debugging")
parser.add_argument("--fvtt-data-path", default=None, help="Path to the FVTT Data directory, or to a Foundry installation directory containing Config/options.json (used for importing items and spells from dnd5e system)")
parser.add_argument("--srd-edition", default=foundry.DEFAULT_SRD_EDITION,
                    choices=sorted(foundry.DND5E_SRD_PACKS),
                    help="Which dnd5e SRD generation to match converted content against. "
                         "The two generations share spell and item names while differing in "
                         "text and mechanics, so the wrong one replaces a matched item with a "
                         "different edition of the same name. Pick the edition the campaign "
                         "was built on (Default: %s)" % foundry.DEFAULT_SRD_EDITION)
parser.add_argument("--npc-source", default="Roll 20", help="Source reference for NPC actors (displayed in the character sheet)")
parser.add_argument("--no-compendium-overwrite", action="store_true", help="If enabled, items, feats and spells found in the Compendium will not be overwritten with custom description/damage/etc.. from the Roll20 data")
parser.add_argument("--images-as-drawings", action="store_true", help="Set all images on the scene as textured drawings instead of tiles (requires Furnace to function properly)")
parser.add_argument("--disable-module-journal", action="store_true", help="Disable conversion of Journal entries in the module (requires --export-as-module)")
parser.add_argument("--disable-module-actors", action="store_true", help="Disable conversion of Actors in the module (requires --export-as-module)")
parser.add_argument("--disable-module-scenes", action="store_true", help="Disable conversion of Scenes in the module (requires --export-as-module)")
parser.add_argument("--disable-module-playlists", action="store_true", help="Disable conversion of Playlists in the module (requires --export-as-module)")
parser.add_argument("--disable-module-tables", action="store_true", help="Disable conversion of rollable tables in the module (requires --export-as-module)")
parser.add_argument("--disable-module-decks", action="store_true", help="Disable conversion of card decks in the module (requires --export-as-module)")
# The conversion code in R20Converter.convert() has always honoured this option,
# but the flag itself was never declared, so it was unreachable from the CLI.
parser.add_argument("--disable-module-items", action="store_true", help="Disable conversion of Items in the module (requires --export-as-module)")
parser.add_argument("--dont-convert-chat", action="store_true", help="Disable converting the chat and leave the chat log empty")
# argparse's "append" action appends to the default list rather than replacing
# it, so a non-empty default here would make "Magic Items" impossible to opt out
# of. We default to an empty list and apply the fallback after parsing instead.
DEFAULT_FOLDERS_AS_ITEMS = ["Magic Items"]
parser.add_argument("--folder-as-items", action="append", default=[], help="Converts each entry in a journal folder into items. Useful for 'Magic Items' folders. Can be passed multiple times to convert more than one folder. (Default: %s)" % ", ".join(DEFAULT_FOLDERS_AS_ITEMS))
parser.add_argument("--dont-export-actor-items", action="store_true", help="Items from actors will be exported as individual Entity Items. This option disables that behavior and no items will be created.")
parser.add_argument("--no-duplicate-actor-items", action="store_true", help="This option causes items with the same name from different actors to be exported under a single item. The first processed actor with the item of that name gets their item in the item entities.")
parser.add_argument("--use-original-image-urls", action="store_true", help="Do not copy images to the world folder but use Roll20 URL instead. (NOT recommended)")
parser.add_argument("--max-path", default=256, type=int, help="Set the maximum allowed length for the asset's absolute file paths. Most File Systems will have a limit of 256 characters, but you can set it to lower (or higher) if you plan on moving the worlds directory to a different FVTT path. Files that don't fit will be written in an 'assets' directory instead of the usual hierarchy.")
parser.add_argument("--overwrite", action="store_true", help="Overwrite the destination directory if it exists.")
parser.add_argument("--game-system", default="dnd5e", help="Set the game system to use for actors and items's sheets (only dnd5e sheets will be converted)")
parser.add_argument("--dedup-assets", action="store_true", help="Deduplicate same assets to minimize space usage. This will use store files in the assets directory and link to those files instead of copying it in a nice hierarchy. (Default: False)")
parser.add_argument("--assets-directory", default="assets", help="The directory where the assets will be copied to. This is relative to the world directory. (Default: assets)")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments means the user launched us by double-clicking or from a
        # bare command line, i.e. they want the GUI. If we cannot give them one,
        # say so explicitly rather than printing an argparse usage error, which
        # is baffling in that context (and invisible in a windowed build).
        if GUI is None:
            print("The graphical interface could not be loaded, so there is nothing to show.")
            print("Run R20Converter with --help to see the command line options.")
            print("\nThe underlying error was:\n%s" % GUI_IMPORT_ERROR)
            sys.exit(1)
        try:
            GUI.start()
            sys.exit(0)
        except Exception:
            import traceback
            print("The graphical interface failed to start.")
            print("Run R20Converter with --help to see the command line options.")
            print("\nThe underlying error was:")
            traceback.print_exc(file=sys.stdout)
            sys.exit(1)

    args = parser.parse_args()

    # See DEFAULT_FOLDERS_AS_ITEMS: apply the default only when the user gave no
    # --folder-as-items at all, so that passing the option replaces the default
    # instead of adding to it.
    if not args.folder_as_items:
        args.folder_as_items = list(DEFAULT_FOLDERS_AS_ITEMS)

    if os.path.exists(args.path):
        if args.overwrite:
            import shutil
            shutil.rmtree(args.path)
        else:
            print("Destination directory must not exist")
            sys.exit(-1)

    if args.use_original_image_urls:
        print("*** WARNING ***")
        print("You have decided to use direct image URLs instead of copying the images to the world folder")
        print("This is NOT recommended, as you are still dependent on the assets being available on Roll 20")
        print("Also, you'd be using the servers of Roll20 but not playing on their platform which is not ethically correct")
        print("Use only this option for testing purposes for example.")
    
    error = None
    try:
        converter = R20Converter(args)
        converter.convert()
    except Exception as e:
        error = e
        print(e)
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass

    if error:
        print(messages.conversionErrorMessage(version, error))
        # Exit non-zero so that shell scripts, CI and batch conversions can
        # actually detect a failed run; previously every outcome exited 0.
        sys.exit(1)

    print(messages.conversionSuccessMessage())
