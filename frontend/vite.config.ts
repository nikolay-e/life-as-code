import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Get version info from environment (set during build)
const version = process.env.VITE_APP_VERSION || "dev";
const buildDate = process.env.VITE_BUILD_DATE || new Date().toISOString();
const commitSha = process.env.VITE_COMMIT_SHA || "unknown";

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __BUILD_DATE__: JSON.stringify(buildDate),
    __COMMIT_SHA__: JSON.stringify(commitSha),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        // Vite's content-based [hash] provides cache busting
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash].[ext]",
      },
    },
  },
});
