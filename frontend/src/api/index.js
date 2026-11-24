/** 接口层:按领域分组的全部端点调用 */
import client from "./client";

/* ---- 认证 ---- */
export const authLogin = (data) => client.post("/login/", data).then((r) => r.data);
export const authRegister = (data) => client.post("/register/", data).then((r) => r.data);

/* ---- 行情 ---- */
export const fetchStocks = () => client.get("/stocks/").then((r) => r.data);
export const fetchIndices = () => client.get("/indices/").then((r) => r.data.indices);
export const fetchKline = (params) => client.get("/kline/", { params }).then((r) => r.data);
export const fetchSectors = () => client.get("/sectors/").then((r) => r.data);
export const fetchMarketPulse = () => client.get("/market/pulse/").then((r) => r.data);
export const fetchNews = () => client.get("/news/").then((r) => r.data);

/* ---- 自选 ---- */
export const fetchFavorites = () => client.get("/favorites/").then((r) => r.data);
export const addFavorite = (stockId) => client.post("/favorites/", { stock_id: stockId }).then((r) => r.data);
export const removeFavorite = (id) => client.delete(`/favorites/${id}/`);

/* ---- AI 助手 ---- */
export const aiQuery = (text, conversationId) =>
  client.post("/ai/query/", { text, conversation_id: conversationId }).then((r) => r.data);

/* ---- 量化回测 ---- */
export const fetchStrategies = () => client.get("/strategies/").then((r) => r.data.strategies);
export const runBacktest = (payload) => client.post("/backtest/", payload).then((r) => r.data.run);
export const runCompare = (payload) => client.post("/backtest/compare/", payload).then((r) => r.data);
export const fetchBacktestHistory = () => client.get("/backtest/history/").then((r) => r.data.runs);
export const fetchBacktestDetail = (id) => client.get(`/backtest/history/${id}/`).then((r) => r.data.run);
