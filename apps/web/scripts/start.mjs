import { cpSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const standalone = resolve(".next/standalone");
if (!existsSync(resolve(standalone, "server.js"))) {
  throw new Error("Production build missing. Run npm run build first.");
}
cpSync(resolve(".next/static"), resolve(standalone, ".next/static"), {
  recursive: true,
});
if (existsSync(resolve("public"))) {
  cpSync(resolve("public"), resolve(standalone, "public"), { recursive: true });
}
process.env.HOSTNAME ||= "127.0.0.1";
await import(pathToFileURL(resolve(standalone, "server.js")).href);
