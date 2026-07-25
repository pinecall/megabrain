// The build: one bundle, one stylesheet, one page, into the Python package.
//
// Output is COMMITTED and a CI job re-runs this and fails on a non-empty diff.
// That way `pip install -e .` works from a clone with no node installed, and
// the committed bundle cannot drift from its source — the two failure modes of
// the alternatives, avoided together.
import { build } from "esbuild";
import { copyFile, mkdir } from "node:fs/promises";

const OUT = new URL("../src/megabrain/transports/http/ui/", import.meta.url);

await mkdir(OUT, { recursive: true });
await build({
  entryPoints: ["src/main.ts"],
  bundle: true,
  format: "esm",
  target: "es2022",
  minify: true,
  sourcemap: false,          // the source ships in this repo; a map would double the bundle
  outfile: new URL("app.js", OUT).pathname,
  logLevel: "info",
});
for (const asset of ["index.html", "style.css"]) {
  await copyFile(new URL(asset, import.meta.url), new URL(asset, OUT));
}
console.log("studio built ->", OUT.pathname);
