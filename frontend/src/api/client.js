/** axios 实例:Token 注入 / 统一错误提取 / 401 全局处理 */
import axios from "axios";

export const API_BASE = "/api"; // 走 Vite 代理,无硬编码后端地址

let unauthorizedHandler = null;
export function onUnauthorized(fn) {
  unauthorizedHandler = fn;
}

export function extractError(error) {
  const data = error?.response?.data;
  if (data) {
    if (typeof data === "string") return data;
    if (data.detail) {
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail)) return data.detail.join("; ");
    }
    // DRF 字段错误字典: {username: ["..."]}
    const first = Object.entries(data)[0];
    if (first) {
      const [field, msgs] = first;
      const text = Array.isArray(msgs) ? msgs.join("; ") : String(msgs);
      return field === "detail" ? text : `${field}: ${text}`;
    }
  }
  if (error?.code === "ECONNABORTED") return "请求超时,请稍后重试";
  if (error?.message === "Network Error") return "网络异常,请确认后端服务已启动";
  return error?.message || "请求失败";
}

const client = axios.create({ baseURL: API_BASE, timeout: 20000 });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("fin_token");
  if (token) config.headers.Authorization = `Token ${token}`;
  return config;
});

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    error.friendlyMessage = extractError(error);
    if (error?.response?.status === 401 && unauthorizedHandler) {
      unauthorizedHandler();
    }
    return Promise.reject(error);
  }
);

export default client;
