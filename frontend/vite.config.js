import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 后端来源可用环境变量覆盖(默认 8080,避开常见占用)
const backendOrigin = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8080";

// 开发代理:前端统一走相对路径 /api,由 Vite 转发到 Django,彻底移除硬编码地址
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backendOrigin, changeOrigin: true },
      "/admin": { target: backendOrigin, changeOrigin: true },
      "/static": { target: backendOrigin, changeOrigin: true },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.js"],
  },
});
