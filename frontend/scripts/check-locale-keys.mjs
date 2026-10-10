import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const localeDirectory = resolve(import.meta.dirname, "../src/i18n/locales");
const locales = Object.fromEntries(
  await Promise.all(["en", "mr", "hi"].map(async (language) => {
    const contents = await readFile(resolve(localeDirectory, `${language}.json`), "utf8");
    return [language, JSON.parse(contents)];
  }))
);

function collectLeafPaths(value, parent = "") {
  return Object.entries(value).flatMap(([key, child]) => {
    const path = parent ? `${parent}.${key}` : key;
    return child !== null && typeof child === "object" && !Array.isArray(child)
      ? collectLeafPaths(child, path)
      : [path];
  });
}

const englishPaths = new Set(collectLeafPaths(locales.en));
let hasErrors = false;

for (const language of ["mr", "hi"]) {
  const translatedPaths = new Set(collectLeafPaths(locales[language]));
  const missing = [...englishPaths].filter((path) => !translatedPaths.has(path));
  const extra = [...translatedPaths].filter((path) => !englishPaths.has(path));
  if (missing.length || extra.length) {
    hasErrors = true;
    for (const path of missing) console.error(`${language}: missing ${path}`);
    for (const path of extra) console.error(`${language}: extra ${path}`);
  }
}

if (hasErrors) process.exitCode = 1;
else console.log(`Locale keys match: ${englishPaths.size} entries in en, mr, and hi.`);
