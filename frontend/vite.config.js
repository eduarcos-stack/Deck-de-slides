import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local-first: o frontend fala com a API na própria máquina (§47).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
