import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      // Dev proxy: forward /api calls to the backend
      "/api": {
        target: "http://localhost:9000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      // Also proxy /metrics directly to backend
      "/metrics": {
        target: "http://localhost:9000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4173,
  },
});
