/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The backend has no CORS middleware, and none is added for this frontend --
// in dev, Vite's own proxy forwards /api/* to the backend so the browser
// only ever talks to the Vite origin (same pattern Nginx uses in prod, see
// frontend/nginx.conf), meaning the app's fetch calls hit relative
// "/api/..." paths unchanged in both environments.
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8001";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
