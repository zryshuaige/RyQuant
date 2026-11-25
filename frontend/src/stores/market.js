/** 行情状态:标的/指数/自选/自选跟踪,统一轮询(页面隐藏时自动暂停) */
import { defineStore } from "pinia";
import * as api from "../api";
import { toast } from "../composables/useToast";

const POLL_MS = 5000;
let refreshPromise = null;

function hasToken() {
  return Boolean(localStorage.getItem("fin_token"));
}

export const useMarketStore = defineStore("market", {
  state: () => ({
    stocks: [],
    indices: [],
    favorites: [],
    favoritesSummary: null,
    summaryLoading: false,
    pendingFavoriteIds: [],
    loading: false,
    loaded: false,
    lastUpdated: 0,
    error: "",
    _timer: null,
    _visibilityHandler: null,
  }),
  getters: {
    favoriteStockIds: (s) => new Set(s.favorites.map((f) => f.stock.id)),
    activeStocks: (s) => s.stocks.filter((st) => st.is_active),
    stale: (s) => !s.lastUpdated || Date.now() - s.lastUpdated > 15000,
  },
  actions: {
    async fetchStocks() {
      try {
        this.stocks = await api.fetchStocks();
        this.loaded = true;
        this.lastUpdated = Date.now();
        this.error = "";
      } catch (e) {
        this.error = this.loaded
          ? "行情更新失败,当前显示的是上一次数据"
          : (e.friendlyMessage || "行情加载失败");
      }
    },
    async fetchIndices() {
      try {
        this.indices = await api.fetchIndices();
        this.lastUpdated = Date.now();
      } catch {
        if (!this.error) this.error = "行情更新失败,当前显示的是上一次数据";
      }
    },
    async fetchFavorites() {
      try {
        this.favorites = await api.fetchFavorites();
      } catch (e) {
        if (e?.response?.status !== 401) toast.error(e.friendlyMessage || "自选加载失败");
      }
    },
    async fetchFavoritesSummary() {
      if (!hasToken()) return;
      this.summaryLoading = true;
      try {
        this.favoritesSummary = await api.fetchFavoritesSummary();
      } catch (e) {
        if (e?.response?.status !== 401) toast.error(e.friendlyMessage || "自选表现加载失败");
      } finally {
        this.summaryLoading = false;
      }
    },
    async searchSymbols(q) {
      return api.searchSymbols(q);
    },
    async resolveStock(query) {
      const stock = await api.resolveStock(query);
      await this.fetchStocks();
      return stock;
    },
    async toggleFavorite(stock) {
      if (!hasToken()) {
        toast.info("登录后可添加自选");
        return false;
      }
      if (this.pendingFavoriteIds.includes(stock.id)) return false;
      this.pendingFavoriteIds.push(stock.id);
      const existing = this.favorites.find((f) => f.stock.id === stock.id);
      try {
        if (existing) {
          await api.removeFavorite(existing.id);
          this.favorites = this.favorites.filter((f) => f.id !== existing.id);
          toast.info(`已移除自选 ${stock.name}`);
        } else {
          const fav = await api.addFavorite(stock.id);
          this.favorites.unshift(fav);
          toast.success(`已加入自选 ${stock.name}`);
        }
        await this.fetchFavoritesSummary();
        return true;
      } catch (e) {
        toast.error(e.friendlyMessage || "操作失败");
        return false;
      } finally {
        this.pendingFavoriteIds = this.pendingFavoriteIds.filter((id) => id !== stock.id);
      }
    },
    resetUserState() {
      this.favorites = [];
      this.favoritesSummary = null;
      this.pendingFavoriteIds = [];
    },
    async refreshAll() {
      if (refreshPromise) return refreshPromise;
      if (!this.loaded) this.loading = true;
      refreshPromise = Promise.allSettled([this.fetchStocks(), this.fetchIndices()])
        .finally(() => {
          refreshPromise = null;
          this.loading = false;
        });
      return refreshPromise;
    },
    async ensureLoaded() {
      if (this.loaded) return;
      await this.refreshAll();
    },
    startPolling() {
      if (this._timer) return;
      this.refreshAll();
      this._timer = setInterval(() => {
        if (document.hidden) return; // 页面不可见时暂停,降低无效请求
        this.fetchStocks();
        this.fetchIndices();
      }, POLL_MS);
      this._visibilityHandler = () => {
        if (!document.hidden) {
          this.fetchStocks();
          this.fetchIndices();
        }
      };
      document.addEventListener("visibilitychange", this._visibilityHandler);
    },
    stopPolling() {
      if (this._timer) clearInterval(this._timer);
      this._timer = null;
      if (this._visibilityHandler) document.removeEventListener("visibilitychange", this._visibilityHandler);
      this._visibilityHandler = null;
    },
  },
});