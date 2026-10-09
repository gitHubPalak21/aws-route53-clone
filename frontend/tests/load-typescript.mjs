import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Load pure application helpers with their local imports using the existing TS compiler. */
export function loadTypeScript(relativePath, cache = new Map()) {
  const filename = path.resolve(root, relativePath);
  if (!filename.startsWith(root + path.sep)) throw new Error("Test modules must stay inside frontend/");
  if (cache.has(filename)) return cache.get(filename).exports;
  const loadedModule = { exports: {} };
  cache.set(filename, loadedModule);
  const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const requireLocal = (specifier) => {
    const resolved = specifier.startsWith("@/") ? specifier.slice(2)
      : path.relative(root, path.resolve(path.dirname(filename), specifier));
    return loadTypeScript(resolved + ".ts", cache);
  };
  new Function("module", "exports", "require", code)(loadedModule, loadedModule.exports, requireLocal);
  return loadedModule.exports;
}
