export default {
    file: null,
    folder: null,
    title: null,
    slug: null,
    error: null,
    form: {},
    foundryDirectory: null,
    debugLog: "",
    compendiumValidation: { path: "", valid: false, pending: false, error: null },
    options: {
        srdEdition: "2014",
        dnd5eVersion: "6.x",
        sceneFolders: null,
        convertCompendium: false,
        compendiumZip: ""
    },
    conversionDone: false,
    conversionError: false
}