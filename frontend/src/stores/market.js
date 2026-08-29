/** 行情状态:标的/指数/自选,统一轮询(页面隐藏时自动暂停) */
import { defineStore } from "pinia";
import * as api from "../api";
import { toast } from "../composables/useToast";

const POLL_MS = 5000;

export const useMarketStore = defineStore("market", {
  state: () => ({
    stocks: [],
    indices: [],
    favorites: [],
    loading: false,
    loaded: false,
    _timer: null,
    _visibilityHandler: null,
  }),
  getters: {
    favoriteStockIds: (s) => new Set(s.favorites.map((f) => f.stock.id)),
    activeStocks: (s) => s.stocks.filter((st) => st.is_active),
  },
  actions: {
    async fetchStocks() {
      try {
        this.stocks = await api.fetchStocks();
        this.loaded = true;
      } catch (e) {
        if (!this.loaded) console.warn("行情加载失败", e.friendlyMessage || e.message);
      }
    },
    async fetchIndices() {
      try {
        this.indices = await api.fetchIndices();
      } catch { /* 静默,下一轮重试 */ }
    },
    async fetchFavorites() {
      this.favorites = await api.fetchFavorites();
    },
    async toggleFavorite(stock) {
      const existing = this.favorites.find((f) => f.stock.id === stock.id);
      try {
        if (existing) {
          await api.removeFavorite(existing.id);
          this.favorites = this.favorites.filter((f) => f.id !== existing.id);
          toast.info(`已移除自选 ${stock.name}`);
        } else {
          const fav = await api.addFavorite(stock.id);
          this.favorites.push(fav);
          toast.success(`已加入自选 ${stock.name}`);
        }
      } catch (e) {
        toast.error(e.friendlyMessage || "操作失败");
      }
    },
    async refreshAll() {
      if (!this._timer) this.loading = true;
      await Promise.all([this.fetchStocks(), this.fetchIndices()]);
      this.loading = false;
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
