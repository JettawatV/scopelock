import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  server: {
    // Development only: keep the operator key in the browser request header
    // while forwarding live API calls to the separately-running local backend.
    // No proxy configuration is included in the built Cloud Run application.
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/artifacts": "http://127.0.0.1:8080",
      "/buffers": "http://127.0.0.1:8080",
      "/gmail": "http://127.0.0.1:8080",
      "/health": "http://127.0.0.1:8080",
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
