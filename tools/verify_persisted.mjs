/**
 * verify-persisted.mjs — read the LevelDB Foundry actually wrote and check it.
 *
 *   node verify-persisted.mjs "<world dir>"
 *
 * This is the check that matters. A unit test asserts on a Python dict; a check
 * on the emitted NeDB asserts on what the converter wrote. Neither can see what
 * Foundry did to the documents when it loaded them — and Foundry's dnd5e
 * migration is known to consume `damage.parts`, stamp `_stats.systemVersion`,
 * and write an EMPTY `damage.base` back for a subset of documents. A compat shim
 * rebuilds it in memory, so the LIVE document reads correctly while the STORED
 * one holds nothing. Measured on a real module: 390 weapons with dice live, 293
 * stored.
 *
 * So: read the stored bytes, not the live document.
 */

// classic-level ships with Foundry itself, so no dependency has to be installed:
//   node tools/verify_persisted.mjs <world> --foundry "<FoundryVTT>/resources/app"
const foundryArg = process.argv.indexOf("--foundry");
const foundryApp = foundryArg > -1 ? process.argv[foundryArg + 1] : process.env.FOUNDRY_APP_PATH;
if (!foundryApp) {
  console.error("pass --foundry <path to Foundry resources/app> or set FOUNDRY_APP_PATH");
  process.exit(2);
}
const { ClassicLevel } = await import(
  new URL("node_modules/classic-level/index.js", `file://${foundryApp.replace(/\\/g, "/")}/`).href);
import path from "node:path";
import process from "node:process";

const EXPECTED_SYSTEM_VERSION = "5.3.3";

const LEGACY_ITEM_FIELDS = [
  "weaponType", "armorType", "consumableType", "toolType", "actionType",
  "attackBonus", "chatFlavor", "critical", "formula", "scaling", "ability",
  "components", "preparation", "consume", "recharge"
];

async function readPack(dir) {
  const db = new ClassicLevel(dir, { valueEncoding: "json" });
  const out = [];
  try {
    for await (const [key, value] of db.iterator()) out.push([key, value]);
  } finally {
    await db.close();
  }
  return out;
}

function fail(list, label, detail = "") {
  list.push(label + (detail ? ` - ${detail}` : ""));
}

function report(ok, failures) {
  console.log("persisted dnd5e check");
  for (const line of ok) console.log(`  ok   ${line}`);
  for (const line of failures) console.log(`  FAIL ${line}`);
  console.log(`\n  ${failures.length ? `FAIL (${failures.length})` : "PASS"}`);
  process.exit(failures.length ? 1 : 0);
}

async function main() {
  const world = process.argv[2];
  if (!world) {
    console.error("usage: node verify-persisted.mjs <world dir>");
    process.exit(2);
  }
  const data = path.join(world, "data");
  const failures = [];
  const ok = [];

  const actorRows = await readPack(path.join(data, "actors"));
  const itemRows = await readPack(path.join(data, "items"));
  const settingRows = await readPack(path.join(data, "settings"));

  // Top-level documents only; embedded ones use `!actors.items!parent.child`.
  const actors = actorRows.filter(([k]) => k.startsWith("!actors!")).map(([, v]) => v);
  const ownedItems = actorRows
    .filter(([k]) => k.startsWith("!actors.items!")).map(([, v]) => v);
  const worldItems = itemRows.filter(([k]) => k.startsWith("!items!")).map(([, v]) => v);
  const items = [...worldItems, ...ownedItems];

  // Non-vacuity. A run that scans nothing and reports PASS is worse than none.
  actors.length ? ok.push(`actors persisted: ${actors.length}`)
    : fail(failures, "no actors persisted");
  items.length ? ok.push(`items persisted: ${items.length} (${worldItems.length} world, ${ownedItems.length} owned)`)
    : fail(failures, "no items persisted");
  if (!items.length) { report(ok, failures); return; }

  // 1. Did a dnd5e migration run?
  const migration = settingRows
    .map(([, v]) => v)
    .find(s => s?.key === "dnd5e.systemMigrationVersion");
  if (!migration) fail(failures, "dnd5e.systemMigrationVersion setting is missing");
  else if (String(migration.value).replace(/"/g, "") !== EXPECTED_SYSTEM_VERSION) {
    fail(failures, "systemMigrationVersion moved", `${migration.value}`);
  } else ok.push(`dnd5e.systemMigrationVersion = ${migration.value}`);

  // 2. Foundry sets this flag on every document its migration rewrote.
  const migrated = items.filter(i => i.flags?.dnd5e?.persistSourceMigration);
  migrated.length === 0
    ? ok.push("no document carries flags.dnd5e.persistSourceMigration")
    : fail(failures, "documents were rewritten by the dnd5e migration",
      `${migrated.length}, e.g. ${migrated.slice(0, 3).map(i => i.name).join(", ")}`);

  // 3. Legacy fields, read from storage rather than from the emitter.
  const legacy = new Map();
  for (const item of items) {
    const system = item.system ?? {};
    for (const field of LEGACY_ITEM_FIELDS) {
      if (field in system) legacy.set(field, (legacy.get(field) ?? 0) + 1);
    }
    if (system.damage && "parts" in system.damage) {
      legacy.set("damage.parts", (legacy.get("damage.parts") ?? 0) + 1);
    }
  }
  legacy.size === 0 ? ok.push("no legacy fields survived the load")
    : fail(failures, "legacy fields present after load",
      [...legacy].map(([k, v]) => `${k} x${v}`).join(", "));

  // 4. THE trap (M09): the migration writes an empty damage.base while a shim
  //    keeps the live document looking right.
  const weapons = items.filter(i => i.type === "weapon");
  const armed = weapons.filter(w => w.system?.damage?.base?.denomination);
  weapons.length && armed.length === weapons.length
    ? ok.push(`weapons with dice in STORED damage.base: ${armed.length}/${weapons.length}`)
    : fail(failures, "weapons lost their stored damage",
      `${armed.length}/${weapons.length}`);

  // 5. Activities survived. The migration never creates them for weapons, so a
  //    zero here means we depended on it after all.
  const rollable = items.filter(i => ["weapon", "spell", "feat", "consumable"].includes(i.type));
  const withActivity = rollable.filter(i => Object.keys(i.system?.activities ?? {}).length);
  const orphans = rollable.filter(i =>
    !Object.keys(i.system?.activities ?? {}).length && i.system?.activation?.type);
  orphans.length === 0
    ? ok.push(`activities: ${withActivity.length}/${rollable.length} rollable, 0 activated-without-activity`)
    : fail(failures, "activated items lost their activity", `${orphans.length}`);

  const weaponsWithActivity = weapons.filter(w => Object.keys(w.system?.activities ?? {}).length);
  weapons.length && weaponsWithActivity.length === weapons.length
    ? ok.push(`every weapon has an attack activity: ${weaponsWithActivity.length}/${weapons.length}`)
    : fail(failures, "weapons without an activity",
      `${weapons.length - weaponsWithActivity.length}`);

  // 6. Version stamps survived.
  const stamped = [...items, ...actors]
    .filter(d => d._stats?.systemVersion === EXPECTED_SYSTEM_VERSION);
  stamped.length === items.length + actors.length
    ? ok.push(`_stats.systemVersion intact: ${stamped.length}/${items.length + actors.length}`)
    : fail(failures, "_stats.systemVersion changed on load",
      `${stamped.length}/${items.length + actors.length}`);

  // 7. Named sentinels, so a silently-empty world cannot pass.
  const names = [...new Set(items.map(i => i.name))];
  const sentinels = ["Bite", "Shortsword", "Dagger", "Club", "Shortbow"];
  const found = sentinels.filter(s => names.some(n => n === s || n?.startsWith(s)));
  found.length >= 3
    ? ok.push(`sentinels found: ${found.join(", ")}`)
    : fail(failures, "sentinel weapons missing", found.join(", ") || "none");

  report(ok, failures);
}

main().catch(err => { console.error(err); process.exit(2); });
