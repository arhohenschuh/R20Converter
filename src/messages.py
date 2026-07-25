"""
User-facing end-of-conversion messages.

These strings used to be duplicated verbatim between ``main.py`` (plain text,
printed to the console) and ``GUI.py`` (the same text with one link marked up as
HTML for the eel front-end). Keeping two copies meant every wording change had
to be made twice and one copy inevitably drifted. Both callers now render from
here, choosing the flavour with the ``html`` flag.
"""


def conversionErrorMessage(version, error):
    """Message shown when the conversion raised.

    ``error`` may be an exception or a pre-formatted traceback string; it is
    stringified as-is so the caller decides how much detail to surface.
    """
    return ("Error converting campaign with R20Converter v" + version + ": \n" + str(error) +
            "\nPlease contact the author with the log of the error from the console window")


def conversionSuccessMessage(html=False):
    """Message shown after a successful conversion.

    :param html: when True, render links as anchors for the eel/Vue front-end
        instead of bare URLs for a terminal.
    """
    forge = ("<a href='https://forge-vtt.com/setup' target='_blank'>The Forge</a>"
             if html else "The Forge (https://forge-vtt.com)")
    return ("\nConversion completed.\n\n"
            "It is strongly suggested to check the sheets of the NPCs and player characters "
            "for any errors or missing information, or for adding special traits.\n"
            "Some things may not have been carried over, especially to-hit, damage, AC or "
            "saving throw modifiers or more complicated weapon or spell macros\n"
            "If using " + forge + " for hosting your Foundry games, you can now import the "
            "generated world using the Import Wizard.\n"
            "\nThank you for your support!")
