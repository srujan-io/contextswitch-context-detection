import { existsSync } from "node:fs";
import { env } from "node:process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const extensionRoot = resolve(
  env["CONTEXTSWITCH_EXTENSION_DIR"] ?? resolve(frontendRoot, "../extension"),
);
if (!existsSync(resolve(extensionRoot, "manifest.json"))) {
  throw new Error(
    "Set CONTEXTSWITCH_EXTENSION_DIR to the ContextSwitch extension directory before building the popup.",
  );
}

export default defineConfig({
  root: frontendRoot,
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: { tsconfigPaths: true },
  build: {
    outDir: resolve(extensionRoot, "ui"),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(frontendRoot, "extension.html"),
    },
  },
});
