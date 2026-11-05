// Lists [UPPERCASE] placeholder brackets left in src/. Report only: always exits 0.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../src", import.meta.url).pathname;
const pattern = /\[[A-Z][A-Z ]+\]/g;

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (/\.(tsx?|css|json|mdx?)$/.test(entry.name)) yield full;
  }
}

let count = 0;
for (const file of walk(root)) {
  readFileSync(file, "utf8").split("\n").forEach((line, i) => {
    for (const match of line.matchAll(pattern)) {
      console.log(`${relative(join(root, ".."), file)}:${i + 1}  ${match[0]}`);
      count++;
    }
  });
}
console.log(`\n${count} placeholder${count === 1 ? "" : "s"} found.`);
